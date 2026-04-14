from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.codeNavigator.embedding.chunker import chunk_parsed_file
from src.codeNavigator.embedding.embedder import Embedder
from src.codeNavigator.embedding.vector_store import COLLECTION_NAME, VectorStore
from src.codeNavigator.generation.assembler import (
    build_project_doc,
    estimate_doc_workload,
)
from src.codeNavigator.generation.doc_generator import DocGenerator
from src.codeNavigator.generation.exporter import export_to_markdown
from src.codeNavigator.graph.builder import GraphBuilder
from src.codeNavigator.graph.json_exporter import export_graph_json
from src.codeNavigator.ingestion.parser_dispatcher import dispatch_parser
from src.codeNavigator.ingestion.repo_walker import walk_repo

from backend.chat import router as chat_router


DOCS_OUTPUT_DIR = Path(os.getenv("DOCS_OUTPUT_DIR", "data/output/docs"))
MODULES_DIR = DOCS_OUTPUT_DIR / "modules"
GRAPH_JSON_PATH = Path(os.getenv("GRAPH_JSON_PATH", "data/output/graph/graph.json"))
README_PATH = DOCS_OUTPUT_DIR / "README.md"
INDEX_PATH = DOCS_OUTPUT_DIR / "INDEX.md"


class HealthResponse(BaseModel):
    status: str


class DocModule(BaseModel):
    name: str
    path: str
    kind: str = "module"
    source_path: str | None = None


class DocsListResponse(BaseModel):
    documents: list[DocModule]
    modules: list[DocModule]


class DocContentResponse(BaseModel):
    content: str


class DocsSearchResult(BaseModel):
    name: str
    path: str
    kind: str
    snippet: str
    source_path: str | None = None


class DocsSearchResponse(BaseModel):
    query: str
    results: list[DocsSearchResult]


class RelatedDocsResponse(BaseModel):
    module_name: str
    related: list[DocModule]


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class PipelineRunRequest(BaseModel):
    repo: str
    output_docs: str = "data/output/docs"
    output_graph: str = "data/output/graph"
    recreate: bool = False
    dialect: str = "mysql"
    dry_run: bool = False


class PipelineStartResponse(BaseModel):
    job_id: str
    status: str


class PipelineEvent(BaseModel):
    timestamp: str
    stage: str
    message: str
    progress: float
    details: dict[str, Any] | None = None


class PipelineStatusResponse(BaseModel):
    job_id: str | None
    status: str
    started_at: str | None
    finished_at: str | None
    progress: float
    current_stage: str
    error: str | None
    request: dict[str, Any] | None
    stats: dict[str, Any]
    outputs: dict[str, str]
    events: list[PipelineEvent]


class QdrantInfoResponse(BaseModel):
    host: str
    port: int
    url: str
    reachable: bool
    active_collection: str
    collections: list[str]


class QdrantOpenResponse(BaseModel):
    status: str
    url: str


MAX_PIPELINE_EVENTS = 600

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


class PipelineCancelledError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _append_pipeline_event(
    stage: str,
    message: str,
    progress: float,
    details: dict[str, Any] | None = None,
) -> None:
    with PIPELINE_LOCK:
        PIPELINE_STATE["current_stage"] = stage
        PIPELINE_STATE["progress"] = round(progress, 2)
        event = {
            "timestamp": _utc_now(),
            "stage": stage,
            "message": message,
            "progress": round(progress, 2),
            "details": details,
        }
        PIPELINE_STATE["events"].append(event)
        if len(PIPELINE_STATE["events"]) > MAX_PIPELINE_EVENTS:
            PIPELINE_STATE["events"] = PIPELINE_STATE["events"][-MAX_PIPELINE_EVENTS:]


def _raise_if_pipeline_cancelled() -> None:
    if PIPELINE_CANCEL_EVENT.is_set():
        raise PipelineCancelledError("Pipeline cancelled by user request.")


def _pipeline_snapshot() -> PipelineStatusResponse:
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


