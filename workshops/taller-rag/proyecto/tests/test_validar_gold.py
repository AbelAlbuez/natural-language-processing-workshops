"""Pruebas del validador del gold standard con datos sintéticos (no reales)."""
import csv
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts import validar_gold_standard as vg

TEMAS = ["Tema A", "Tema B"]
CUOTAS = {"estratos": [
    {"fuente_esperada": "media_cloud", "idioma": "es", "desarrollo": 2, "prueba": 1},
    {"fuente_esperada": "bluesky", "idioma": "en", "desarrollo": 1, "prueba": 2},
]}
DOC_IDS = ["doc-1", "doc-2", "doc-3", "doc-4"]

FILAS = [
    # id, pregunta, idioma, tipo, fuente, tema, respuesta, evidencia, split
    ("G01", "Pregunta sintética uno", "es", "sintetica", "media_cloud", "Tema A", "Respuesta 1", "doc-1", "desarrollo"),
    ("G02", "Pregunta sintética dos", "es", "manual", "media_cloud", "Tema B", "Respuesta 2", "doc-2;doc-3", "desarrollo"),
    ("G03", "Pregunta sintética tres", "es", "no_respondible", "media_cloud", "Tema A", "", "", "prueba"),
    ("G04", "Synthetic question four", "en", "sintetica", "bluesky", "Tema B", "Answer 4", "doc-4", "desarrollo"),
    ("G05", "Synthetic question five", "en", "manual", "bluesky", "Tema A", "Answer 5", "doc-1", "prueba"),
    ("G06", "Synthetic question six", "en", "no_respondible", "bluesky", "Tema B", "", "", "prueba"),
]


def escribir_entradas(tmp_path, filas):
    gold = tmp_path / "gold.csv"
    with gold.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(vg.COLUMNAS)
        writer.writerows(filas)
    docs = tmp_path / "docs.parquet"
    pq.write_table(pa.table({"document_id": DOC_IDS}), docs)
    cuotas = tmp_path / "cuotas.json"
    cuotas.write_text(json.dumps(CUOTAS), encoding="utf-8")
    temas = tmp_path / "temas.json"
    temas.write_text(json.dumps(TEMAS), encoding="utf-8")
    return gold, docs, cuotas, temas


def ejecutar(tmp_path, filas):
    gold, docs, cuotas, temas = escribir_entradas(tmp_path, filas)
    salida = tmp_path / "validacion.json"
    code = vg.main([
        "--gold", str(gold), "--documentos", str(docs), "--cuotas", str(cuotas), "--temas", str(temas),
        "--filas-esperadas", "6", "--min-no-respondible", "2", "--salida", str(salida),
    ])
    resumen = json.loads(salida.read_text(encoding="utf-8"))
    return code, {r["verificacion"]: r for r in resumen["resultados"]}, resumen


def test_caso_valido_aprueba_todas_las_verificaciones(tmp_path):
    code, res, resumen = ejecutar(tmp_path, FILAS)
    assert code == 0 and resumen["aprobado"]
    assert all(r["ok"] for r in res.values()), [k for k, r in res.items() if not r["ok"]]


def test_evidencia_inexistente_falla_solo_esa_verificacion(tmp_path):
    filas = list(FILAS)
    filas[0] = filas[0][:7] + ("doc-no-existe",) + filas[0][8:]
    code, res, _ = ejecutar(tmp_path, filas)
    assert code == 1
    assert not res["evidencia_doc_id"]["ok"]
    assert res["evidencia_doc_id"]["ids_inexistentes"] == 1
    assert [k for k, r in res.items() if not r["ok"]] == ["evidencia_doc_id"]


def test_salida_no_contiene_texto_de_preguntas(tmp_path, capsys):
    _, _, resumen = ejecutar(tmp_path, FILAS)
    volcado = json.dumps(resumen, ensure_ascii=False) + capsys.readouterr().out
    for fila in FILAS:
        assert fila[1] not in volcado and (not fila[6] or fila[6] not in volcado)


@pytest.mark.parametrize("cambio, verificacion", [
    (lambda f: f[:6] + ("",) + f[7:], "respuesta_en_respondibles"),
    (lambda f: f[:3] + ("no_respondible",) + f[4:], "evidencia_doc_id"),
    (lambda f: f[:1] + ("PREGUNTA   sintética DOS",) + f[2:], "preguntas_sin_duplicados"),
    (lambda f: f[:8] + ("prueba",), "cuotas_split"),
])
def test_otras_fallas_se_detectan(tmp_path, cambio, verificacion):
    filas = list(FILAS)
    filas[0] = cambio(filas[0])
    _, res, _ = ejecutar(tmp_path, filas)
    assert not res[verificacion]["ok"]


def test_columnas_ausentes_no_rompen_el_validador():
    res = {r["verificacion"]: r for r in vg.validar(["id", "pregunta"], [{"id": "G01", "pregunta": ""}],
                                                    set(), {}, TEMAS, filas_esperadas=1, min_no_respondible=0)}
    assert not res["columnas_obligatorias"]["ok"] and res["columnas_obligatorias"]["faltantes"] == 7
    assert not res["pregunta_no_vacia"]["ok"]
