import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import silver
from silver import (ESTRATOS, PLAN, asignacion, asignar_estrato, build_workbook, combinar, consolidar,
                    elegir_dobles, enmascarar_medio, kappa_ponderada, menciona_medio, muestrear, poblacion,
                    split_for_two, tasa_ponderada, terminos_carga, wilson_p)

SILVER = Path(__file__).resolve().parents[1] / "resultados_publico" / "silver"
# Lo que no puede aparecer en ninguna celda de la planilla: nombres de los medios
# (como se escriben en el proyecto y en minúsculas sin tildes), marcas y dominios.
PROHIBIDO = ["El Tiempo", "Blu Radio", "Noticias RCN", "Noticias Caracol", "La República", "bluradio", "blu radio",
             "noticias caracol", "noticiascaracol", "noticias rcn", "noticiasrcn", "eltiempo", "larepublica",
             "el_tiempo", "blu_radio", "noticias_rcn", "noticias_caracol", "la_republica", "http", "www."]


def _celdas(path):
    from openpyxl import load_workbook

    wb = load_workbook(path)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    yield ws.title, c.coordinate, str(c.value)
                if c.hyperlink is not None:
                    yield ws.title, c.coordinate, str(c.hyperlink.target)


def _sin_medio(path):
    for hoja, coord, v in _celdas(path):
        for p in PROHIBIDO:
            assert p.lower() not in v.lower(), (hoja, coord, v)
        assert not re.search(r"\b(?:blu|rcn|caracol)\b", v, re.I), (hoja, coord, v)


def _muestra(n=40, dobles=10):
    return pd.DataFrame({
        "id": [f"T{i:03d}" for i in range(1, n + 1)], "doble": ["Sí"] * dobles + ["No"] * (n - dobles),
        "fecha": "2023-01-02", "gobierno": "Petro", "titular": "Gobierno anuncia reforma",
        "contexto": "• Otro titular", "n_otros": 1})


def test_menciones_a_medios_se_detectan_y_enmascaran():
    assert menciona_medio("Ministro habla en noticias caracol sobre atentados")
    assert menciona_medio("Editorial de el tiempo del de octubre")
    assert menciona_medio("Situacion en el cauca mananas blu con camila zuluaga")
    assert not menciona_medio("Banco de la republica sube las tasas")
    assert not menciona_medio("El tiempo se agota para la reforma")
    assert enmascarar_medio("Ministro habla en Noticias caracol de la paz") == "Ministro habla en [medio] de la paz"
    assert "rcn" not in enmascarar_medio("Lo que dijo a rcn el ministro").lower()


def test_terminos_de_carga_y_usos_neutros():
    assert terminos_carga("ministro se despacho contra los jueces") == ["se despacho"]
    assert terminos_carga("el fracaso de la reforma") == ["fracaso"]
    assert terminos_carga("pacto historico presenta lista") == []
    assert terminos_carga("ataque terrorista en cauca") == []
    assert terminos_carga("un dia historico para el pais") == ["historico"]


def test_estratos_y_prioridad():
    en = pd.Series([True, True, True, False, False])
    lex = pd.Series([True, False, False, True, False])
    div = pd.Series([True, True, False, True, False])
    assert asignar_estrato(en, lex, div).tolist() == ["E_lexico", "E_divergente", "E_resto", "S_lexico", "S_resto"]
    assert set(PLAN) == set(ESTRATOS) and sum(PLAN.values()) == 30


def test_asignacion_no_pasa_de_la_poblacion_y_completa_con_el_resto():
    n = asignacion({"E_lexico": 3, "E_divergente": 100, "E_resto": 100, "S_lexico": 100, "S_resto": 100})
    assert n["E_lexico"] == 3 and sum(n.values()) == 30
    assert n["E_resto"] == PLAN["E_resto"] + PLAN["E_lexico"] - 3
    n = asignacion({"E_lexico": 1, "E_resto": 2, "S_resto": 100})
    assert sum(n.values()) == 30 and n["S_resto"] == 27


