import numpy as np
import pandas as pd
import pytest

from calibracion import cohen_kappa, reciprocal_pairs, stratified, tramo


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def test_parejas_reciprocas_solo_entre_medios_y_dentro_de_la_ventana():
    emb = np.array([_unit([1, 0, 0]), _unit([1, 0.05, 0]), _unit([1, 0, 0.02]), _unit([0, 1, 0])])
    media = np.array(["a", "b", "b", "a"])
    dates = np.array([0, 1, 10, 0])  # el 2 queda fuera de ±2 días del 0
    pairs = reciprocal_pairs(dates, media, emb, queries=np.arange(4), sim_min=0.6)
    assert {(min(a, b), max(a, b)) for a, b in zip(pairs["a"], pairs["b"])} == {(0, 1)}


def test_no_recíproca_no_entra():
    # 1 es el mejor de "b" para 0, pero el mejor de "a" para 1 es 2.
    emb = np.array([_unit([1, 0.3, 0]), _unit([1, 0, 0]), _unit([1, 0.01, 0])])
    media = np.array(["a", "b", "a"])
    pairs = reciprocal_pairs(np.zeros(3, dtype=int), media, emb, queries=np.array([0]), sim_min=0.0)
    assert pairs.empty


def test_tramos_y_muestra_estratificada():
    assert tramo(0.61) == "0.60–0.65" and tramo(0.95) == "0.90–1.00" and tramo(0.5) == "<0.60"
    pairs = pd.DataFrame({"a": range(100), "b": range(100, 200), "sim": np.linspace(0.55, 0.99, 100)})
    sample = stratified(pairs, per_bin=3, seed=1)
    assert sample.groupby("tramo").size().eq(3).all()
    assert "<0.60" not in set(sample["tramo"])


def test_kappa():
    assert cohen_kappa(["s", "n", "s", "n"], ["s", "n", "s", "n"]) == pytest.approx(1.0)
    assert cohen_kappa(["s", "s", "n", "n"], ["s", "n", "s", "n"]) == pytest.approx(0.0)


def test_etiquetas_sin_comas_para_la_lista_desplegable():
    from calibracion import ETIQUETAS

    assert all("," not in e for e in ETIQUETAS)


def test_division_para_dos_personas():
    from calibracion import combine_personas, split_for_two

    n = 70
    muestra = pd.DataFrame({"pareja": [f"P{i:03d}" for i in range(1, n + 1)],
                            "doble": ["Sí"] * 20 + ["No"] * 50, "titular_a": "x"})
    key = pd.DataFrame({"pareja": muestra["pareja"], "tramo": [f"t{i % 5}" for i in range(n)]})
    p1, p2 = split_for_two(muestra, key, seed=1)
    dob = set(muestra.loc[muestra["doble"] == "Sí", "pareja"])
    assert dob <= set(p1["pareja"]) and dob <= set(p2["pareja"])
    simples1, simples2 = set(p1["pareja"]) - dob, set(p2["pareja"]) - dob
    assert not simples1 & simples2 and len(simples1 | simples2) == 50
    assert abs(len(simples1) - len(simples2)) <= 1

    def filled(p, label):
        return p.assign(**{"Anotador · nombre": label, "Anotador · ¿mismo hecho?": "Mismo hecho",
                           "Anotador · comentario": None})
    both = combine_personas([filled(p1, "uno"), filled(p2, "dos")])
    assert len(both) == n
    d = both[both["doble"] == "Sí"]
    assert d["Anotador 1 · nombre"].eq("uno").all() and d["Anotador 2 · nombre"].eq("dos").all()
    s = both[both["doble"] == "No"]
    assert s["Anotador 1 · nombre"].notna().all() and s["Anotador 2 · nombre"].isna().all()


def test_precision_ponderada_por_poblacion():
    from calibracion import weighted_precision

    # Tramo bajo: 0 % de aciertos y muy frecuente; tramo alto: 100 % y raro.
    d1 = pd.DataFrame({"tramo": ["0.85–0.90"] * 10 + ["0.90–1.00"] * 10,
                       "acierto": [False] * 10 + [True] * 10})
    pop = pd.Series({"0.85–0.90": 900, "0.90–1.00": 100})
    w = weighted_precision(d1, pop).set_index("umbral")
    assert w.loc[0.85, "precision"] == pytest.approx(0.10)  # sin ponderar sería 0.50
    assert w.loc[0.90, "precision"] == pytest.approx(1.0)
    assert w.loc[0.85, "ic_bajo"] < 0.10 < w.loc[0.85, "ic_alto"]
