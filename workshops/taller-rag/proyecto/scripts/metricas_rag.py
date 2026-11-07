"""Métricas de evaluación del RAG: recuperación (Recall@k, MRR, nDCG@k) y abstención.

Relevancia binaria: un identificador recuperado es relevante si está en el conjunto de
relevantes de la pregunta. Los identificadores pueden ser de documento o de chunk, pero
recuperados y relevantes deben estar al mismo nivel. Para pasar de chunks a documentos
use ``unique_in_order`` sobre los document_id recuperados (conserva el primer rango).

Las preguntas sin relevantes (no respondibles) no tienen métricas de recuperación
(devuelven None y se excluyen de los promedios); entran solo en las de abstención.
Este módulo no lee el gold standard ni consulta servicios.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def unique_in_order(ids: Iterable[str]) -> list[str]:
    """Elimina repetidos conservando la primera aparición (p. ej., varios chunks de un documento)."""
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _check_k(k: int) -> None:
    if k < 1:
        raise ValueError("k debe ser >= 1")


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    """|relevantes ∩ top-k| / |relevantes|. None si no hay relevantes."""
    _check_k(k)
    relevant = set(relevant)
    if not relevant:
        return None
    return len(relevant & set(retrieved[:k])) / len(relevant)


def reciprocal_rank(retrieved: Sequence[str], relevant: Iterable[str], k: int | None = None) -> float | None:
    """1 / rango del primer relevante (0 si no aparece en los primeros k). None si no hay relevantes."""
    relevant = set(relevant)
    if not relevant:
        return None
    ranked = retrieved if k is None else retrieved[:k]
    for rank, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    """nDCG@k con ganancia binaria: DCG = Σ rel_i / log2(i + 1), i desde 1."""
    _check_k(k)
    relevant = set(relevant)
    if not relevant:
        return None
    dcg = sum(1.0 / math.log2(i + 1) for i, item in enumerate(retrieved[:k], start=1) if item in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal


def mean_defined(values: Iterable[float | None]) -> float | None:
    """Promedio ignorando None. None si no queda ningún valor."""
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def abstention_precision_recall(should_abstain: Sequence[bool], abstained: Sequence[bool]) -> dict:
    """Precisión y recall de la abstención (clase positiva: abstenerse).

    precisión = VP / (VP + FP): de las abstenciones, cuántas eran correctas.
    recall    = VP / (VP + FN): de las preguntas que debían abstenerse, cuántas lo hicieron.
    Cada valor es None si su denominador es 0.
    """
    if len(should_abstain) != len(abstained):
        raise ValueError("should_abstain y abstained deben tener la misma longitud")
    tp = sum(1 for s, a in zip(should_abstain, abstained) if s and a)
    fp = sum(1 for s, a in zip(should_abstain, abstained) if not s and a)
    fn = sum(1 for s, a in zip(should_abstain, abstained) if s and not a)
    return {
        "vp": tp, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def retrieval_summary(runs: Sequence[tuple[Sequence[str], Iterable[str]]], ks=(1, 3, 5, 10)) -> dict:
    """Promedios por pregunta respondible. runs: [(recuperados_en_orden, relevantes), ...]."""
    runs = [(list(r), set(rel)) for r, rel in runs]
    out = {"preguntas": len(runs), "evaluadas": sum(1 for _, rel in runs if rel)}
    for k in ks:
        out[f"recall@{k}"] = mean_defined(recall_at_k(r, rel, k) for r, rel in runs)
    out["mrr"] = mean_defined(reciprocal_rank(r, rel) for r, rel in runs)
    out["ndcg@10"] = mean_defined(ndcg_at_k(r, rel, 10) for r, rel in runs)
    return out