def test_poblacion_excluye_rcn_duque_antes_de_2020_09_y_menciones():
    frame = pd.DataFrame({
        "article_id": range(6),
        "source_id": ["noticias_rcn", "noticias_rcn", "noticias_rcn", "blu_radio", "blu_radio", "el_tiempo"],
        "government_id": ["duque", "duque", "petro", "duque", "duque", "petro"],
        "published_date": ["2020-08-15", "2020-09-02", "2023-01-01", "2019-01-01", "2019-01-01", "2023-05-01"],
        "title": [f"Gobierno presenta su nueva reforma {x}" for x in ("uno", "dos", "tres")] + ["Ministra revela propuesta en blu radio hoy",
                                                              "Corte tumba la ley de financiamiento", "Opinion x y z w"],
        "section": ["nacion"] * 6, "topic": [1, 1, 1, 1, 1, 1]})
    pop, excl = poblacion(frame)
    assert pop["article_id"].tolist() == [1, 2, 4]
    assert excl["rcn_duque_antes_2020_09"] == 1 and excl["menciona_un_medio"] == 1 and excl["opinion_o_humor"] == 1


def test_muestreo_estratificado_y_dobles_por_celda():
    rng = np.random.default_rng(0)
    rows = []
    for m in ["a", "b"]:
        for g in ["duque", "petro"]:
            for h in ESTRATOS:
                rows += [{"source_id": m, "government_id": g, "estrato": h, "x": rng.random()} for _ in range(50)]
    pop = pd.DataFrame(rows)
    sample, tabla = muestrear(pop, seed=1)
    assert len(sample) == 4 * 30
    tam = sample.groupby(["source_id", "government_id", "estrato"]).size()
    assert tam.to_dict() == tabla.set_index(["source_id", "government_id", "estrato"])["n_h"].to_dict()
    dob = sample.loc[elegir_dobles(sample, 6, seed=1)]
    assert dob.groupby(["source_id", "government_id"]).size().eq(6).all()
    assert dob.groupby(["source_id", "government_id"])["estrato"].nunique().eq(5).all()


def test_division_con_dobles_en_ambas():
    muestra = _muestra(70, 20)
    key = pd.DataFrame({"id": muestra["id"], "source_id": [f"m{i % 5}" for i in range(70)],
                        "government_id": "petro", "estrato": [ESTRATOS[i % 5] for i in range(70)]})
    p1, p2 = split_for_two(muestra, key, seed=1)
    dob = set(muestra.loc[muestra["doble"] == "Sí", "id"])
    assert dob <= set(p1["id"]) and dob <= set(p2["id"])
    s1, s2 = set(p1["id"]) - dob, set(p2["id"]) - dob
    assert not s1 & s2 and len(s1 | s2) == 50 and abs(len(s1) - len(s2)) <= 1
    assert list(p1.columns) == list(muestra.columns)  # la clave (medio, estrato) no pasa a la planilla


def test_opciones_sin_comas():
    for opciones in silver.LISTAS.values():
        assert all("," not in o for o in opciones)
        assert len(",".join(opciones)) + 2 <= 255  # límite de Excel para listas en línea


def test_planilla_a_ciegas_del_medio(tmp_path):
    m = _muestra(12, 4)
    m.loc[0, "contexto"] = "• " + enmascarar_medio("Ministro habla en noticias caracol sobre la paz")
    path = tmp_path / "p.xlsx"
    build_workbook(m, path, persona=1)
    _sin_medio(path)
    from openpyxl import load_workbook

    an = load_workbook(path)["Anotación"]
    headers = [c.value for c in an[1]]
    assert "medio" not in headers and not any("url" in str(h).lower() or "enlace" in str(h).lower() for h in headers)
    assert an.max_row == 13


@pytest.mark.parametrize("k", [1, 2])
def test_planillas_reales_a_ciegas(k):
    path = SILVER / f"planilla_silver_persona_{k}.xlsx"
    if not path.exists():
        pytest.skip("sin planillas generadas")
    _sin_medio(path)


