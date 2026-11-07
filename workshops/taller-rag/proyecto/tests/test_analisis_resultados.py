"""Análisis de resultados con datos sintéticos: 6 corridas (2 por modelo, una con error)."""
import csv
import json
import math

import pytest

from scripts import analisis_resultados as ar

GOLD = [  # id, tipo, fuente, idioma, evidencia, split
    ("G01", "sintetica", "bluesky", "en", "d-ev1", "desarrollo"),
    ("G02", "no_respondible", "", "es", "", "desarrollo"),
    ("G03", "sintetica", "media_cloud", "es", "d-ev3", "prueba"),
    ("G04", "sintetica", "bluesky", "en", "d-ev4", "desarrollo"),
    ("G05", "no_respondible", "", "en", "", "prueba"),
]
RETRIEVE = [
    {"fase": "retrieve", "id": "G03", "docs": ["d-x", "d-ev3", "d-ev3", "d-y", "d-z"], "scores": [0.90, 0.89, 0.88, 0.87, 0.86]},
    {"fase": "retrieve", "id": "G05", "docs": ["d-a", "d-b", "d-c", "d-d", "d-e"], "scores": [0.85, 0.84, 0.83, 0.82, 0.81]},
]


def ask(model, gid, http=200, abstained=False, validas=(), invalidas=(), evid=False, seg=10.0):
    rec = {"fase": "ask", "modelo": model, "id": gid, "http": http, "segundos": seg}
    if http == 200:
        rec.update(abstained=abstained, citas_validas=list(validas), citas_invalidas=list(invalidas),
                   evidencia_citada=evid, threshold=0.8, repeat_penalty=1.1)
    else:
        rec["error"] = {"servicio": "ollama", "error": "Ollama devolvió HTTP 500."}
    return rec


ASKS = [
    ask("A", "G03", validas=[1, 2], evid=True, seg=20.0),       # cita válida y cita la evidencia
    ask("A", "G05", abstained=True, seg=1.0),                   # abstención correcta
    ask("B", "G03", http=503, seg=0.5),                         # error: cuenta como fallo
    ask("B", "G05", abstained=False, validas=[1], seg=30.0),    # no se abstuvo
    ask("C", "G03", validas=[], invalidas=[7], seg=40.0),       # sin cita válida, 1 inválida
    ask("C", "G05", abstained=True, seg=2.0),
]


@pytest.fixture()
def resultados(tmp_path):
    gold = tmp_path / "gold.csv"
    with gold.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "pregunta", "idioma", "tipo", "fuente_esperada", "tema", "respuesta_referencia",
                    "evidencia_doc_id", "split", "validada_por"])
        for gid, tipo, fuente, idioma, ev, split in GOLD:
            w.writerow([gid, f"pregunta {gid}", idioma, tipo, fuente, "", "r" if ev else "", ev, split, "pendiente"])
    runs = tmp_path / "runs.jsonl"
    runs.write_text("\n".join(json.dumps(r) for r in RETRIEVE + ASKS), encoding="utf-8")
    salida = tmp_path / "res.json"
    assert ar.main(["--runs", str(runs), "--gold", str(gold), "--salida", str(salida)]) == 0
    return json.loads(salida.read_text(encoding="utf-8"))


def test_solo_particion_de_prueba(resultados):
    assert resultados["preguntas"] == 2 and resultados["respondibles"] == 1 and resultados["no_respondibles"] == 1


def test_recuperacion_valores_exactos(resultados):
    r = resultados["recuperacion"]
    assert r["n"] == 1 and r["recall@5"] == 1.0 and r["mrr"] == 0.5  # evidencia en el rango 2 (tras deduplicar)
    assert r["ndcg@5"] == pytest.approx(1 / math.log2(3))


def test_error_cuenta_como_fallo_en_el_denominador(resultados):
    b = resultados["generacion"]["B"]
    assert b["corridas"] == 2 and b["exitosas"] == 1
    assert b["errores"] == [{"id": "G03", "http": 503, "segundos": 0.5, "servicio": "ollama"}]
    assert b["con_al_menos_una_cita_valida"] == 0 and b["pct_con_cita_valida"] == 0.0  # 0/1, no excluida
    assert b["abstencion_correcta"] == 0 and b["tiempo_medio_s"] == 30.0


def test_metricas_de_generacion(resultados):
    a, c = resultados["generacion"]["A"], resultados["generacion"]["C"]
    assert (a["con_al_menos_una_cita_valida"], a["cita_documento_evidencia"], a["abstencion_correcta"]) == (1, 1, 1)
    assert a["pct_citas_invalidas"] == 0.0 and a["abstencion_precision"] == 1.0 and a["abstencion_recall"] == 1.0
    assert a["tiempo_medio_s"] == 10.5 and a["tiempo_mediana_s"] == 10.5
    assert c["con_al_menos_una_cita_valida"] == 0 and c["citas_invalidas_total"] == 1 and c["pct_citas_invalidas"] == 1.0
    assert a["umbrales_registrados"] == [0.8] and a["repeat_penalty_registrado"] == [1.1]


def test_umbrales_complementarios(resultados):
    u = {x["umbral"]: x for x in resultados["analisis_complementario_no_usado_para_decision"]["umbrales"]}
    assert (u[0.80]["respondibles_respondidas"], u[0.80]["no_respondibles_abstenidas"]) == (1, 0)
    assert (u[0.8465]["respondibles_respondidas"], u[0.8465]["no_respondibles_abstenidas"]) == (1, 0)  # 0,85 ≥ 0,8465
    assert (u[0.876]["respondibles_respondidas"], u[0.876]["no_respondibles_abstenidas"]) == (1, 1)
