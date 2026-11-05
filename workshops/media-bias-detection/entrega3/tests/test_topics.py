import numpy as np
import pandas as pd
import pytest

from core import fold, tokenize
from topics import (
    balanced_sample,
    block_bootstrap_diff,
    match_topics,
    relative_series,
    stop_words,
)


def _frame(sizes):
    rows = []
    for (medio, gob), n in sizes.items():
        rows += [{"source_id": medio, "government_id": gob, "title": f"t{i}"} for i in range(n)]
    return pd.DataFrame(rows)


def test_muestra_balanceada_tiene_el_mismo_tamano_por_celda():
    frame = _frame({("a", "duque"): 50, ("a", "petro"): 80, ("b", "duque"): 30, ("b", "petro"): 99})
    idx = balanced_sample(frame, 20, seed=42)
    assert frame.loc[idx].groupby(["source_id", "government_id"]).size().eq(20).all()


def test_muestra_balanceada_es_reproducible():
    frame = _frame({("a", "duque"): 50, ("a", "petro"): 80})
    assert balanced_sample(frame, 10, seed=42).equals(balanced_sample(frame, 10, seed=42))


def test_muestra_balanceada_falla_si_una_celda_no_alcanza():
    frame = _frame({("a", "duque"): 5, ("a", "petro"): 80})
    with pytest.raises(ValueError):
        balanced_sample(frame, 10, seed=42)


def test_stopwords_de_dominio_usan_el_mismo_plegado_de_tildes():
    stops = stop_words()
    assert "miercoles" in stops and "segun" in stops
    assert tokenize("Según el Gobierno, el miércoles aprobó la reforma", stops) == ["gobierno", "aprobo", "reforma"]


def test_stopwords_conservan_actores_y_lugares():
    stops = stop_words()
    assert not {"petro", "duque", "bogota", "fiscalia", "gobierno", "estados", "estado"} & stops


def test_emparejamiento_recupera_una_permutacion():
    rng = np.random.default_rng(0)
    topics = rng.dirichlet(np.ones(50), size=6)
    perm = np.array([3, 0, 5, 1, 4, 2])
    matched, sims = match_topics(topics, topics[perm])
    assert (perm[matched] == np.arange(6)).all()
    assert np.allclose(sims, 1)


def test_serie_relativa_suma_cero_entre_medios():
    shares = pd.DataFrame(np.random.default_rng(1).random((12, 5)), columns=list("abcde"))
    rel = relative_series(shares)
    assert np.allclose(rel.sum(axis=1), 0)
    expected = shares["a"] - shares[["b", "c", "d", "e"]].mean(axis=1)
    assert np.allclose(rel["a"], expected)


def test_bootstrap_detecta_un_cambio_claro_y_no_uno_nulo():
    rng = np.random.default_rng(2)
    before = 0.10 + rng.normal(0, 0.005, 48)
    after = 0.15 + rng.normal(0, 0.005, 48)
    claro = block_bootstrap_diff(after, before)
    assert claro["low"] > 0 and claro["p"] < 0.01
    assert claro["delta"] == pytest.approx(after.mean() - before.mean())
    nulo = block_bootstrap_diff(before + rng.normal(0, 0.005, 48), before)
    assert nulo["low"] < 0 < nulo["high"]


def test_clasificacion_de_robustez_por_jaccard():
    from topics import robustness_class

    assert robustness_class(0.82) == "robusto"
    assert robustness_class(0.5) == "robusto"
    assert robustness_class(0.34) == "parcial"
    assert robustness_class(0.29) == "inestable"
