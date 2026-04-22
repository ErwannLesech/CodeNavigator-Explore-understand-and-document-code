from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.embedding.chunker import chunk_parsed_file
from src.embedding.embedder import Embedder
from src.embedding.vector_store import VectorStore
from src.generation.assembler import build_project_doc, estimate_doc_workload
from src.generation.doc_generator import DocGenerator
from src.generation.exporter import export_to_markdown
from src.graph.builder import GraphBuilder
from src.graph.json_exporter import export_graph_json
from src.ingestion.parser_dispatcher import dispatch_parser
from src.ingestion.repo_walker import walk_repo

from backend.config import MAX_PIPELINE_EVENTS
from backend.schemas import (
    PipelineEvent,
    PipelineRunRequest,
    PipelineStartResponse,
    PipelineStatusResponse,
)


class PipelineCancelledError(RuntimeError):
    pass


# Shared mutable runtime for pipeline jobs. Guard every read/write with this lock.
PIPELINE_LOCK = threading.RLock()
PIPELINE_CANCEL_EVENT = threading.Event()
PIPELINE_STATE: dict[str, Any] = {
    "job_id": None,
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "progress": 0.0,
    "current_stage": "idle",
    "error": None,
    "request": None,
    "stats": {"files": 0, "parsed_files": 0, "chunks": 0, "embeddings": 0},
    "outputs": {"docs": "", "graph": "", "graph_json": ""},
    "events": [],
}


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def append_pipeline_event(
    stage: str,
    message: str,
    progress: float,
    details: dict[str, Any] | None = None,
) -> None:
    # Event append and truncation must stay in one critical section.
    with PIPELINE_LOCK:
        PIPELINE_STATE["current_stage"] = stage
        PIPELINE_STATE["progress"] = round(progress, 2)
        event = {
            "timestamp": utc_now(),
            "stage": stage,
            "message": message,
            "progress": round(progress, 2),
            "details": details,
        }
        PIPELINE_STATE["events"].append(event)
        if len(PIPELINE_STATE["events"]) > MAX_PIPELINE_EVENTS:
            PIPELINE_STATE["events"] = PIPELINE_STATE["events"][-MAX_PIPELINE_EVENTS:]


def raise_if_pipeline_cancelled() -> None:
    if PIPELINE_CANCEL_EVENT.is_set():
        raise PipelineCancelledError("Pipeline cancelled by user request.")


def pipeline_snapshot() -> PipelineStatusResponse:
    with PIPELINE_LOCK:
        return PipelineStatusResponse(
            job_id=PIPELINE_STATE["job_id"],
            status=PIPELINE_STATE["status"],
            started_at=PIPELINE_STATE["started_at"],
            finished_at=PIPELINE_STATE["finished_at"],
            progress=float(PIPELINE_STATE["progress"]),
            current_stage=PIPELINE_STATE["current_stage"],
            error=PIPELINE_STATE["error"],
            request=dict(PIPELINE_STATE["request"])
            if PIPELINE_STATE["request"]
            else None,
            stats=dict(PIPELINE_STATE["stats"]),
            outputs=dict(PIPELINE_STATE["outputs"]),
            events=[PipelineEvent(**event) for event in PIPELINE_STATE["events"]],
        )


def start_pipeline(request: PipelineRunRequest) -> PipelineStartResponse:
    with PIPELINE_LOCK:
        job_id = str(uuid.uuid4())
        PIPELINE_STATE["job_id"] = job_id
        PIPELINE_STATE["status"] = "queued"
        PIPELINE_CANCEL_EVENT.clear()

    worker = threading.Thread(
        target=run_pipeline_job,
        args=(job_id, request),
        daemon=True,
    )
    worker.start()

    return PipelineStartResponse(job_id=job_id, status="queued")


def reset_pipeline_status() -> PipelineStatusResponse:
    with PIPELINE_LOCK:
        PIPELINE_CANCEL_EVENT.clear()
        PIPELINE_STATE.update(
            {
                "job_id": None,
                "status": "idle",
                "started_at": None,
                "finished_at": None,
                "progress": 0.0,
                "current_stage": "idle",
                "error": None,
                "request": None,
                "stats": {
                    "files": 0,
                    "parsed_files": 0,
                    "chunks": 0,
                    "embeddings": 0,
                },
                "outputs": {"docs": "", "graph": "", "graph_json": ""},
                "events": [],
            }
        )
    return pipeline_snapshot()


