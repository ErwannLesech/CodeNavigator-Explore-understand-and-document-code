import argparse
import sys
from datetime import datetime
from pathlib import Path
import logging

from rag_evaluation.src.chatbot_runner import (
    case_to_dict,
    load_dataset,
    run_dataset,
    write_json,
)
from rag_evaluation.src.metrics import (
    aggregate_metric_results,
    case_metrics_to_dict,
    compute_case_metrics,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _build_output_path(output):
    output_path = Path(output)
    if output_path.suffix:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    output_path.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return output_path / f"scorecard_{stamp}.json"


def run_evaluation(
    dataset_path,
    graph_json_path=None,
    top_k=6,
    model="mistral-large-latest",
    provider="mistral",
    qdrant_host="localhost",
    qdrant_port=6333,
    qdrant_collection="CodeNavigatorChunks",
):
    dataset = load_dataset(dataset_path)
    runs = run_dataset(
        dataset,
        graph_json_path=graph_json_path,
        top_k=top_k,
        model=model,
        provider=provider,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        qdrant_collection=qdrant_collection,
    )

    cases = []
    i = 0
    for item, run in zip(dataset, runs):
        logger.info(f"Computing metrics for case: {i+1}/{len(dataset)}")
        metrics = compute_case_metrics(item, run)
        row = case_to_dict(run)
        row["metrics"] = case_metrics_to_dict(metrics)
        cases.append(row)
        i += 1

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {"path": str(dataset_path), "count": len(dataset)},
        "run": {
            "top_k": top_k,
            "provider": provider,
            "model": model,
            "qdrant_host": qdrant_host,
            "qdrant_port": qdrant_port,
            "qdrant_collection": qdrant_collection,
            "graph_json_path": graph_json_path,
        },
        "summary": aggregate_metric_results(cases),
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run a simple RAG evaluation and export a scorecard JSON"
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--graph-json-path", default=None)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--provider", choices=["mistral", "ollama"], default="mistral")
    parser.add_argument("--model", default="mistral-large-latest")
    parser.add_argument("--qdrant-host", default="localhost")
    parser.add_argument("--qdrant-port", type=int, default=6333)
    parser.add_argument("--qdrant-collection", default="CodeNavigatorChunks")
    args = parser.parse_args()

    scorecard = run_evaluation(
        args.dataset,
        graph_json_path=args.graph_json_path,
        top_k=args.top_k,
        model=args.model,
        provider=args.provider,
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        qdrant_collection=args.qdrant_collection,
    )
    write_json(_build_output_path(args.output), scorecard)


if __name__ == "__main__":
    main()
