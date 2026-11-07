import numpy as np
import pandas as pd
from scipy import sparse

from lexico import (bh_adjust, clase_termino, comparar, formas_nombrar, log_odds, matrices_emparejadas, newcombe,
                    proporciones_emparejadas, terminos)


# ── log-odds con prior ───────────────────────────────────────────────────────


def test_log_odds_signo_y_simetria():
    y_i = np.array([30.0, 5.0, 10.0])
    y_j = np.array([5.0, 30.0, 10.0])
    prior = np.array([1.0, 1.0, 1.0])
    d, var = log_odds(y_i, y_j, prior)
    assert d[0] > 0 and d[1] < 0          # más propio de i / de j
    assert np.isclose(d[0], -d[1])        # simetría entre los dos términos espejo
    d_inv, var_inv = log_odds(y_j, y_i, prior)
    assert np.allclose(d, -d_inv)         # intercambiar los grupos invierte el signo
    assert np.allclose(var, var_inv)


def test_log_odds_presencia_uso_igual_da_cero():
    # Con n = número de eventos en los dos lados, el mismo uso da δ = 0 exactamente,
    # aunque los totales de términos de cada lado sean distintos.
    d, _ = log_odds(np.array([7.0, 0.0]), np.array([7.0, 3.0]), np.array([0.5, 0.5]), 50, 50, 10)
    assert d[0] == 0 and d[1] < 0


def test_log_odds_prior_encoge_los_raros():
    # Con un prior más fuerte, el mismo contraste en un término raro da |δ| menor.
    debil, _ = log_odds(np.array([3.0]), np.array([0.0]), np.array([0.1]), 100, 100, 1)
    fuerte, _ = log_odds(np.array([3.0]), np.array([0.0]), np.array([5.0]), 100, 100, 50)
    assert 0 < fuerte[0] < debil[0]


def test_bh():
    q = bh_adjust([0.01, 0.04, 0.03, 0.5])
    assert np.allclose(q, [0.04, 0.16 / 3, 0.16 / 3, 0.5])


# ── diseño emparejado ────────────────────────────────────────────────────────


def _meta(filas):
    return pd.DataFrame(filas, columns=["event_id", "source_id"])


def test_emparejado_solo_eventos_compartidos_y_otros_promediados():
    meta = _meta([(1, "a"), (1, "b"), (1, "c"), (2, "a"), (3, "b"), (3, "c"), (4, "a"), (4, "b")])
    X = np.array([[1, 0], [1, 0], [0, 0], [1, 1], [0, 1], [0, 1], [0, 0], [0, 1]], dtype=float)
    eventos, A, B = matrices_emparejadas(meta, X, "a")
    assert eventos.tolist() == [1, 4]     # el 2 sólo tiene al medio; el 3 no lo tiene
    assert A.toarray().tolist() == [[1, 0], [0, 0]]
    assert B.toarray().tolist() == [[0.5, 0], [0, 1]]   # evento 1: b y c pesan 1/2 cada uno


def test_emparejado_excluir_medio():
    meta = _meta([(1, "a"), (1, "rcn"), (2, "a"), (2, "b")])
    X = np.eye(4)
    eventos, _, B = matrices_emparejadas(meta, X, "a", excluir=("rcn",))
    assert eventos.tolist() == [2]
    assert B.toarray().tolist() == [[0, 0, 0, 1]]


