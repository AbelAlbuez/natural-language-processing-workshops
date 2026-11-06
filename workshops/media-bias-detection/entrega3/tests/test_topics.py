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


def test_emparejamiento_con_menos_topicos_deja_sin_pareja():
    rng = np.random.default_rng(3)
    base = rng.dirichlet(np.ones(40), size=5)
    matched, sims = match_topics(base, base[[4, 1, 0]])
    assert sorted(matched[matched >= 0].tolist()) == [0, 1, 2]
    assert (matched == -1).sum() == 2 and (sims[matched == -1] == 0).all()
    assert matched[4] == 0 and matched[1] == 1 and matched[0] == 2


def test_pesos_por_seccion_igualan_la_mezcla_entre_gobiernos():
    from topics import section_weights

    # Duque: 80 % deportes; Petro: 20 % deportes. Mezcla común: 50 %.
    meta = pd.DataFrame({
        "source_id": ["a"] * 200,
        "government_id": ["duque"] * 100 + ["petro"] * 100,
        "section": ["deportes"] * 80 + ["politica"] * 20 + ["deportes"] * 20 + ["politica"] * 80,
    })
    w = section_weights(meta)
    meta["w"] = w
    for gov in ("duque", "petro"):
        g = meta[meta["government_id"] == gov]
        assert g.loc[g["section"] == "deportes", "w"].sum() / g["w"].sum() == pytest.approx(0.5)


def test_secciones_raras_se_agrupan():
    from topics import section_weights

    meta = pd.DataFrame({
        "source_id": ["a"] * 1000, "government_id": ["duque"] * 500 + ["petro"] * 500,
        "section": ["x"] * 499 + ["rara"] + ["x"] * 500,
    })
    w = section_weights(meta)
    assert np.isfinite(w).all()


def test_medias_mensuales_ponderadas():
    from topics import monthly_shares

    meta = pd.DataFrame({"government_id": ["duque"] * 2, "month": ["2020-01"] * 2, "source_id": ["a"] * 2})
    theta = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert monthly_shares(theta, meta)["t0"].iloc[0] == pytest.approx(0.5)
    assert monthly_shares(theta, meta, np.array([3.0, 1.0]))["t0"].iloc[0] == pytest.approx(0.75)


def test_piso_del_p_valor_permite_significancia_tras_holm():
    """Con 125 pruebas, el p mínimo bootstrap × 125 debe quedar bajo 0,05."""
    from topics import BOOTSTRAP_REPS

    assert 125 / BOOTSTRAP_REPS < 0.05