def _run_pipeline_job(job_id: str, request: PipelineRunRequest) -> None:
    with PIPELINE_LOCK:
        if PIPELINE_CANCEL_EVENT.is_set():
            PIPELINE_STATE["status"] = "cancelled"
            PIPELINE_STATE["started_at"] = _utc_now()
            PIPELINE_STATE["finished_at"] = _utc_now()
            PIPELINE_STATE["current_stage"] = "cancelled"
            PIPELINE_STATE["error"] = None
            return
        PIPELINE_STATE["status"] = "running"
        PIPELINE_STATE["started_at"] = _utc_now()
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
        _append_pipeline_event(
            stage="starting",
            message="Pipeline started",
            progress=1,
            details={"repo": request.repo},
        )
        _raise_if_pipeline_cancelled()

        files = list(walk_repo(request.repo))
        if not files:
            raise ValueError("No supported source files found in repository.")

        with PIPELINE_LOCK:
            PIPELINE_STATE["stats"]["files"] = len(files)

        _append_pipeline_event(
            stage="scan",
            message=f"Repository scanned: {len(files)} files detected",
            progress=6,
        )

        parsed_files = []
        all_chunks = []
        file_count = len(files)
        parse_tick = max(1, file_count // 20)

        for index, source_file in enumerate(files, start=1):
            _raise_if_pipeline_cancelled()
            parsed = dispatch_parser(source_file, sql_dialect=request.dialect)
            parsed_files.append(parsed)
            file_chunks = chunk_parsed_file(parsed)
            all_chunks.extend(file_chunks)

            with PIPELINE_LOCK:
                PIPELINE_STATE["stats"]["parsed_files"] = index
                PIPELINE_STATE["stats"]["chunks"] = len(all_chunks)

            if index % parse_tick == 0 or index == file_count:
                _append_pipeline_event(
                    stage="parsing",
                    message=f"Parsed {index}/{file_count}: {source_file.relative_path}",
                    progress=6 + (index / file_count) * 34,
                    details={"chunks": len(all_chunks)},
                )

        store = VectorStore()
        _raise_if_pipeline_cancelled()
        _append_pipeline_event(
            stage="embedding",
            message="Preparing Qdrant collection",
            progress=42,
            details={"collection": COLLECTION_NAME},
        )
        store.create_collection(recreate=request.recreate)

        if request.dry_run:
            _append_pipeline_event(
                stage="embedding",
                message="Dry-run enabled: embedding generation skipped",
                progress=62,
            )
        else:
            embedder = Embedder()
            embeddings: list[list[float]] = []
            total_chunks = len(all_chunks)
            if total_chunks == 0:
                raise ValueError("No chunks generated from parsed files.")

            batch_size = 100
            for start_idx in range(0, total_chunks, batch_size):
                _raise_if_pipeline_cancelled()
                batch = all_chunks[start_idx : start_idx + batch_size]
                response = embedder.client.embeddings.create(
                    model="mistral-embed", inputs=[chunk.content for chunk in batch]
                )
                if response is None or response.data is None:
                    raise RuntimeError("Embedding API returned an empty response")

                embeddings.extend([item.embedding for item in response.data])
                processed = min(start_idx + batch_size, total_chunks)
                with PIPELINE_LOCK:
                    PIPELINE_STATE["stats"]["embeddings"] = len(embeddings)

                _append_pipeline_event(
                    stage="embedding",
                    message=f"Embedded {processed}/{total_chunks} chunks",
                    progress=42 + (processed / total_chunks) * 20,
                )

                if processed < total_chunks:
                    if PIPELINE_CANCEL_EVENT.wait(0.5):
                        raise PipelineCancelledError("Pipeline cancelled by user request.")

            _raise_if_pipeline_cancelled()
            store.upsert_chunks(all_chunks, embeddings)
            _append_pipeline_event(
                stage="embedding",
                message="Embeddings uploaded to Qdrant",
                progress=64,
            )

        estimated_llm_calls, modules_count = estimate_doc_workload(
            all_chunks, "full"
        )

        _append_pipeline_event(
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
            "ok": False,
            "error": None,
            "completed": 0,
            "total": estimated_llm_calls,
            "last_label": None,
        }

        def _docs_worker() -> None:
            try:
                generator = DocGenerator()

                def _on_doc_progress(done: int, total: int, label: str) -> None:
                    docs_result["completed"] = done
                    docs_result["total"] = total
                    docs_result["last_label"] = label

                project_doc = build_project_doc(
                    all_chunks,
                    generator,
                    detail_level="full",
                    progress_callback=_on_doc_progress,
                )
                export_to_markdown(project_doc, request.output_docs)
                docs_result["ok"] = True
            except Exception as docs_exc:
                docs_result["error"] = docs_exc

        docs_thread = threading.Thread(target=_docs_worker, daemon=True)
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
            _append_pipeline_event(
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

        _raise_if_pipeline_cancelled()
        docs_thread.join()
        if docs_result["error"] is not None:
            raise RuntimeError(str(docs_result["error"]))

        _append_pipeline_event(
            stage="docs",
            message="Documentation generated",
            progress=84,
            details={"output": request.output_docs},
        )

        _append_pipeline_event(
            stage="graph",
            message="Building knowledge graph",
            progress=88,
            details={"output": request.output_graph},
        )
        _raise_if_pipeline_cancelled()

        builder = GraphBuilder()
        builder.ingest(parsed_files)
        nodes = builder.get_nodes()
        edges = builder.get_edges()

        graph_json_path = str(Path(request.output_graph) / "graph.json")
        export_graph_json(nodes, edges, output_path=graph_json_path)
        _raise_if_pipeline_cancelled()

        os.environ["GRAPH_JSON_PATH"] = graph_json_path
        import backend.chat as chat_backend

        chat_backend._chatbot = None

        _append_pipeline_event(
            stage="done",
            message="Pipeline completed successfully",
            progress=100,
            details={"graph_json": graph_json_path},
        )

        with PIPELINE_LOCK:
            PIPELINE_STATE["status"] = "succeeded"
            PIPELINE_STATE["finished_at"] = _utc_now()
            PIPELINE_STATE["outputs"] = {
                "docs": request.output_docs,
                "graph": request.output_graph,
                "graph_json": graph_json_path,
            }
    except PipelineCancelledError as exc:
        _append_pipeline_event(
            stage="cancelled",
            message=str(exc),
            progress=float(PIPELINE_STATE.get("progress", 0.0)),
        )
        with PIPELINE_LOCK:
            PIPELINE_STATE["status"] = "cancelled"
            PIPELINE_STATE["finished_at"] = _utc_now()
            PIPELINE_STATE["error"] = None
    except Exception as exc:
        _append_pipeline_event(
            stage="failed",
            message=f"Pipeline failed: {exc}",
            progress=float(PIPELINE_STATE.get("progress", 0.0)),
        )
        with PIPELINE_LOCK:
            PIPELINE_STATE["status"] = "failed"
            PIPELINE_STATE["finished_at"] = _utc_now()
            PIPELINE_STATE["error"] = str(exc)
    finally:
        PIPELINE_CANCEL_EVENT.clear()


def _qdrant_url() -> str:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return f"http://{host}:{port}/dashboard"


def _qdrant_public_url() -> str:
    host = os.getenv("QDRANT_PUBLIC_HOST", "localhost")
    port = int(os.getenv("QDRANT_PUBLIC_PORT", os.getenv("QDRANT_PORT", "6333")))
    return f"http://{host}:{port}/dashboard"


def _qdrant_info() -> QdrantInfoResponse:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    url = _qdrant_public_url()
    collections: list[str] = []
    reachable = False
    try:
        store = VectorStore(host=host, port=port)
        collections = [c.name for c in store.client.get_collections().collections]
        reachable = True
    except Exception:
        reachable = False

    return QdrantInfoResponse(
        host=host,
        port=port,
        url=url,
        reachable=reachable,
        active_collection=COLLECTION_NAME,
        collections=collections,
    )


def _list_doc_modules() -> list[DocModule]:
    if not MODULES_DIR.exists() or not MODULES_DIR.is_dir():
        return []

    source_by_doc = _extract_source_paths_by_doc_name()
    modules: list[DocModule] = []
    for path in sorted(MODULES_DIR.glob("*.md"), key=lambda p: p.name.lower()):
        modules.append(
            DocModule(
                name=path.name,
                path=str(path.relative_to(DOCS_OUTPUT_DIR)),
                source_path=source_by_doc.get(path.name),
            )
        )
    return modules


def _list_global_docs() -> list[DocModule]:
    docs: list[DocModule] = []
    for path in [README_PATH, INDEX_PATH]:
        if path.exists() and path.is_file():
            docs.append(
                DocModule(
                    name=path.name,
                    path=str(path.relative_to(DOCS_OUTPUT_DIR)),
                    kind="global",
                )
            )
    return docs


def _normalize_path(raw_path: str) -> str:
    return raw_path.replace("\\", "/").lower()


def _extract_doc_links_from_index() -> dict[str, str]:
    if not INDEX_PATH.exists() or not INDEX_PATH.is_file():
        return {}

    mapping: dict[str, str] = {}
    content = INDEX_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*\[doc\]\(modules/([^\)]+)\)")
    for match in pattern.finditer(content):
        source_path = _normalize_path(match.group(1))
        doc_name = match.group(2)
        mapping[source_path] = doc_name
    return mapping


def _extract_source_paths_by_doc_name() -> dict[str, str]:
    if not INDEX_PATH.exists() or not INDEX_PATH.is_file():
        return {}

    mapping: dict[str, str] = {}
    content = INDEX_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*\[doc\]\(modules/([^\)]+)\)")
    for match in pattern.finditer(content):
        source_path = match.group(1).replace("\\", "/")
        doc_name = match.group(2)
        mapping[doc_name] = source_path
    return mapping


