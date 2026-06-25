from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache

import evaluate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types (identiques à rag_evaluation.src.models pour rester compatible)
# ---------------------------------------------------------------------------


@dataclass
class MetricResult:
    value: float
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Chargement paresseux des métriques evaluate (une seule fois par process)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _load_rouge():
    return evaluate.load("rouge")


@lru_cache(maxsize=None)
def _load_bleu():
    return evaluate.load("bleu")


@lru_cache(maxsize=None)
def _load_bertscore():
    return evaluate.load("bertscore")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk_ids(run) -> list[str]:
    return [chunk.chunk_id for chunk in run.retrieved_chunks]


# ---------------------------------------------------------------------------
# Métriques de RETRIEVAL
# ---------------------------------------------------------------------------


def hit_rate_at_k(item, run) -> MetricResult:
    """Au moins un chunk attendu est-il dans les résultats récupérés ?"""
    found = set(_chunk_ids(run)) & set(item.expected_chunks)
    return MetricResult(
        value=1.0 if found else 0.0,
        details={"matched_chunks": sorted(found)},
    )


def mrr(item, run) -> MetricResult:
    """Mean Reciprocal Rank : rang du premier chunk pertinent."""
    for rank, chunk_id in enumerate(_chunk_ids(run), start=1):
        if chunk_id in item.expected_chunks:
            return MetricResult(value=1.0 / rank, details={"rank": rank})
    return MetricResult(value=0.0, details={"rank": None})


def context_recall(item, run) -> MetricResult:
    """Part des chunks récupérés qui sont effectivement pertinents."""
    retrieved = set(_chunk_ids(run))
    if not retrieved:
        return MetricResult(value=0.0, details={"useful": 0, "retrieved": 0})

    useful = retrieved & set(item.expected_chunks)
    return MetricResult(
        value=len(useful) / len(retrieved),
        details={"useful": len(useful), "retrieved": len(retrieved)},
    )


def retrieval_score(item, run) -> MetricResult:
    """Score composite retrieval (hit 40% + MRR 30% + recall 30%)."""
    hit = hit_rate_at_k(item, run).value
    rank = mrr(item, run).value
    recall = context_recall(item, run).value
    return MetricResult(
        value=0.4 * hit + 0.3 * rank + 0.3 * recall,
        details={"hit_rate": hit, "mrr": rank, "context_recall": recall},
    )


# ---------------------------------------------------------------------------
# Métriques de GENERATION — via HuggingFace evaluate
# ---------------------------------------------------------------------------


def rouge_scores(item, run) -> MetricResult:
    """
    ROUGE-1 / ROUGE-2 / ROUGE-L / ROUGE-Lsum.

    ROUGE-L    : LCS (plus longue sous-séquence commune) sur la phrase entière.
                 Adapté aux réponses courtes, une seule phrase de référence.

    ROUGE-Lsum : LCS calculée ligne par ligne puis agrégée par somme.
                 Conçu pour les textes multi-phrases / résumés.
                 Sur une paire unique (cas par cas), use_aggregator=False
                 retourne la valeur brute non moyennée — c'est ce qu'on veut.

    Valeur principale exposée : rougeL (le plus pertinent pour le QA phrase courte).
    rougeLsum disponible dans details pour les réponses longues / multi-paragraphes.
    """
    # use_aggregator=False → liste de scores par paire, pas de moyenne corpus
    result = _load_rouge().compute(
        predictions=[run.answer],
        references=[item.expected_answer],
        use_aggregator=False,
    )
    # Sur une paire unique, chaque valeur est une liste de 1 élément
    rouge1 = result["rouge1"][0]
    rouge2 = result["rouge2"][0]
    rougeL = result["rougeL"][0]
    rougeLsum = result["rougeLsum"][0]

    return MetricResult(
        value=rougeL,
        details={
            "rouge1": rouge1,
            "rouge2": rouge2,
            "rougeL": rougeL,
            "rougeLsum": rougeLsum,
        },
    )


def bleu_score(item, run) -> MetricResult:
    """
    BLEU (precision-oriented, chevauchement de n-grammes).
    ⚠️  Pénalise les paraphrases correctes — à interpréter avec recul en QA.
    """
    try:
        result = _load_bleu().compute(
            predictions=[run.answer],
            references=[[item.expected_answer]],  # BLEU attend une liste de références
        )
        return MetricResult(
            value=result["bleu"],
            details={
                "bleu": result["bleu"],
                "precisions": result["precisions"],  # par n-gramme 1..4
                "brevity_penalty": result["brevity_penalty"],
            },
        )
    except Exception as exc:
        logger.warning("bleu_score failed: %s", exc)
        return MetricResult(value=0.0, details={"error": str(exc)})