def test_comparar_detecta_palabra_del_medio_y_no_la_agenda():
    # 60 eventos con a y b. «agenda» aparece en los dos titulares de cada evento (mismo hecho);
    # «encuadre» sólo en a, en 30 eventos. Sólo «encuadre» debe salir distintiva.
    rng = np.random.default_rng(0)
    filas, X = [], []
    for e in range(60):
        enc = e < 30
        for m in ("a", "b"):
            filas.append((e, m))
            X.append([1, int(enc and m == "a"), int(rng.random() < 0.3)])
    meta = _meta(filas).assign(mes=lambda d: (d["event_id"] // 10).astype(str))
    tab, n = comparar(meta, sparse.csr_matrix(np.array(X, float)), ["agenda", "encuadre", "ruido"],
                      (np.array([0.5, 0.1, 0.2]), 10.0), "a", reps=300, min_eventos=5)
    tab = tab.set_index("termino")
    assert n == 60
    assert tab.loc["agenda", "delta"] == 0 and tab.loc["agenda", "z"] == 0
    assert tab.loc["encuadre", "delta"] > 0 and tab.loc["encuadre", "q_bh"] < 0.05
    assert tab.loc["encuadre", "n_solo_medio"] == 30 and tab.loc["encuadre", "n_solo_otros"] == 0
    assert abs(tab.loc["ruido", "z"]) < 3


def test_proporciones_emparejadas_y_newcombe():
    meta = _meta([(e, m) for e in range(40) for m in ("a", "b")])
    F = pd.DataFrame({c: False for c in ["gobierno_apellido", "ref_gobierno", "personal_amplio", "ref_ejecutivo"]},
                     index=meta.index)
    a = meta["source_id"] == "a"
    F.loc[:, "ref_gobierno"] = True
    F.loc[:, "ref_ejecutivo"] = True
    F.loc[a & (meta["event_id"] < 20), "gobierno_apellido"] = True       # a: 50 %
    F.loc[~a & (meta["event_id"] < 4), "gobierno_apellido"] = True       # b: 10 %
    r = proporciones_emparejadas(meta, F, "a", reps=500).set_index("forma")
    assert np.isclose(r.loc["gobierno_apellido", "diferencia"], 0.4)
    assert r.loc["gobierno_apellido", "ic_bajo"] > 0
    assert np.isclose(r.loc["pers_gobierno", "prop_medio"], 0.5)
    d, lo, hi = newcombe(10, 100, 30, 100)
    assert np.isclose(d, 0.2) and lo < 0.2 < hi and lo > 0


# ── texto y formas de nombrar ────────────────────────────────────────────────


def test_terminos_y_clases():
    t = terminos("El Gobierno Petro radicó la reforma a la salud", set(["el", "la", "a"]))
    assert {"gobierno", "petro", "gobierno petro", "reforma salud"} <= t
    assert clase_termino("videos") == "formato"
    assert clase_termino("mananas blu") == "formato"
    assert clase_termino("denuncio") == "atribucion"
    assert clase_termino("reforma salud") == "contenido"


def test_formas_nombrar_simetricas():
    p = formas_nombrar("gobierno petro radico con mensaje de urgencia la reforma", "petro")
    d = formas_nombrar("gobierno duque radico con mensaje de urgencia la reforma", "duque")
    assert p == d                                   # misma frase, mismo resultado en los dos gobiernos
    assert p["gobierno_apellido"] and p["ref_gobierno"] and p["personal_amplio"]
    assert not p["gobierno_generico"] and not p["apellido_solo"]


def test_formas_nombrar_casos():
    f = formas_nombrar("presidente gustavo petro anuncio que el gobierno nacional", "petro")
    assert f["presidente_apellido"] and f["nombre_completo"] and f["gobierno_nacional"]
    assert not f["apellido_solo"] and not f["gobierno_generico"]
    f = formas_nombrar("petro dice que el gobierno no negociara", "petro")
    assert f["apellido_solo"] and f["gobierno_generico"] and not f["gobierno_apellido"]
    # el apellido es el del presidente de ESE gobierno: «Duque» en tiempos de Petro no cuenta
    f = formas_nombrar("gobierno duque dejo deudas dice el gobierno de petro", "petro")
    assert f["gobierno_apellido"] and not f["gobierno_generico"]
    # gobiernos extranjeros o locales no son «gobierno» sin más
    for t in ("gobierno de venezuela", "gobierno estadounidense anuncio", "gobierno trump", "gobierno distrital"):
        assert not formas_nombrar(t, "petro")["gobierno_generico"], t
    assert formas_nombrar("visita a la casa de narino", "duque")["casa_narino"]
    assert not formas_nombrar("presidente ejecutivo de ecopetrol", "petro")["ejecutivo"]
    assert formas_nombrar("mintrabajo radico la reforma", "petro")["ministro"]