def _safe_module_path(module_name: str) -> Path:
    normalized_name = Path(module_name).name
    if normalized_name != module_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid module name.",
        )

    if not normalized_name.endswith(".md"):
        normalized_name = f"{normalized_name}.md"

    module_path = MODULES_DIR / normalized_name
    if not module_path.exists() or not module_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documentation module not found.",
        )

    return module_path


def _safe_doc_path(doc_name: str) -> Path:
    normalized_name = Path(doc_name).name
    if normalized_name != doc_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document name.",
        )

    if not normalized_name.endswith(".md"):
        normalized_name = f"{normalized_name}.md"

    if normalized_name in {README_PATH.name, INDEX_PATH.name}:
        target = DOCS_OUTPUT_DIR / normalized_name
    else:
        target = MODULES_DIR / normalized_name

    if not target.exists() or not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documentation file not found.",
        )

    return target


def _build_snippet(content: str, query: str, window: int = 120) -> str:
    lowered = content.lower()
    index = lowered.find(query.lower())
    if index < 0:
        snippet = content[: window * 2]
    else:
        start = max(index - window, 0)
        end = min(index + len(query) + window, len(content))
        snippet = content[start:end]
    return " ".join(snippet.split())


def _search_docs(query: str) -> list[DocsSearchResult]:
    query = query.strip()
    if not query:
        return []

    results: list[DocsSearchResult] = []
    source_by_doc = _extract_source_paths_by_doc_name()
    for doc in [*_list_global_docs(), *_list_doc_modules()]:
        path = _safe_doc_path(doc.name)
        content = path.read_text(encoding="utf-8")
        if query.lower() in content.lower() or query.lower() in doc.name.lower():
            results.append(
                DocsSearchResult(
                    name=doc.name,
                    path=doc.path,
                    kind=doc.kind,
                    snippet=_build_snippet(content, query),
                    source_path=source_by_doc.get(doc.name),
                )
            )
    return results


