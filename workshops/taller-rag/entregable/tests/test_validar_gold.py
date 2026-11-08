"""Pruebas del validador del gold standard con datos sintéticos (no reales)."""
import csv
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts import validar_gold_standard as vg

TEMAS = ["Tema A", "Tema B", "Tema C"]  # "Tema C" no aparece: no se exige cobertura
CUOTAS = {"estratos": [  # solo respondibles
    {"fuente_esperada": "media_cloud", "idioma": "es", "desarrollo": 2, "prueba": 0},
    {"fuente_esperada": "bluesky", "idioma": "en", "desarrollo": 1, "prueba": 1},
]}
DOC_IDS = ["doc-1", "doc-2", "doc-3", "doc-4"]

FILAS = [
    # id, pregunta, idioma, tipo, fuente, tema, respuesta, evidencia, split
    ("G01", "Pregunta sintética uno", "es", "sintetica", "media_cloud", "", "Respuesta 1", "doc-1", "desarrollo"),
    ("G02", "Pregunta sintética dos", "es", "manual", "media_cloud", "", "Respuesta 2", "doc-2;doc-3", "desarrollo"),
    ("G03", "Pregunta sintética tres", "es", "no_respondible", "", "", "", "", "prueba"),
    ("G04", "Synthetic question four", "en", "sintetica", "bluesky", "Tema B", "Answer 4", "doc-4", "desarrollo"),
    ("G05", "Synthetic question five", "en", "manual", "bluesky", "Tema A", "Answer 5", "doc-1", "prueba"),
    ("G06", "Synthetic question six", "en", "no_respondible", "", "", "", "", "prueba"),
]
I = {c: i for i, c in enumerate(vg.COLUMNAS)}


def cambiar(fila, **campos):
    fila = list(fila)
    for col, valor in campos.items():
        fila[I[col]] = valor
    return tuple(fila)


def escribir_entradas(tmp_path, filas, temas_en_docs=False):
    gold = tmp_path / "gold.csv"
    with gold.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(vg.COLUMNAS + ["validada_por"])  # columna extra permitida
        writer.writerows([f + ("pendiente de revisión humana",) for f in filas])
    docs = tmp_path / "docs.parquet"
    pq.write_table(pa.table({"document_id": DOC_IDS}), docs)
    cuotas = tmp_path / "cuotas.json"
    cuotas.write_text(json.dumps(CUOTAS), encoding="utf-8")
    temas = tmp_path / ("docs/temas_gold.json" if temas_en_docs else "temas.json")
    temas.parent.mkdir(exist_ok=True)
    temas.write_text(json.dumps(TEMAS), encoding="utf-8")
    return gold, docs, cuotas, temas


def ejecutar(tmp_path, filas, usar_temas_por_defecto=False):
    gold, docs, cuotas, temas = escribir_entradas(tmp_path, filas, temas_en_docs=usar_temas_por_defecto)
    salida = tmp_path / "validacion.json"
    argv = ["--gold", str(gold), "--documentos", str(docs), "--cuotas", str(cuotas),
            "--filas-esperadas", "6", "--min-no-respondible", "2", "--salida", str(salida)]
    if not usar_temas_por_defecto:
        argv += ["--temas", str(temas)]
    code = vg.main(argv)
    resumen = json.loads(salida.read_text(encoding="utf-8"))
    return code, {r["verificacion"]: r for r in resumen["resultados"]}, resumen


def fallas(res):
    return [k for k, r in res.items() if not r["ok"]]


def test_caso_valido_aprueba_todas_las_verificaciones(tmp_path):
    code, res, resumen = ejecutar(tmp_path, FILAS)
    assert code == 0 and resumen["aprobado"], fallas(res)
    assert "cobertura_temas" not in res                      # (d) no se exige cobertura
    assert res["valores_tema"]["temas_distintos"] == 2       # se informa


def test_evidencia_inexistente_falla_solo_esa_verificacion(tmp_path):
    filas = list(FILAS)
    filas[0] = cambiar(filas[0], evidencia_doc_id="doc-no-existe")
    code, res, _ = ejecutar(tmp_path, filas)
    assert code == 1 and fallas(res) == ["evidencia_doc_id"]
    assert res["evidencia_doc_id"]["ids_inexistentes"] == 1


# (a) fuente y tema solo en respondibles
@pytest.mark.parametrize("campo, verificacion", [("fuente_esperada", "valores_fuente_esperada"),
                                                  ("tema", "valores_tema")])