def bert_f1(item, run, lang: str = "fr") -> MetricResult:
    """
    BERTScore F1  (similarité sémantique via embeddings contextuels).
    Robuste aux synonymes et reformulations — le plus pertinent pour le QA.
    rescale_with_baseline=True  → scores normalisés, comparables entre modèles.
    """
    if not item.expected_answer.strip() or not run.answer.strip():
        return MetricResult(
            value=0.0,
            details={"precision": 0.0, "recall": 0.0, "available": True},
        )

    try:
        result = _load_bertscore().compute(
            predictions=[run.answer],
            references=[item.expected_answer],
            lang=lang,
            rescale_with_baseline=True,
        )
        p = result["precision"][0]
        r = result["recall"][0]
        f1 = result["f1"][0]
        return MetricResult(
            value=f1,
            details={
                "precision": p,
                "recall": r,
                "model": result.get("hashcode", "unknown"),
                "available": True,
            },
        )
    except Exception as exc:
        logger.warning("bert_f1 failed: %s", exc)
        return MetricResult(
            value=0.0,
            details={"available": False, "error": str(exc)},
        )


def generation_score(item, run) -> MetricResult:
    """
    Score composite génération.
    - Si BERTScore disponible : moyenne(ROUGE-L, BERTScore F1)
    - Sinon : ROUGE-L seul
    """
    rouge = rouge_scores(item, run)
    bert = bert_f1(item, run)

    scores = [rouge.value]
    details = {"rougeL": rouge.value}

    if bert.details.get("available"):
        scores.append(bert.value)
        details.update(
            {
                "bert_f1": bert.value,
                "bert_precision": bert.details["precision"],
                "bert_recall": bert.details["recall"],
                "bert_model": bert.details.get("model"),
            }
        )
    else:
        details["bert_unavailable"] = bert.details.get("error", "unknown")

    return MetricResult(value=sum(scores) / len(scores), details=details)


# ---------------------------------------------------------------------------
# Métriques opérationnelles
# ---------------------------------------------------------------------------


def output_tokens(item, run) -> MetricResult:
    completion = run.tokens.get("completion")
    return MetricResult(
        value=float(completion) if completion is not None else 0.0,
        details={"completion_tokens": completion},
    )


def response_time_ms(item, run) -> MetricResult:
    value = float(run.duration_ms) if run.duration_ms is not None else 0.0
    return MetricResult(value=value, details={"duration_ms": value})


# ---------------------------------------------------------------------------
# Score composite global
# ---------------------------------------------------------------------------


def composite_score(item, run) -> MetricResult:
    retrieval = retrieval_score(item, run).value
    generation = generation_score(item, run).value
    return MetricResult(
        value=(retrieval + generation) / 2,
        details={"retrieval": retrieval, "generation": generation},
    )


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------


def compute_case_metrics(item, run) -> dict[str, MetricResult]:
    return {
        # --- retrieval ---
        "hit_rate_at_k": hit_rate_at_k(item, run),
        "mrr": mrr(item, run),
        "context_recall": context_recall(item, run),
        "retrieval_score": retrieval_score(item, run),
        # --- generation ---
        "rouge": rouge_scores(item, run),
        "bleu": bleu_score(item, run),
        "bert_f1": bert_f1(item, run),
        "generation_score": generation_score(item, run),
        # --- opérationnel ---
        "output_tokens": output_tokens(item, run),
        "response_time_ms": response_time_ms(item, run),
        # --- composite ---
        "composite_score": composite_score(item, run),
    }


def case_metrics_to_dict(metrics: dict[str, MetricResult]) -> dict:
    return {
        name: {"value": result.value, "details": result.details}
        for name, result in metrics.items()
    }


def aggregate_metric_results(per_case: list[dict]) -> dict:
    """
    Moyenne de chaque métrique sur tous les cas.
    Pour ROUGE, inclut aussi les détails (rouge1, rouge2, rougeL, rougeLsum).
    Pour BERT F1, inclut aussi les détails (precision, recall, model).
    """
    names = [
        "hit_rate_at_k",
        "mrr",
        "context_recall",
        "retrieval_score",
        "rouge",
        "bleu",
        "bert_f1",
        "generation_score",
        "output_tokens",
        "response_time_ms",
        "composite_score",
    ]
    result = {}

    # Agrégation des métriques principales
    for name in names:
        if per_case:
            result[name] = sum(
                case["metrics"][name]["value"] for case in per_case
            ) / len(per_case)
        else:
            result[name] = 0.0

    # Détails supplémentaires pour ROUGE
    rouge_details = {
        "rouge1": 0.0,
        "rouge2": 0.0,
        "rougeL": 0.0,
        "rougeLsum": 0.0,
    }
    if per_case:
        for key in rouge_details.keys():
            rouge_details[key] = sum(
                case["metrics"]["rouge"]["details"].get(key, 0.0) for case in per_case
            ) / len(per_case)
    result["rouge_details"] = rouge_details

    # Détails supplémentaires pour BERT F1
    bert_details = {
        "precision": 0.0,
        "recall": 0.0,
        "model": "unknown",
    }
    if per_case:
        # Moyenne des precisions/recalls
        bert_cases = [
            case["metrics"]["bert_f1"]["details"]
            for case in per_case
            if case["metrics"]["bert_f1"]["details"].get("available")
        ]
        if bert_cases:
            bert_details["precision"] = sum(b["precision"] for b in bert_cases) / len(
                bert_cases
            )
            bert_details["recall"] = sum(b["recall"] for b in bert_cases) / len(
                bert_cases
            )
            # Model du premier cas disponible
            bert_details["model"] = bert_cases[0].get("model", "unknown")
    result["bert_f1_details"] = bert_details

    return result
