import json
import time
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from src.rag.chatbot import CodeNavigatorChatbot

from rag_evaluation.src.models import ChatbotRun, DatasetItem, RetrievedChunk


def load_dataset(path):
    dataset = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        dataset.append(
            DatasetItem(
                id=row["id"],
                question=row["question"],
                expected_answer=row["expected_answer"],
                expected_chunks=row.get("expected_chunks", []),
                type=row.get("type", "unknown"),
                difficulty=row.get("difficulty", "unknown"),
                module=row.get("module", "unknown"),
                dataset_version=row.get("dataset_version", "unknown"),
            )
        )
    return dataset


def build_chatbot(
    graph_json_path=None,
    top_k=6,
    model="mistral-large-latest",
    qdrant_host="localhost",
    qdrant_port=6333,
    qdrant_collection="CodeNavigatorChunks",
):
    return CodeNavigatorChatbot(
        graph_json_path=graph_json_path,
        top_k=top_k,
        model=model,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        qdrant_collection=qdrant_collection,
    )


def run_chatbot_case(bot, item):
    bot.reset()
    response = bot.chat(item.question)

    chunks = []
    for source in response.sources:
        chunks.append(
            RetrievedChunk(
                chunk_id=source.chunk_id,
                source_file=source.source_file,
                chunk_type=source.chunk_type,
                score=float(source.score),
                content_excerpt=source.content[:800],
            )
        )

    tokens = response.debug.get("tokens", {})
    return ChatbotRun(
        id=item.id,
        question=item.question,
        expected_answer=item.expected_answer,
        expected_chunks=list(item.expected_chunks),
        answer=response.answer,
        retrieved_chunks=chunks,
        duration_ms=float(response.debug.get("duration_ms", 0.0)),
        tokens={
            "prompt": tokens.get("prompt"),
            "completion": tokens.get("completion"),
            "total": tokens.get("total"),
        },
        model=str(response.debug.get("model", "unknown")),
        error=None,
    )


def run_dataset(
    dataset,
    graph_json_path=None,
    top_k=6,
    model="mistral-large-latest",
    qdrant_host="localhost",
    qdrant_port=6333,
    qdrant_collection="CodeNavigatorChunks",
):
    bot = build_chatbot(
        graph_json_path=graph_json_path,
        top_k=top_k,
        model=model,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        qdrant_collection=qdrant_collection,
    )

    runs = []
    for item in dataset:
        attempts = 0
        delay = 3

        while True:
            try:
                runs.append(run_chatbot_case(bot, item))
                break
            except Exception as exc:
                message = str(exc)
                attempts += 1

                if attempts <= 2 and ("429" in message or "rate" in message.lower()):
                    time.sleep(delay)
                    delay = delay * 2
                    continue

                runs.append(
                    ChatbotRun(
                        id=item.id,
                        question=item.question,
                        expected_answer=item.expected_answer,
                        expected_chunks=list(item.expected_chunks),
                        answer="",
                        retrieved_chunks=[],
                        duration_ms=0.0,
                        tokens={"prompt": None, "completion": None, "total": None},
                        model=model,
                        error=message,
                    )
                )
                break

        time.sleep(2)
    return runs


def write_json(path, payload):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_jsonl(path, rows):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def case_to_dict(run):
    return {
        "id": run.id,
        "question": run.question,
        "expected_answer": run.expected_answer,
        "expected_chunks": run.expected_chunks,
        "answer": run.answer,
        "retrieved_chunks": [chunk.__dict__ for chunk in run.retrieved_chunks],
        "duration_ms": run.duration_ms,
        "tokens": run.tokens,
        "model": run.model,
        "error": run.error,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run the chatbot on a dataset")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--model", default="mistral-large-latest")
    parser.add_argument("--graph-json-path", default=None)
    parser.add_argument("--qdrant-host", default="localhost")
    parser.add_argument("--qdrant-port", type=int, default=6333)
    parser.add_argument("--qdrant-collection", default="CodeNavigatorChunks")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    runs = run_dataset(
        dataset,
        graph_json_path=args.graph_json_path,
        top_k=args.top_k,
        model=args.model,
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        qdrant_collection=args.qdrant_collection,
    )
    write_jsonl(args.output, (case_to_dict(run) for run in runs))


if __name__ == "__main__":
    main()
