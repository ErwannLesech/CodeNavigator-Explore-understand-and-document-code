import re
from collections import Counter

from rag_evaluation.src.models import MetricResult


def _tokens(text):
    return re.findall(r"[\wÀ-ÿ]+", text.lower())


def _chunk_ids(run):
    return [chunk.chunk_id for chunk in run.retrieved_chunks]


def hit_rate_at_k(item, run):
    found = set(_chunk_ids(run)) & set(item.expected_chunks)
    return MetricResult(1.0 if found else 0.0, {"matched_chunks": sorted(found)})


def mrr(item, run):
    for index, chunk_id in enumerate(_chunk_ids(run), start=1):
        if chunk_id in item.expected_chunks:
            return MetricResult(1.0 / index, {"rank": index})
    return MetricResult(0.0, {"rank": None})


def answer_overlap(item, run):
    expected = Counter(_tokens(item.expected_answer))
    answer = Counter(_tokens(run.answer))
    if not expected or not answer:
        return MetricResult(0.0, {"common_tokens": 0})

    common = sum((expected & answer).values())
    score = common / max(len(expected), len(answer))
    return MetricResult(score, {"common_tokens": common})


def retrieval_score(item, run):
    hit = hit_rate_at_k(item, run).value
    rank = mrr(item, run).value
    return MetricResult((0.6 * hit) + (0.4 * rank), {"hit_rate": hit, "mrr": rank})


def generation_score(item, run):
    overlap = answer_overlap(item, run).value
    return MetricResult(overlap, {"answer_overlap": overlap})


def composite_score(item, run):
    retrieval = retrieval_score(item, run).value
    generation = generation_score(item, run).value
    return MetricResult(
        (retrieval + generation) / 2, {"retrieval": retrieval, "generation": generation}
    )


def compute_case_metrics(item, run):
    return {
        "hit_rate_at_k": hit_rate_at_k(item, run),
        "mrr": mrr(item, run),
        "answer_overlap": answer_overlap(item, run),
        "retrieval_score": retrieval_score(item, run),
        "generation_score": generation_score(item, run),
        "composite_score": composite_score(item, run),
    }


def aggregate_metric_results(per_case):
    names = [
        "hit_rate_at_k",
        "mrr",
        "answer_overlap",
        "retrieval_score",
        "generation_score",
        "composite_score",
    ]
    summary = {}
    for name in names:
        values = [case["metrics"][name]["value"] for case in per_case]
        summary[name] = sum(values) / len(values) if values else 0.0
    return summary


def case_metrics_to_dict(metrics):
    return {
        name: {"value": result.value, "details": result.details}
        for name, result in metrics.items()
    }
