"""Valores exactos de las métricas sobre 5 casos sintéticos (no datos reales)."""
import math

import pytest

from scripts import metricas_rag as m

# 5 preguntas: recuperados en orden, relevantes, ¿debía abstenerse?, ¿se abstuvo?
CASOS = [
    (["a", "b", "c", "d", "e"], {"a"}, False, False),       # relevante en rango 1
    (["x", "a", "y", "z", "w"], {"a"}, False, True),        # rango 2; abstención indebida (FP)
    (["x", "y", "z", "w", "v"], {"a"}, False, False),       # relevante no recuperado
    (["a", "x", "b", "y", "z"], {"a", "b"}, False, False),  # dos relevantes, rangos 1 y 3
    (["x", "y", "z", "w", "v"], set(), True, True),          # no respondible; abstención correcta (VP)
]
L3 = 1 / math.log2(3)  # ganancia descontada en el rango 2


def test_recall_por_pregunta_y_promedio():
    assert [m.recall_at_k(r, rel, 1) for r, rel, *_ in CASOS] == [1.0, 0.0, 0.0, 0.5, None]
    assert [m.recall_at_k(r, rel, 3) for r, rel, *_ in CASOS] == [1.0, 1.0, 0.0, 1.0, None]
    assert m.mean_defined(m.recall_at_k(r, rel, 5) for r, rel, *_ in CASOS) == 0.75


def test_mrr():
    rr = [m.reciprocal_rank(r, rel) for r, rel, *_ in CASOS]
    assert rr == [1.0, 0.5, 0.0, 1.0, None]
    assert m.mean_defined(rr) == 0.625
    assert m.reciprocal_rank(["x", "a"], {"a"}, k=1) == 0.0


def test_ndcg_valores_exactos():
    nd = [m.ndcg_at_k(r, rel, 5) for r, rel, *_ in CASOS]
    assert nd[0] == 1.0 and nd[2] == 0.0 and nd[4] is None
    assert nd[1] == pytest.approx(L3)                       # 0,630930
    assert nd[3] == pytest.approx((1 + 0.5) / (1 + L3))     # 0,919721
    assert m.mean_defined(nd) == pytest.approx((1 + L3 + 0 + 1.5 / (1 + L3)) / 4)  # 0,637663


def test_abstencion_precision_y_recall():
    res = m.abstention_precision_recall([c[2] for c in CASOS], [c[3] for c in CASOS])
    assert (res["vp"], res["fp"], res["fn"]) == (1, 1, 0)
    assert res["precision"] == 0.5 and res["recall"] == 1.0
    assert m.abstention_precision_recall([False], [False])["precision"] is None


def test_resumen_y_casos_limite():
    s = m.retrieval_summary([(r, rel) for r, rel, *_ in CASOS], ks=(1, 5))
    assert s["preguntas"] == 5 and s["evaluadas"] == 4
    assert s["recall@1"] == 0.375 and s["recall@5"] == 0.75 and s["mrr"] == 0.625  # (1+0+0+0,5)/4
    assert m.unique_in_order(["d1", "d2", "d1", "d3"]) == ["d1", "d2", "d3"]
    with pytest.raises(ValueError):
        m.recall_at_k(["a"], {"a"}, 0)
