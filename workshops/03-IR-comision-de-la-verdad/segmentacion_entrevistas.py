"""Segmenta las entrevistas en pasajes para usarlos como consultas.

POR QUÉ EXISTE ESTE PASO

La actividad 3 usó cada entrevista completa como consulta y el ranking
colapsó: una entrevista aporta ~1.128 términos distintos sobre un vocabulario
de 15.950, así que se parece un poco a todo y el modelo devuelve casi las
mismas unidades a todas las consultas (ver 6.4 de docs/bitacora-taller.md). La
normalización de longitud corrigió parte del sesgo pero no la causa (6.5).

Este script ataca la causa: en lugar de una consulta de ~4.100 tokens
preprocesados, varias consultas cortas y temáticamente coherentes.

CÓMO SE SEGMENTA

Las transcripciones traen estructura de turnos: cada línea que empieza con una
etiqueta de hablante ("TEST:", "ENT:", "ENT1:", "INF2:") abre una intervención.
Son las mismas marcas que el análisis exploratorio descartó como ruido léxico;
como estructura, en cambio, valen: dan ~282 turnos por entrevista.

- Turnos del **testigo** (cualquier etiqueta que no sea ENT*): son el 81,7 % de
  los tokens y el contenido que interesa recuperar.
- Turnos del **entrevistador** (ENT*): se descartan por defecto. Son preguntas
  del protocolo de la Comisión, prácticamente iguales en todas las entrevistas,
  así que aportan vocabulario compartido que empuja justo hacia el problema que
  se quiere resolver. `--incluir-entrevistador` permite medir la diferencia.
- Un turno suelto es demasiado corto para ser consulta (mediana 11 tokens, el
  30 % tiene 5 o menos), así que se **agrupan turnos consecutivos** hasta
  alcanzar el tamaño objetivo, y los turnos enormes se parten en trozos de ese
  mismo tamaño. Los límites de turno siempre se respetan.

SALIDA
    data/corpus_pasajes.json — un registro por pasaje, con su texto
    preprocesado (mismas reglas que preprocesar_corpus.py) y un fragmento del
    texto crudo como evidencia.

Uso:
    .venv/bin/python segmentacion_entrevistas.py
    .venv/bin/python segmentacion_entrevistas.py --tokens-objetivo 80
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import spacy

from preprocesar_corpus import (
    construir_diccionario_lemas,
    localizar_entrevistas,
    normalizar_texto,
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SALIDA_PATH = DATA_DIR / "corpus_pasajes.json"

# Etiqueta de hablante al inicio de línea: TEST:, ENT:, ENT1:, INF2:, TES.
PATRON_TURNO = re.compile(r"(?m)^[ \t]*([A-ZÁÉÍÓÚÑ]{2,6}\d{0,2})[ \t]*[:.](?=\s)")
PREFIJO_ENTREVISTADOR = "ENT"

TOKENS_OBJETIVO = 150
LARGO_FRAGMENTO = 240


def partir_en_turnos(texto):
    """[(etiqueta, texto)] del turno. Lo previo al primer turno se descarta:
    es el encabezado del acta, no habla de nadie."""
    marcas = list(PATRON_TURNO.finditer(texto))
    turnos = []
    for posicion, marca in enumerate(marcas):
        fin = marcas[posicion + 1].start() if posicion + 1 < len(marcas) else len(texto)
        contenido = texto[marca.end() : fin].strip()
        if contenido:
            turnos.append((marca.group(1), contenido))
    return turnos


def es_entrevistador(etiqueta):
    return etiqueta.startswith(PREFIJO_ENTREVISTADOR)


def agrupar_en_pasajes(turnos, tokens_objetivo, incluir_entrevistador):
    """Agrupa turnos consecutivos hasta el tamaño objetivo, sin cruzar turnos."""
    pasajes, actual, tamano = [], [], 0

    def cerrar():
        nonlocal actual, tamano
        if actual:
            pasajes.append(" ".join(actual))
            actual, tamano = [], 0

    for etiqueta, contenido in turnos:
        if es_entrevistador(etiqueta) and not incluir_entrevistador:
            continue
        palabras = contenido.split()
        # un turno más largo que el objetivo se parte en trozos de ese tamaño
        for inicio in range(0, len(palabras), tokens_objetivo):
            trozo = palabras[inicio : inicio + tokens_objetivo]
            actual.append(" ".join(trozo))
            tamano += len(trozo)
            if tamano >= tokens_objetivo:
                cerrar()
    cerrar()
    return pasajes


def construir_pasajes(entrevistas, tokens_objetivo, incluir_entrevistador):
    registros, sin_turnos = [], []
    for entrevista in entrevistas:
        texto = entrevista.get("text", "")
        turnos = partir_en_turnos(texto)
        if not turnos:
            # sin etiquetas de hablante: la entrevista entera es un solo bloque
            # y se parte por tamaño, para no perderla
            sin_turnos.append(entrevista["id_doc"])
            turnos = [("TEST", texto)]
        for posicion, pasaje in enumerate(
            agrupar_en_pasajes(turnos, tokens_objetivo, incluir_entrevistador)
        ):
            registros.append({
                "id": f"pasaje:{entrevista['id_doc']}:{posicion:04d}",
                "entrevista": f"entrevista:{entrevista['id_doc']}",
                "indice": posicion,
                "texto": pasaje,
            })
    return registros, sin_turnos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", default="es_core_news_md")
    parser.add_argument("--tokens-objetivo", type=int, default=TOKENS_OBJETIVO,
                        help="tamaño al que se agrupan los turnos (%(default)s)")
    parser.add_argument("--incluir-entrevistador", action="store_true",
                        help="conservar también los turnos ENT* (preguntas)")
    args = parser.parse_args()

    path = localizar_entrevistas()
    if path is None:
        raise SystemExit(
            "no se encontró el corpus de entrevistas; ver preprocesar_corpus.py --help"
        )
    with path.open(encoding="utf-8") as archivo:
        entrevistas = json.load(archivo)

    registros, sin_turnos = construir_pasajes(
        entrevistas, args.tokens_objetivo, args.incluir_entrevistador
    )
    print(f"Entrevistas: {len(entrevistas)}  (sin etiquetas de turno: {len(sin_turnos)})")
    print(f"Pasajes: {len(registros)}")

    # mismas reglas de preprocesamiento que el resto del corpus
    nlp = spacy.load(args.modelo, disable=["parser", "ner", "textcat"])
    lemas, stopwords = construir_diccionario_lemas(nlp, [r["texto"] for r in registros])

    documentos, vacios = [], 0
    for registro in registros:
        preprocesado, _, _ = normalizar_texto(registro["texto"], lemas, stopwords)
        if not preprocesado:
            vacios += 1
        texto = " ".join(registro["texto"].split())
        documentos.append({
            "id": registro["id"],
            "entrevista": registro["entrevista"],
            "indice": registro["indice"],
            "texto_preprocesado": preprocesado,
            "fragmento": texto[:LARGO_FRAGMENTO] + "…" if len(texto) > LARGO_FRAGMENTO else texto,
        })

    longitudes = np.array([len(d["texto_preprocesado"].split()) for d in documentos])
    conteo = Counter(d["entrevista"] for d in documentos)
    por_entrevista = np.array(list(conteo.values()))

    salida = {
        "version": 1,
        "parametros": {
            "modelo": args.modelo,
            "tokens_objetivo": args.tokens_objetivo,
            "incluye_entrevistador": args.incluir_entrevistador,
            "regla": "turnos consecutivos agrupados hasta el tamaño objetivo",
        },
        "resumen": {
            "entrevistas": len(entrevistas),
            "entrevistas_sin_etiquetas_de_turno": len(sin_turnos),
            "pasajes": len(documentos),
            "pasajes_vacios_tras_preprocesar": vacios,
            "tokens_por_pasaje": {
                "media": float(longitudes.mean()),
                "mediana": float(np.median(longitudes)),
                "p90": float(np.percentile(longitudes, 90)),
            },
            "pasajes_por_entrevista": {
                "media": float(por_entrevista.mean()),
                "mediana": float(np.median(por_entrevista)),
                "max": int(por_entrevista.max()),
            },
        },
        "documentos": documentos,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporal = SALIDA_PATH.with_suffix(".json.tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)
    temporal.replace(SALIDA_PATH)

    resumen = salida["resumen"]
    print(f"Tokens preprocesados por pasaje: media "
          f"{resumen['tokens_por_pasaje']['media']:.1f}, mediana "
          f"{resumen['tokens_por_pasaje']['mediana']:.0f}")
    print(f"Pasajes por entrevista: media "
          f"{resumen['pasajes_por_entrevista']['media']:.1f}, máximo "
          f"{resumen['pasajes_por_entrevista']['max']}")
    print(f"Pasajes vacíos tras preprocesar: {vacios}")
    print(f"Guardado en: {SALIDA_PATH}")


if __name__ == "__main__":
    main()