def test_kappa():
    from calibracion import cohen_kappa

    assert cohen_kappa(["Sí", "No", "Sí"], ["Sí", "No", "Sí"]) == pytest.approx(1.0)
    assert cohen_kappa(["s", "s", "n", "n"], ["s", "n", "s", "n"]) == pytest.approx(0.0)
    assert kappa_ponderada([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    # desacuerdos de un punto pesan menos que de dos
    assert kappa_ponderada([1, 2, 3, 1], [1, 2, 3, 2]) > kappa_ponderada([1, 2, 3, 1], [1, 2, 3, 3])


def _sheet(ids, dobles, sesgado, tipo=None, direccion=None, intensidad=None):
    n = len(ids)
    return pd.DataFrame({"id": ids, "doble": dobles, "¿sesgado?": sesgado,
                         "tipo principal": tipo or [None] * n, "dirección": direccion or [None] * n,
                         "intensidad": intensidad or [None] * n, "comentario": [None] * n, "nombre": ["x"] * n})


def test_consolidacion_y_adjudicacion():
    s1 = _sheet(["T1", "T2", "T3", "T4"], ["Sí", "Sí", "Sí", "No"], ["Sí", "No", "Sí", "No"],
                ["Sensacionalismo", None, "Lenguaje cargado", None], ["Neutra / no aplica", None, "Favorable", None],
                ["1 leve", None, "3 fuerte", None])
    s2 = _sheet(["T1", "T2", "T3", "T5"], ["Sí", "Sí", "Sí", "No"], ["Sí", "Sí", "Sí", "Sí"],
                ["Sensacionalismo", "Otro", "Opinión como hecho", "Otro"],
                ["Neutra / no aplica", "Favorable", "Favorable", "Favorable"], ["3 fuerte", "1 leve", "2 moderada",
                                                                               "1 leve"])
    c = consolidar(combinar([s1, s2])).set_index("id")
    assert c.loc["T1", "fuente"] == "acuerdo de dos" and c.loc["T1", "intensidad"] == 2.0
    assert c.loc["T2", "sesgado"] == "Pendiente" and np.isnan(c.loc["T2", "sesgado_bin"])
    assert c.loc["T3", "sesgado"] == "Sí" and c.loc["T3", "tipo"] == "Pendiente" and c.loc["T3", "fuente"] == "desacuerdo"
    assert c.loc["T4", "fuente"] == "una persona" and c.loc["T5", "sesgado_bin"] == 1
    adj = pd.DataFrame({"id": ["T2"], "decisión · ¿sesgado?": ["No"]})
    c2 = consolidar(combinar([s1, s2]), adj).set_index("id")
    assert c2.loc["T2", "sesgado"] == "No" and c2.loc["T2", "fuente"] == "adjudicado"


def test_tasa_ponderada_por_estrato():
    # Estrato grande con 10 % de sesgo y estrato pequeño enriquecido con 50 %.
    d = pd.DataFrame({"source_id": "a", "government_id": "petro",
                      "estrato": ["E_resto"] * 10 + ["E_lexico"] * 10,
                      "sesgado_bin": [1] + [0] * 9 + [1] * 5 + [0] * 5})
    pe = pd.DataFrame({"source_id": "a", "government_id": "petro", "estrato": ["E_resto", "E_lexico"],
                       "N_h": [900, 100]})
    r = tasa_ponderada(d, pe, ["source_id", "government_id"]).iloc[0]
    assert r["tasa_sin_ponderar"] == pytest.approx(0.30)
    assert r["tasa_ponderada"] == pytest.approx(0.9 * 0.1 + 0.1 * 0.5)
    assert r["n_efectivo"] < 20 and r["ic_bajo"] < r["tasa_ponderada"] < r["ic_alto"]
    lo, hi = wilson_p(0.5, 20)
    from research_stats import wilson_interval

    assert (lo, hi) == pytest.approx(wilson_interval(10, 20))