def cancel_pipeline() -> PipelineStatusResponse:
    with PIPELINE_LOCK:
        PIPELINE_CANCEL_EVENT.set()
        PIPELINE_STATE["status"] = "cancelling"

    append_pipeline_event(
        stage="cancelling",
        message="Cancellation requested",
        progress=float(PIPELINE_STATE.get("progress", 0.0)),
    )
    return pipeline_snapshot()


def run_pipeline_job(job_id: str, request: PipelineRunRequest) -> None:
    with PIPELINE_LOCK:
        if PIPELINE_CANCEL_EVENT.is_set():
            PIPELINE_STATE["status"] = "cancelled"
            PIPELINE_STATE["started_at"] = utc_now()
            PIPELINE_STATE["finished_at"] = utc_now()
            PIPELINE_STATE["current_stage"] = "cancelled"
            PIPELINE_STATE["error"] = None
            return
        PIPELINE_STATE["status"] = "running"
        PIPELINE_STATE["started_at"] = utc_now()
        PIPELINE_STATE["finished_at"] = None
        PIPELINE_STATE["error"] = None
        PIPELINE_STATE["progress"] = 0.0
        PIPELINE_STATE["current_stage"] = "starting"
        PIPELINE_STATE["request"] = request.model_dump()
        PIPELINE_STATE["stats"] = {
            "files": 0,
            "parsed_files": 0,
            "chunks": 0,
            "embeddings": 0,
        }
        PIPELINE_STATE["outputs"] = {"docs": "", "graph": "", "graph_json": ""}
        PIPELINE_STATE["events"] = []

    try:
        append_pipeline_event(
            stage="starting",
            message="Pipeline started",
            progress=1,
            details={"repo": request.repo},
        )
        raise_if_pipeline_cancelled()

        files = list(walk_repo(request.repo))

        with PIPELINE_LOCK:
            PIPELINE_STATE["stats"]["files"] = len(files)

        append_pipeline_event(
            stage="scan",
            message=f"Repository scanned: {len(files)} files detected",
            progress=6,
        )

        parsed_files = []
        all_chunks = []
        file_count = len(files)
        parse_tick = max(1, file_count // 20)

        for index, source_file in enumerate(files, start=1):
            raise_if_pipeline_cancelled()
            parsed = dispatch_parser(source_file, sql_dialect=request.dialect)
            parsed_files.append(parsed)
            file_chunks = chunk_parsed_file(parsed)
            all_chunks.extend(file_chunks)

            with PIPELINE_LOCK:
                PIPELINE_STATE["stats"]["parsed_files"] = index
                PIPELINE_STATE["stats"]["chunks"] = len(all_chunks)

            if index % parse_tick == 0 or index == file_count:
                append_pipeline_event(
                    stage="parsing",
                    message=f"Parsed {index}/{file_count}: {source_file.relative_path}",
                    progress=6 + (index / file_count) * 34,
                    details={"chunks": len(all_chunks)},
                )

        store = VectorStore()
        raise_if_pipeline_cancelled()
        append_pipeline_event(
            stage="embedding",
            message="Preparing Qdrant collection",
            progress=42,
            details={"collection": "CodeNavigatorChunks"},
        )
        store.create_collection(recreate=request.recreate)

        if request.dry_run:
            append_pipeline_event(
                stage="embedding",
                message="Dry-run enabled: embedding generation skipped",
                progress=62,
            )
        else:
            embedder = Embedder()
            embeddings: list[list[float]] = []
            total_chunks = len(all_chunks)
            if total_chunks > 0:
                batch_size = 100
                for start_idx in range(0, total_chunks, batch_size):
                    raise_if_pipeline_cancelled()
                    batch = all_chunks[start_idx : start_idx + batch_size]
                    response = embedder.client.embeddings.create(
                        model="mistral-embed", inputs=[chunk.content for chunk in batch]
                    )
                    data = response.data if response is not None else []
                    embeddings.extend(
                        [item.embedding for item in data if item.embedding is not None]
                    )
                    processed = min(start_idx + batch_size, total_chunks)
                    with PIPELINE_LOCK:
                        PIPELINE_STATE["stats"]["embeddings"] = len(embeddings)

                    append_pipeline_event(
                        stage="embedding",
                        message=f"Embedded {processed}/{total_chunks} chunks",
                        progress=42 + (processed / total_chunks) * 20,
                    )

                    if processed < total_chunks and PIPELINE_CANCEL_EVENT.wait(0.5):
                        raise PipelineCancelledError(
                            "Pipeline cancelled by user request."
                        )

                raise_if_pipeline_cancelled()
                store.upsert_chunks(all_chunks, embeddings)
                append_pipeline_event(
                    stage="embedding",
                    message="Embeddings uploaded to Qdrant",
                    progress=64,
                )

        estimated_llm_calls, modules_count = estimate_doc_workload(all_chunks, "full")

        append_pipeline_event(
            stage="docs",
            message="Generating project documentation",
            progress=70,
            details={
                "output": request.output_docs,
                "estimated_llm_calls": estimated_llm_calls,
                "modules": modules_count,
            },
        )

        docs_result: dict[str, Any] = {
            "completed": 0,
            "total": estimated_llm_calls,
            "last_label": None,
        }

        def docs_worker() -> None:
            generator = DocGenerator()

            def on_doc_progress(done: int, total: int, label: str) -> None:
                docs_result["completed"] = done
                docs_result["total"] = total
                docs_result["last_label"] = label

            project_doc = build_project_doc(
                all_chunks,
                generator,
                detail_level="full",
                progress_callback=on_doc_progress,
            )
            export_to_markdown(project_doc, request.output_docs)

        docs_thread = threading.Thread(target=docs_worker, daemon=True)
        docs_thread.start()

        docs_elapsed = 0
        docs_heartbeat_seconds = 6
        while docs_thread.is_alive():
            if PIPELINE_CANCEL_EVENT.wait(docs_heartbeat_seconds):
                raise PipelineCancelledError("Pipeline cancelled by user request.")
            docs_elapsed += docs_heartbeat_seconds
            completed = int(docs_result.get("completed") or 0)
            total = int(docs_result.get("total") or estimated_llm_calls)
            label = docs_result.get("last_label") or "starting"
            if total > 0 and completed > 0:
                docs_progress = min(83.5, 70 + (completed / total) * 13.5)
            else:
                docs_progress = min(83.5, 70 + (docs_elapsed / 240) * 13.5)
            append_pipeline_event(
                stage="docs",
                message=(
                    "Documentation generation in progress "
                    f"({completed}/{total}, {docs_elapsed}s elapsed)"
                ),
                progress=docs_progress,
                details={
                    "estimated_llm_calls": estimated_llm_calls,
                    "output": request.output_docs,
                    "docs_done": completed,
                    "docs_total": total,
                    "docs_last_label": label,
                },
            )

        raise_if_pipeline_cancelled()
        docs_thread.join()

        append_pipeline_event(
            stage="docs",
            message="Documentation generated",
            progress=84,
            details={"output": request.output_docs},
        )

        append_pipeline_event(
            stage="graph",
            message="Building knowledge graph",
            progress=88,
            details={"output": request.output_graph},
        )
        raise_if_pipeline_cancelled()

        builder = GraphBuilder()
        builder.ingest(parsed_files)
        nodes = builder.get_nodes()
        edges = builder.get_edges()

        graph_json_path = str(Path(request.output_graph) / "graph.json")
        export_graph_json(nodes, edges, output_path=graph_json_path)
        raise_if_pipeline_cancelled()

        os.environ["GRAPH_JSON_PATH"] = graph_json_path
        import backend.chat as chat_backend

        chat_backend._chatbot = None

        append_pipeline_event(
            stage="done",
            message="Pipeline completed successfully",
            progress=100,
            details={"graph_json": graph_json_path},
        )

        with PIPELINE_LOCK:
            PIPELINE_STATE["status"] = "succeeded"
            PIPELINE_STATE["finished_at"] = utc_now()
            PIPELINE_STATE["outputs"] = {
                "docs": request.output_docs,
                "graph": request.output_graph,
                "graph_json": graph_json_path,
            }
    except PipelineCancelledError as exc:
        append_pipeline_event(
            stage="cancelled",
            message=str(exc),
            progress=float(PIPELINE_STATE.get("progress", 0.0)),
        )
        with PIPELINE_LOCK:
            PIPELINE_STATE["status"] = "cancelled"
            PIPELINE_STATE["finished_at"] = utc_now()
            PIPELINE_STATE["error"] = None
    except Exception as exc:
        append_pipeline_event(
            stage="failed",
            message=f"Pipeline failed: {exc}",
            progress=float(PIPELINE_STATE.get("progress", 0.0)),
        )
        with PIPELINE_LOCK:
            PIPELINE_STATE["status"] = "failed"
            PIPELINE_STATE["finished_at"] = utc_now()
            PIPELINE_STATE["error"] = str(exc)
    finally:
        PIPELINE_CANCEL_EVENT.clear()
