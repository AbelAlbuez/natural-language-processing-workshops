import numpy as np
import pandas as pd

from lexico_banda import (aplica_regla, comparar_con_080, elegir_regla, evento_de_titular, idf_titulares,
                          parejas_banda, precision_anidada, precision_filtro, rasgos_pareja, reglas, tabla_larga)


# ── unidad: parejas de la banda ──────────────────────────────────────────────


def test_parejas_banda_rango_y_fuera_de_eventos():
    pi = np.array([0, 2, 4, 6, 8])
    pj = np.array([1, 3, 5, 7, 9])
    ps = np.array([0.64, 0.65, 0.79, 0.80, 0.70])
    ev_de = np.full(10, -1)
    ev_de[[8, 9]] = 3          # la pareja (8, 9) ya está junta en un evento ≥ 0,80
    ev_de[4] = 1                # (4, 5): sólo uno está en un evento, se queda
    P = parejas_banda(pi, pj, ps, ev_de)
    assert P[["i", "j"]].values.tolist() == [[2, 3], [4, 5]]   # 0,64 y 0,80 fuera; (8, 9) fuera


def test_evento_de_titular():
    frame = pd.DataFrame({"article_id": [10, 11, 12]})
    ev = pd.DataFrame({"event_id": [5, 5], "article_id": [10, 12]})
    assert evento_de_titular(frame, ev).tolist() == [5, -1, 5]


# ── rasgos y filtro ──────────────────────────────────────────────────────────


def test_rasgos_terminos_raros():
    sets = [{"otoniel", "corte", "extradicion"}, {"otoniel", "corte", "aval"}] + [{"corte"}] * 2000
    idf = idf_titulares(sets)
    r = rasgos_pareja(sets[0], sets[1], idf)
    assert r["n_comunes"] == 2
    assert r["n_raro_300"] == 1             # «otoniel» es raro; «corte» (2.002 titulares) no
    assert r["n_raro_3000"] == 2
    assert r["sum_idf"] >= r["max_idf"] > 0     # «corte» está en todos: IDF 0
    assert 0 < r["wjac"] < 1


def _R(dias, raros, topico):
    n = len(dias)
    return pd.DataFrame({"dias": dias, "n_raro_300": raros, "n_raro_1000": raros, "n_raro_3000": raros,
                         "mismo_topico": topico, "sim": np.full(n, 0.7)})


def test_reglas_sin_duplicados_y_aplicacion():
    todas = reglas()
    claves = {(r["dias_max"], r["df_raro"] if r["n_raro_min"] else 0, r["n_raro_min"], r["mismo_topico"])
              for r in todas}
    assert len(claves) == len(todas)
    R = _R([0, 1, 0], [1, 1, 0], [True, True, False])
    m = aplica_regla(R, {"dias_max": 0, "df_raro": 1000, "n_raro_min": 1, "mismo_topico": False})
    assert m.tolist() == [True, False, False]


def test_elegir_regla_y_validacion_anidada_separable():
    # la etiqueta es exactamente «misma fecha y un término raro»: esa regla debe ganar
    rng = np.random.default_rng(0)
    dias = rng.integers(0, 3, 120)
    raros = rng.integers(0, 3, 120)
    y = (dias == 0) & (raros >= 1)
    R = _R(dias, raros, rng.random(120) < 0.5)
    todas = reglas()
    elegida = todas[elegir_regla(R, y, todas)]
    assert elegida["dias_max"] == 0 and elegida["n_raro_min"] == 1 and not elegida["mismo_topico"]
    res = precision_anidada(R, y, todas, reps=5, seed=1)
    assert res["precision_mediana"] == 1.0


def test_precision_filtro_wilson_y_ponderada():
    A = pd.DataFrame({"tramo": ["0.65–0.70"] * 4 + ["0.75–0.80"] * 4,
                      "acierto": [True, False, False, False, True, True, True, False]})
    pasa = np.array([True, True, False, False, True, True, False, False])
    pob = pd.Series({"0.65–0.70": 100, "0.75–0.80": 300})
    f = precision_filtro("x", pasa, A, pob)
    assert f["pasan"] == 4 and f["mismo_hecho"] == 3 and f["precision"] == 0.75
    assert f["ic_bajo"] < 0.75 < f["ic_alto"]
    assert np.isclose(f["precision_ponderada"], 0.25 * 0.5 + 0.75 * 1.0)   # pesos 100/400 y 300/400


# ── tabla larga y comparación ────────────────────────────────────────────────


def test_tabla_larga_dos_filas_y_descarta_cruce_de_gobierno():
    frame = pd.DataFrame({
        "source_id": ["el_tiempo", "blu_radio", "el_tiempo", "noticias_rcn"],
        "title": ["Gobierno Petro anuncia", "El gobierno anuncia", "a", "b"],
        "government_id": ["petro", "petro", "duque", "petro"],
        "topic": [1, 1, 2, 5],
        "fecha": pd.to_datetime(["2023-01-02", "2023-01-01", "2022-08-06", "2022-08-07"]),
    })
    P = pd.DataFrame({"i": [0, 2], "j": [1, 3], "sim": [0.7, 0.7], "pareja": [0, 1],
                      "variante": ["filtrada", "filtrada"], "logit": [0.6, 0.6]})
    L = tabla_larga(P, frame)
    assert L["event_id"].tolist() == [0, 0]            # la pareja 1 cruza Duque → Petro
    assert set(L["fecha_inicio"]) == {"2023-01-01"}    # la primera fecha de la pareja
    assert L["mes"].iat[0] == "2023-01" and L["domestico"].all()


def test_comparar_con_080_marca_nuevas():
    base = dict(medio="el_tiempo", gobierno="petro")
    lo = pd.DataFrame([{**base, "termino": "a", "distintiva": True}, {**base, "termino": "b", "distintiva": True},
                       {**base, "termino": "c", "distintiva": True}])
    lo80 = pd.DataFrame([{**base, "termino": "a", "delta": 1.0, "z": 5.0, "distintiva": True, "robusta": True},
                         {**base, "termino": "b", "delta": 0.3, "z": 2.5, "distintiva": False, "robusta": False}])
    otra = lo[["medio", "gobierno", "termino"]].assign(delta=0.1, z=[3.0, 0.5, 0.0])
    r = comparar_con_080(lo, lo80, {"rechazada": otra}).set_index("termino")
    assert r["nueva"].tolist() == [False, True, True]
    assert r["nueva_estricta"].tolist() == [False, False, True]   # «b» ya era nominalmente significativa
    assert r["tambien_en_rechazadas"].tolist() == [True, False, False]
    assert not r.loc["c", "en_vocab_080"]
