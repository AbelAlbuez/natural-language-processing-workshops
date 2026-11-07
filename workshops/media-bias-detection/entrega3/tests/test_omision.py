import numpy as np
import pandas as pd

from omision import (analyze, block_weights, eligible, monthly_counts, naive_eligible, near_present, relative,
                     shares)
from topics import relative_series

MEDIA5 = ["a", "b", "c", "d", "e"]


def test_denominador_no_depende_del_medio_evaluado():
    # Evento 0: exactamente 3 medios (a, b, c). Evento 1: 4 medios (a, b, c, d).
    pres = np.array([[1, 1, 1, 0, 0], [1, 1, 1, 1, 0]], dtype=bool)
    elig = eligible(pres, 3)
    # En el evento de 3 medios ninguno de los 3 puede «faltar»: no entran a su denominador…
    assert not elig[0, :3].any()
    # …y los ausentes sí entran (3 de los otros 4 están).
    assert elig[0, 3:].all()
    # Con 4 medios, cada presente tiene 3 de los otros: entra; e (ausente) también.
    assert elig[1].all()
    # El ingenuo mete a todos en los eventos con ≥3 medios.
    assert naive_eligible(pres, 3).all()


def test_condicionar_a_los_otros_corrige_el_sesgo_de_seleccion():
    # Presencias independientes: el medio 0 aparece con prob. 0,4 en cualquier evento.
    rng = np.random.default_rng(0)
    probs = np.array([0.4, 0.6, 0.6, 0.5, 0.3])
    pres = rng.random((200_000, 5)) < probs
    pres = pres[pres.sum(axis=1) >= 2]  # los eventos tienen al menos 2 medios
    cond = pres[eligible(pres, 3)[:, 0], 0].mean()
    naive = pres[naive_eligible(pres, 3)[:, 0], 0].mean()
    assert abs(cond - 0.4) < 0.01
    assert naive > 0.5  # el denominador ingenuo infla la participación


def test_relativo_suma_cero_y_coincide_con_topics():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(7, 5))
    rel = relative(x)
    assert np.allclose(rel.sum(axis=1), 0)
    ref = relative_series(pd.DataFrame(x, columns=MEDIA5)).to_numpy()
    assert np.allclose(rel, ref)


def test_pesos_de_bloques_conservan_el_numero_de_meses():
    w = block_weights(10, 500, 3, np.random.default_rng(0))
    assert w.shape == (500, 10)
    assert (w.sum(axis=1) == 10).all()


def test_conteos_y_participacion_por_tema():
    pres = np.array([[1, 1, 1, 1, 0], [1, 1, 1, 0, 1], [0, 1, 1, 1, 0]], dtype=bool)
    elig = eligible(pres, 3)
    months = np.array(["m1", "m1", "m2"])
    topics = np.array([0, 1, 1])
    den, num = monthly_counts(months, topics, pres, elig, ["m1", "m2"], 2)
    # Medio a: entra en los 3 eventos (siempre hay ≥3 de los otros), participa en 2.
    assert den[:, :, 0].sum() == 3 and num[:, :, 0].sum() == 2
    topic, general = shares(den.sum(0), num.sum(0))
    assert np.isclose(general[0], 2 / 3)
    assert np.isclose(topic[1, 0], 1 / 2)  # tema 1: eventos 1 (está) y 2 (falta)


def _synthetic(n_per_month=60, months=24, drop=None, seed=0):
    """Eventos sintéticos de dos gobiernos con 2 temas; `drop` = (medio, tema, gobierno, prob)
    baja la presencia de ese medio sólo en ese tema y gobierno."""
    rng = np.random.default_rng(seed)
    rows, pres = [], []
    base = np.array([0.8, 0.7, 0.6, 0.6, 0.4])
    for gov in ("duque", "petro"):
        for mo in range(months):
            for _ in range(n_per_month):
                t = int(rng.integers(0, 2))
                p = base.copy()
                if gov == "petro":
                    p[4] *= 0.5  # e publica menos en general con Petro: no debe ser omisión del tema
                if drop and drop[1] == t and drop[2] == gov:
                    p[drop[0]] = drop[3]
                pres.append(rng.random(5) < p)
                rows.append({"gobierno": gov, "mes": f"{gov}-{mo:02d}", "topic": t})
    pres = np.array(pres)
    keep = pres.sum(axis=1) >= 2
    return pres[keep], pd.DataFrame(rows)[keep].reset_index(drop=True)


def test_baja_general_del_medio_no_es_omision_del_tema():
    pres, meta = _synthetic()
    out = analyze(pres, eligible(pres, 3), meta, MEDIA5, 2, inferencia=[0, 1], repetitions=300)
    d = out["deltas"]
    # e baja en todos los temas: su participación cae, pero el Δ específico queda cerca de 0.
    gen = out["general"].set_index(["gobierno", "source_id"])["pct_general"]
    assert gen[("petro", "e")] < gen[("duque", "e")] - 10
    assert d.loc[d["source_id"] == "e", "delta_esp_pp"].abs().max() < 5
    assert np.allclose(d.groupby("topic")["delta_rel_pp"].sum(), 0, atol=1e-9)


def test_detecta_una_omision_especifica_plantada():
    # Con Petro, el medio b casi nunca cubre el tema 1.
    pres, meta = _synthetic(drop=(1, 1, "petro", 0.1))
    out = analyze(pres, eligible(pres, 3), meta, MEDIA5, 2, inferencia=[0, 1], repetitions=500)
    d = out["deltas"].set_index(["topic", "source_id"])
    assert d.loc[(1, "b"), "delta_rel_pp"] < -20
    assert d.loc[(1, "b"), "delta_rel_high_pp"] < 0
    assert d.loc[(1, "b"), "delta_rel_p_holm"] < 0.05
    # El tema 0 también se mueve para b (su general baja), con el signo contrario.
    assert d.loc[(0, "b"), "delta_esp_pp"] > 0


def test_casi_presente_toma_la_mejor_arista_con_el_nucleo():
    ev = pd.DataFrame({"event_id": [0, 0, 1], "article_id": [10, 11, 20], "es_seguimiento": [False, False, False],
                       "source_id": ["a", "b", "a"]})
    aristas = pd.DataFrame({"article_id_a": [10, 30, 11, 20], "article_id_b": [30, 11, 31, 32],
                            "medio_a": ["a", "c", "b", "a"], "medio_b": ["c", "b", "c", "d"],
                            "sim": [0.72, 0.65, 0.78, 0.61]})
    near = near_present(ev, aristas, np.array([0, 1]), media=["a", "b", "c", "d"])
    assert np.isclose(near[0, 2], 0.78)   # medio c: mejor de 0,72 (con 10) y 0,78 (con 11)
    assert np.isnan(near[0, 3])           # sin arista hacia d
    assert np.isclose(near[1, 3], 0.61)