def _read_graph() -> GraphResponse:
    if not GRAPH_JSON_PATH.exists() or not GRAPH_JSON_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Graph file not found.",
        )

    try:
        payload = json.loads(GRAPH_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Graph file is invalid JSON.",
        ) from exc

    nodes = payload.get("nodes", [])
    edges = payload.get("edges", payload.get("links", []))

    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Graph payload format is invalid.",
        )

    return GraphResponse(nodes=nodes, edges=edges)


def _related_docs(module_name: str) -> list[DocModule]:
    graph = _read_graph()
    mapping = _extract_doc_links_from_index()
    reverse_mapping = {doc_name: src for src, doc_name in mapping.items()}

    if module_name not in reverse_mapping:
        return []

    raw_source = reverse_mapping[module_name]
    module_node = next(
        (
            node
            for node in graph.nodes
            if node.get("type") == "module"
            and _normalize_path(str(node.get("label", ""))) == raw_source
        ),
        None,
    )
    if not module_node:
        return []

    module_id = str(module_node.get("id", ""))
    neighbor_module_labels: set[str] = set()
    for edge in graph.edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source == module_id or target == module_id:
            other_id = target if source == module_id else source
            other_node = next(
                (node for node in graph.nodes if str(node.get("id", "")) == other_id),
                None,
            )
            if other_node and other_node.get("type") == "module":
                neighbor_module_labels.add(
                    _normalize_path(str(other_node.get("label", "")))
                )

    related: list[DocModule] = []
    for raw in sorted(neighbor_module_labels):
        doc_name = mapping.get(raw)
        if doc_name:
            related.append(
                DocModule(
                    name=doc_name,
                    path=f"modules/{doc_name}",
                    kind="module",
                    source_path=raw,
                )
            )
    return related


