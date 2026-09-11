"""Construye los corpus raw y preprocesado para el Taller 3."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import spacy


ROOT = Path(__file__).resolve().parent
BOOK_CORPUS_DIR = ROOT / "corpus"
INTERVIEWS_PATH = ROOT / "entrevistas_all_2023-03-21_14-24_05.json"
DATA_DIR = ROOT / "data"
RAW_PATH = DATA_DIR / "corpus_raw.json"
PREPROCESSED_PATH = DATA_DIR / "corpus_preprocesado.json"
STATS_PATH = DATA_DIR / "estadisticas_preprocesamiento.json"


def cargar_libros():
    unidades = []
    for path in sorted(BOOK_CORPUS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        with path.open(encoding="utf-8") as archivo:
            registros = json.load(archivo)
        for posicion, registro in enumerate(registros):
            unidades.append({
                "id": f"libro:{registro['libro']}:{posicion:06d}",
                "tipo": "libro",
                "texto": registro.get("texto", ""),
                "metadatos": {
                    "libro": registro.get("libro"),
                    "parte": registro.get("parte"),
                    "capitulo": registro.get("capitulo"),
                    "titulo": registro.get("titulo"),
                    "subtitulo": registro.get("subtitulo"),
                    "es_relato": registro.get("es_relato", False),
                    "pie_de_pagina": registro.get("pie_de_pagina", False),
                    "origen": f"corpus/{path.name}",
                    "posicion_origen": posicion,
                },
            })
    return unidades


def cargar_entrevistas():
    with INTERVIEWS_PATH.open(encoding="utf-8") as archivo:
        registros = json.load(archivo)
    entrevistas = []
    for posicion, registro in enumerate(registros):
        entrevistas.append({
            "id": f"entrevista:{registro['id_doc']}",
            "tipo": "entrevista",
            "texto": registro.get("text", ""),
            "metadatos": {
                "id_doc": registro.get("id_doc"),
                "pages": registro.get("pages"),
                "origen": INTERVIEWS_PATH.name,
                "posicion_origen": posicion,
            },
        })
    return entrevistas


def normalizar_lemas(doc):
    tokens = []
    for token in doc:
        if token.is_space or token.is_punct or token.is_stop:
            continue
        lema = token.lemma_.strip().lower()
        if lema and re.search(r"\w", lema, flags=re.UNICODE):
            tokens.append(lema)
    return " ".join(tokens)


def construir_diccionario_lemas(nlp, textos):
    palabras = set()
    for texto in textos:
        palabras.update(re.findall(r"\b\w+\b", texto.lower(), flags=re.UNICODE))

    lemas = {}
    stopwords = nlp.Defaults.stop_words
    for palabra, doc in zip(sorted(palabras), nlp.pipe(sorted(palabras), batch_size=256)):
        token = doc[0]
        if palabra in stopwords or token.is_punct or token.is_space:
            continue
        lema = token.lemma_.strip().lower()
        if lema and re.search(r"\w", lema, flags=re.UNICODE):
            lemas[palabra] = lema
    return lemas, stopwords


def normalizar_texto(texto, lemas, stopwords):
    tokens = []
    stopwords_removidas = []
    tokens_originales = 0
    for palabra in re.findall(r"\b\w+\b", texto.lower(), flags=re.UNICODE):
        if palabra.isalpha():
            tokens_originales += 1
        if palabra in stopwords:
            stopwords_removidas.append(palabra)
        elif palabra in lemas:
            tokens.append(lemas[palabra])
    return " ".join(tokens), tokens_originales, stopwords_removidas


def escribir_json_atomico(path, contenido):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(path.suffix + ".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
    temporal.replace(path)


def construir_corpus(modelo):
    documentos = cargar_libros() + cargar_entrevistas()
    raw = {
        "version": 1,
        "descripcion": "Unidades segmentadas de libros y entrevistas completas.",
        "documentos": documentos,
    }
    escribir_json_atomico(RAW_PATH, raw)

    nlp = spacy.load(modelo, disable=["parser", "ner", "textcat"])
    preprocesados = []
    stopwords_por_tipo = {
        "libro": Counter(),
        "entrevista": Counter(),
    }
    tokens_por_documento = {}
    documentos_vacios = []
    textos = [documento["texto"] for documento in documentos]
    lemas, stopwords = construir_diccionario_lemas(nlp, textos)
    for documento in documentos:
        texto_preprocesado, tokens_originales, removidas = normalizar_texto(
            documento["texto"], lemas, stopwords
        )
        tokens_finales = len(texto_preprocesado.split())
        tipo = documento["tipo"]
        stopwords_por_tipo[tipo].update(removidas)
        tokens_por_documento[documento["id"]] = {
            "tokens_originales": tokens_originales,
            "tokens_finales": tokens_finales,
            "tipo": tipo,
        }
        if tokens_finales == 0:
            documentos_vacios.append(documento["id"])
        preprocesados.append({
            "id": documento["id"],
            "tipo": tipo,
            "texto_preprocesado": texto_preprocesado,
            "metadatos": documento["metadatos"],
        })

    preprocesado = {
        "version": 1,
        "modelo": modelo,
        "reglas": {
            "minusculas": True,
            "puntuacion": "eliminada",
            "stopwords": "spaCy español",
            "lematizacion": True,
        },
        "documentos": preprocesados,
    }
    escribir_json_atomico(PREPROCESSED_PATH, preprocesado)
    estadisticas = {
        "version": 1,
        "modelo": modelo,
        "stopwords_top50_libros": [
            list(item) for item in stopwords_por_tipo["libro"].most_common(50)
        ],
        "stopwords_top50_entrevistas": [
            list(item) for item in stopwords_por_tipo["entrevista"].most_common(50)
        ],
        "tokens_por_documento": tokens_por_documento,
        "documentos_vacios_tras_limpieza": documentos_vacios,
    }
    escribir_json_atomico(STATS_PATH, estadisticas)
    imprimir_resumen(estadisticas)
    return len(documentos), len(preprocesados)


def imprimir_resumen(estadisticas):
    print("\n=== Resumen de preprocesamiento ===")
    for tipo in ("libro", "entrevista"):
        registros = [
            datos for datos in estadisticas["tokens_por_documento"].values()
            if datos["tipo"] == tipo
        ]
        originales = sum(datos["tokens_originales"] for datos in registros)
        finales = sum(datos["tokens_finales"] for datos in registros)
        reduccion = (1 - finales / originales) * 100 if originales else 0
        top20 = estadisticas[f"stopwords_top50_{tipo}s"][:20]
        print(f"{tipo}: reducción promedio ponderada = {reduccion:.2f}%")
        print(f"{tipo}: top-20 stopwords removidas = {top20}")
    print(
        "Documentos vacíos tras la limpieza: "
        f"{len(estadisticas['documentos_vacios_tras_limpieza'])}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", default="es_core_news_md")
    args = parser.parse_args()
    total_raw, total_preprocesados = construir_corpus(args.modelo)
    print(f"Documentos raw: {total_raw}")
    print(f"Documentos preprocesados: {total_preprocesados}")
    print(f"Raw: {RAW_PATH}")
    print(f"Preprocesado: {PREPROCESSED_PATH}")


if __name__ == "__main__":
    main()