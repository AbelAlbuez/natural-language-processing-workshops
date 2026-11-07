"""Valida el gold standard (estructura, valores, evidencia, duplicados, cuotas y temas).

Uso:
    python -m scripts.validar_gold_standard \
        --gold docs/gold_standard.csv \
        --documentos data/documentos_rag.parquet \
        --cuotas cuotas.json --temas temas.json

--cuotas: JSON {"estratos": [{"fuente_esperada": "bluesky", "idioma": "en",
          "desarrollo": 5, "prueba": 4}, ...]}
--temas:  JSON con una lista de etiquetas, o texto con una etiqueta por línea
          (las 18 de collection_keyword_label).

Cada verificación imprime OK o FALLA con conteos; nunca imprime texto de preguntas ni
respuestas. El resumen se guarda en data/validacion_gold.json (solo conteos y
resultados). Sale con código 1 si alguna verificación falla.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

COLUMNAS = ["id", "pregunta", "idioma", "tipo", "fuente_esperada", "tema",
            "respuesta_referencia", "evidencia_doc_id", "split"]
IDIOMAS = {"es", "en"}
TIPOS = {"sintetica", "manual", "no_respondible"}
FUENTES = {"bluesky", "media_cloud", "gdelt"}
SPLITS = {"desarrollo", "prueba"}
SEPARADOR_EVIDENCIA = re.compile(r"[;|]")


def leer_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        columnas = list(reader.fieldnames or [])
        filas = [{k: (v or "").strip() for k, v in row.items() if k is not None} for row in reader]
    return columnas, filas


def leer_temas(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        temas = json.loads(text)
    except json.JSONDecodeError:
        temas = [line.strip() for line in text.splitlines() if line.strip()]
    if not isinstance(temas, list) or not all(isinstance(t, str) for t in temas):
        raise SystemExit("--temas debe ser una lista JSON de cadenas o un texto con un tema por línea.")
    return temas


def leer_cuotas(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cuotas = {}
    for e in data["estratos"]:
        key = (e["fuente_esperada"], e["idioma"])
        cuotas[key] = {"desarrollo": int(e["desarrollo"]), "prueba": int(e["prueba"])}
    return cuotas


def leer_document_ids(path):
    import pyarrow.parquet as pq

    return set(pq.read_table(path, columns=["document_id"])["document_id"].to_pylist())


def normalizar(texto):
    return re.sub(r"\s+", " ", texto).strip().casefold()


def evidencias(valor):
    return [v.strip() for v in SEPARADOR_EVIDENCIA.split(valor) if v.strip()]


def check(nombre, ok, **conteos):
    return {"verificacion": nombre, "ok": bool(ok), **conteos}


def validar(columnas, filas, document_ids, cuotas, temas, filas_esperadas=40, min_no_respondible=5):
    """Devuelve la lista de verificaciones. Columnas ausentes se tratan como vacías."""
    get = lambda fila, col: fila.get(col, "")  # noqa: E731
    resultados = []

    faltan = [c for c in COLUMNAS if c not in columnas]
    resultados.append(check("columnas_obligatorias", not faltan, faltantes=len(faltan),
                            columnas_faltantes=faltan))

    ids = [get(f, "id") for f in filas]
    esperados = {f"G{i:02d}" for i in range(1, filas_esperadas + 1)}
    duplicados = sum(c - 1 for c in Counter(ids).values() if c > 1)
    fuera = sum(1 for i in ids if i not in esperados)
    ausentes = len(esperados - set(ids))
    resultados.append(check("filas_e_ids", len(filas) == filas_esperadas and not duplicados and not fuera
                            and not ausentes, filas=len(filas), esperadas=filas_esperadas,
                            ids_duplicados=duplicados, ids_fuera_de_rango=fuera, ids_ausentes=ausentes))

    for col, validos in (("idioma", IDIOMAS), ("tipo", TIPOS), ("fuente_esperada", FUENTES),
                         ("split", SPLITS), ("tema", set(temas))):
        vacios = sum(1 for f in filas if not get(f, col))
        invalidos = sum(1 for f in filas if get(f, col) and get(f, col) not in validos)
        resultados.append(check(f"valores_{col}", not vacios and not invalidos, vacios=vacios, invalidos=invalidos))

    vacias = sum(1 for f in filas if not get(f, "pregunta"))
    resultados.append(check("pregunta_no_vacia", not vacias, vacias=vacias))

    respondibles = [f for f in filas if get(f, "tipo") != "no_respondible"]
    sin_respuesta = sum(1 for f in respondibles if not get(f, "respuesta_referencia"))
    resultados.append(check("respuesta_en_respondibles", not sin_respuesta,
                            respondibles=len(respondibles), sin_respuesta=sin_respuesta))

    sin_evidencia = sum(1 for f in respondibles if not evidencias(get(f, "evidencia_doc_id")))
    inexistentes = sum(1 for f in respondibles for d in evidencias(get(f, "evidencia_doc_id"))
                       if d not in document_ids)
    no_resp_con_evidencia = sum(1 for f in filas if get(f, "tipo") == "no_respondible"
                                and get(f, "evidencia_doc_id"))
    resultados.append(check("evidencia_doc_id", not sin_evidencia and not inexistentes and not no_resp_con_evidencia,
                            respondibles_sin_evidencia=sin_evidencia, ids_inexistentes=inexistentes,
                            no_respondibles_con_evidencia=no_resp_con_evidencia))

    normalizadas = [normalizar(get(f, "pregunta")) for f in filas if get(f, "pregunta")]
    dup_preguntas = sum(c - 1 for c in Counter(normalizadas).values() if c > 1)
    resultados.append(check("preguntas_sin_duplicados", not dup_preguntas, duplicadas=dup_preguntas,
                            evaluadas=len(normalizadas)))

    reales = Counter((get(f, "fuente_esperada"), get(f, "idioma"), get(f, "split")) for f in filas)
    estratos_mal = 0
    for (fuente, idioma), esperado in cuotas.items():
        for split in SPLITS:
            if reales.get((fuente, idioma, split), 0) != esperado.get(split, 0):
                estratos_mal += 1
    fuera_de_tabla = sum(n for (fuente, idioma, _), n in reales.items() if (fuente, idioma) not in cuotas)
    resultados.append(check("cuotas_split", not estratos_mal and not fuera_de_tabla,
                            celdas_con_diferencia=estratos_mal, celdas_esperadas=len(cuotas) * len(SPLITS),
                            filas_fuera_de_tabla=fuera_de_tabla))

    n_no_resp = sum(1 for f in filas if get(f, "tipo") == "no_respondible")
    resultados.append(check("minimo_no_respondible", n_no_resp >= min_no_respondible,
                            no_respondibles=n_no_resp, minimo=min_no_respondible))

    presentes = {get(f, "tema") for f in filas}
    temas_ausentes = sum(1 for t in temas if t not in presentes)
    resultados.append(check("cobertura_temas", not temas_ausentes, temas=len(temas),
                            temas_ausentes=temas_ausentes))
    return resultados


def imprimir(resultados):
    ancho = max(len(r["verificacion"]) for r in resultados)
    print(f"{'Verificación'.ljust(ancho)}  Resultado  Conteos")
    for r in resultados:
        conteos = ", ".join(f"{k}={v}" for k, v in r.items() if k not in ("verificacion", "ok"))
        print(f"{r['verificacion'].ljust(ancho)}  {'OK' if r['ok'] else 'FALLA':<9}  {conteos}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", default="docs/gold_standard.csv")
    parser.add_argument("--documentos", default="data/documentos_rag.parquet")
    parser.add_argument("--cuotas", required=True, help="JSON con las cuotas de split por fuente e idioma.")
    parser.add_argument("--temas", required=True, help="Lista de las etiquetas de tema (JSON o una por línea).")
    parser.add_argument("--filas-esperadas", type=int, default=40)
    parser.add_argument("--min-no-respondible", type=int, default=5)
    parser.add_argument("--salida", default="data/validacion_gold.json")
    args = parser.parse_args(argv)

    columnas, filas = leer_csv(args.gold)
    resultados = validar(columnas, filas, leer_document_ids(args.documentos), leer_cuotas(args.cuotas),
                         leer_temas(args.temas), args.filas_esperadas, args.min_no_respondible)
    imprimir(resultados)
    ok = all(r["ok"] for r in resultados)
    resumen = {
        "gold": Path(args.gold).name,
        "filas": len(filas),
        "verificaciones": len(resultados),
        "ok": sum(r["ok"] for r in resultados),
        "fallas": sum(not r["ok"] for r in resultados),
        "aprobado": ok,
        "resultados": resultados,
    }
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'APROBADO' if ok else 'NO APROBADO'}: {resumen['ok']} OK, {resumen['fallas']} FALLA. Detalle: {salida}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