def create_app() -> FastAPI:
    app = FastAPI(title="CodeNavigator API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)

    @app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/api/docs", response_model=DocsListResponse, status_code=status.HTTP_200_OK
    )
    async def list_docs() -> DocsListResponse:
        globals_docs = _list_global_docs()
        modules = _list_doc_modules()
        return DocsListResponse(documents=[*globals_docs, *modules], modules=modules)

    @app.get(
        "/api/docs/search",
        response_model=DocsSearchResponse,
        status_code=status.HTTP_200_OK,
    )
    async def search_docs(q: str) -> DocsSearchResponse:
        return DocsSearchResponse(query=q, results=_search_docs(q))

    @app.get(
        "/api/docs/related/{module_name}",
        response_model=RelatedDocsResponse,
        status_code=status.HTTP_200_OK,
    )
    async def related_docs(module_name: str) -> RelatedDocsResponse:
        return RelatedDocsResponse(
            module_name=module_name,
            related=_related_docs(module_name),
        )

    @app.get(
        "/api/docs/{module_name}",
        response_model=DocContentResponse,
        status_code=status.HTTP_200_OK,
    )
    async def get_doc(module_name: str) -> DocContentResponse:
        module_path = _safe_doc_path(module_name)
        content = module_path.read_text(encoding="utf-8")
        return DocContentResponse(content=content)

    @app.get("/api/graph", response_model=GraphResponse, status_code=status.HTTP_200_OK)
    async def get_graph() -> GraphResponse:
        return _read_graph()

    @app.post(
        "/api/pipeline/start",
        response_model=PipelineStartResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_pipeline(request: PipelineRunRequest) -> PipelineStartResponse:
        with PIPELINE_LOCK:
            if PIPELINE_STATE["status"] in {"running", "queued", "cancelling"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A pipeline run is already in progress.",
                )
            job_id = str(uuid.uuid4())
            PIPELINE_STATE["job_id"] = job_id
            PIPELINE_STATE["status"] = "queued"
            PIPELINE_CANCEL_EVENT.clear()

        worker = threading.Thread(
            target=_run_pipeline_job,
            args=(job_id, request),
            daemon=True,
        )
        worker.start()

        return PipelineStartResponse(job_id=job_id, status="queued")

    @app.get(
        "/api/pipeline/status",
        response_model=PipelineStatusResponse,
        status_code=status.HTTP_200_OK,
    )
    async def pipeline_status() -> PipelineStatusResponse:
        return _pipeline_snapshot()

    @app.post(
        "/api/pipeline/reset",
        response_model=PipelineStatusResponse,
        status_code=status.HTTP_200_OK,
    )
    async def reset_pipeline_status() -> PipelineStatusResponse:
        with PIPELINE_LOCK:
            if PIPELINE_STATE["status"] in {"running", "queued", "cancelling"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot reset while pipeline is running.",
                )
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
        return _pipeline_snapshot()

    @app.post(
        "/api/pipeline/cancel",
        response_model=PipelineStatusResponse,
        status_code=status.HTTP_200_OK,
    )
    async def cancel_pipeline() -> PipelineStatusResponse:
        with PIPELINE_LOCK:
            if PIPELINE_STATE["status"] not in {"running", "queued", "cancelling"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No running pipeline to cancel.",
                )
            PIPELINE_CANCEL_EVENT.set()
            PIPELINE_STATE["status"] = "cancelling"

        _append_pipeline_event(
            stage="cancelling",
            message="Cancellation requested",
            progress=float(PIPELINE_STATE.get("progress", 0.0)),
        )
        return _pipeline_snapshot()

    @app.get(
        "/api/qdrant/info",
        response_model=QdrantInfoResponse,
        status_code=status.HTTP_200_OK,
    )
    async def qdrant_info() -> QdrantInfoResponse:
        return _qdrant_info()

    @app.post(
        "/api/qdrant/open",
        response_model=QdrantOpenResponse,
        status_code=status.HTTP_200_OK,
    )
    async def qdrant_open() -> QdrantOpenResponse:
        url = _qdrant_public_url()
        return QdrantOpenResponse(status="ok", url=url)

    return app


app = create_app()