def test_no_respondible_con_fuente_o_tema_falla(tmp_path, campo, verificacion):
    filas = list(FILAS)
    filas[2] = cambiar(filas[2], **{campo: "media_cloud" if campo == "fuente_esperada" else "Tema A"})
    _, res, _ = ejecutar(tmp_path, filas)
    assert fallas(res) == [verificacion]


def test_respondible_sin_fuente_falla(tmp_path):
    filas = list(FILAS)
    filas[0] = cambiar(filas[0], fuente_esperada="")
    _, res, _ = ejecutar(tmp_path, filas)
    assert not res["valores_fuente_esperada"]["ok"]
    assert res["valores_fuente_esperada"]["vacios_en_respondibles"] == 1


def test_bluesky_respondible_sin_tema_falla(tmp_path):
    filas = list(FILAS)
    filas[3] = cambiar(filas[3], tema="")
    _, res, _ = ejecutar(tmp_path, filas)
    assert fallas(res) == ["valores_tema"] and res["valores_tema"]["bluesky_sin_tema"] == 1


# (b) cuotas solo sobre respondibles
def test_no_respondibles_no_cuentan_en_cuotas(tmp_path):
    filas = list(FILAS) + [("G07", "Otra fuera del corpus", "es", "no_respondible", "", "", "", "", "desarrollo")]
    gold, docs, cuotas, temas = escribir_entradas(tmp_path, filas)
    res = {r["verificacion"]: r for r in vg.validar(*vg.leer_csv(gold), set(DOC_IDS), vg.leer_cuotas(cuotas),
                                                    TEMAS, filas_esperadas=7, min_no_respondible=2)}
    assert res["cuotas_split"]["ok"] and res["cuotas_split"]["filas_fuera_de_tabla"] == 0
    filas[0] = cambiar(filas[0], split="prueba")  # una respondible fuera de cuota sí falla
    gold, *_ = escribir_entradas(tmp_path, filas)
    res = {r["verificacion"]: r for r in vg.validar(*vg.leer_csv(gold), set(DOC_IDS), vg.leer_cuotas(cuotas),
                                                    TEMAS, filas_esperadas=7, min_no_respondible=2)}
    assert not res["cuotas_split"]["ok"]


# (c) tema lleno debe estar en la lista; fuera de Bluesky debe ir vacío
def test_tema_invalido_o_fuera_de_bluesky_falla(tmp_path):
    filas = list(FILAS)
    filas[3] = cambiar(filas[3], tema="Tema inexistente")
    _, res, _ = ejecutar(tmp_path, filas)
    assert fallas(res) == ["valores_tema"] and res["valores_tema"]["invalidos"] == 1
    filas = list(FILAS)
    filas[0] = cambiar(filas[0], tema="Tema A")
    _, res, _ = ejecutar(tmp_path, filas)
    assert fallas(res) == ["valores_tema"] and res["valores_tema"]["lleno_fuera_de_bluesky"] == 1


# (e) --temas por defecto docs/temas_gold.json
def test_temas_por_defecto_en_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, res, _ = ejecutar(tmp_path, FILAS, usar_temas_por_defecto=True)
    assert code == 0, fallas(res)


def test_salida_no_contiene_texto_de_preguntas(tmp_path, capsys):
    _, _, resumen = ejecutar(tmp_path, FILAS)
    volcado = json.dumps(resumen, ensure_ascii=False) + capsys.readouterr().out
    for fila in FILAS:
        assert fila[1] not in volcado and (not fila[6] or fila[6] not in volcado)


@pytest.mark.parametrize("campos, verificacion", [
    ({"respuesta_referencia": ""}, "respuesta_en_respondibles"),
    ({"pregunta": "PREGUNTA   sintética DOS"}, "preguntas_sin_duplicados"),
    ({"split": "prueba"}, "cuotas_split"),
])
def test_otras_fallas_se_detectan(tmp_path, campos, verificacion):
    filas = list(FILAS)
    filas[0] = cambiar(filas[0], **campos)
    _, res, _ = ejecutar(tmp_path, filas)
    assert not res[verificacion]["ok"]


def test_columnas_ausentes_no_rompen_el_validador():
    res = {r["verificacion"]: r for r in vg.validar(["id", "pregunta"], [{"id": "G01", "pregunta": ""}],
                                                    set(), {}, TEMAS, filas_esperadas=1, min_no_respondible=0)}
    assert not res["columnas_obligatorias"]["ok"] and res["columnas_obligatorias"]["faltantes"] == 7
    assert not res["pregunta_no_vacia"]["ok"]
