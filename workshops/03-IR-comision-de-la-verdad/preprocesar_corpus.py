"""Construye los corpus raw y preprocesado para el Taller 3."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import spacy


ROOT = Path(__file__).resolve().parent
BOOK_CORPUS_DIR = ROOT / "corpus"
NOMBRE_ENTREVISTAS = "entrevistas_all_2023-03-21_14-24_05.json"
INTERVIEWS_DIR = ROOT / "entrevistas"
# el archivo de entrevistas se busca en entrevistas/, en la carpeta del taller
# y en corpus/
RUTAS_ENTREVISTAS = (
    INTERVIEWS_DIR / NOMBRE_ENTREVISTAS,
    ROOT / NOMBRE_ENTREVISTAS,
    BOOK_CORPUS_DIR / NOMBRE_ENTREVISTAS,
)
DATA_DIR = ROOT / "data"
RAW_PATH = DATA_DIR / "corpus_raw.json"
PREPROCESSED_PATH = DATA_DIR / "corpus_preprocesado.json"
STATS_PATH = DATA_DIR / "estadisticas_preprocesamiento.json"


def localizar_entrevistas():
    """Primera ruta conocida donde exista el corpus de entrevistas, o None."""
    for path in RUTAS_ENTREVISTAS:
        if path.exists():
            return path
    return None


def es_corpus_de_libro(registros):
    return isinstance(registros, list) and bool(registros) and "libro" in registros[0]


def cargar_libros():
    unidades = []
    for path in sorted(BOOK_CORPUS_DIR.glob("*.json")):
        if path.name.startswith("_") or path.name == NOMBRE_ENTREVISTAS:
            continue
        with path.open(encoding="utf-8") as archivo:
            registros = json.load(archivo)
        if not es_corpus_de_libro(registros):
            print(f"[aviso] {path.name} no tiene forma de corpus de libro: se omite")
            continue
        # el nombre del libro es el del archivo, no el del campo: un corpus
        # segmentado con otra herramienta puede traer ahí el nombre del PDF
        # ("X.pdf") y eso rompería la convención de ids y el agrupamiento
        nombre_libro = path.stem
        for posicion, registro in enumerate(registros):
            unidades.append({
                # el id lo asigna la segmentación; se recalcula solo para
                # corpus generados antes de que existiera el campo
                "id": registro.get("id") or f"libro:{nombre_libro}:{posicion:06d}",
                "tipo": "libro",
                "texto": registro.get("texto", ""),
                "metadatos": {
                    "libro": nombre_libro,
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


def cargar_entrevistas(path):
    with path.open(encoding="utf-8") as archivo:
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
                "origen": path.name,
                "posicion_origen": posicion,
            },
        })
    return entrevistas


# Las notas al pie de los libros citan URLs. El tokenizador las parte en
# fragmentos ("https", "www", "co", el dominio) que entran al índice como si
# fueran términos. Se eliminan del texto ANTES de tokenizar: el corpus raw las
# conserva intactas, el preprocesado —que es el que se indexa— no.
PATRON_URL = re.compile(r"https?://\S+|www\.\S+", flags=re.IGNORECASE)


def tokenizar_para_indice(texto):
    """Tokens del texto que se va a indexar, sin URLs."""
    sin_urls = PATRON_URL.sub(" ", texto)
    return re.findall(r"\b\w+\b", sin_urls.lower(), flags=re.UNICODE)


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
        palabras.update(tokenizar_para_indice(texto))

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
    for palabra in tokenizar_para_indice(texto):
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


def construir_corpus(modelo, path_entrevistas):
    """path_entrevistas=None genera solo la parte de libros (corpus incompleto)."""
    documentos = cargar_libros()
    if path_entrevistas is not None:
        documentos += cargar_entrevistas(path_entrevistas)
    raw = {
        "version": 1,
        "descripcion": "Unidades segmentadas de libros y entrevistas completas.",
        "entrevistas_incluidas": path_entrevistas is not None,
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
        "entrevistas_incluidas": path_entrevistas is not None,
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
        "entrevistas_incluidas": path_entrevistas is not None,
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
        if not registros:
            print(f"{tipo}: sin documentos procesados")
            continue
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
    parser.add_argument(
        "--entrevistas",
        type=Path,
        default=None,
        help=(
            f"ruta al JSON de entrevistas; por defecto se busca {NOMBRE_ENTREVISTAS} "
            "en entrevistas/, en la carpeta del taller y en corpus/"
        ),
    )
    parser.add_argument(
        "--sin-entrevistas",
        action="store_true",
        help=(
            "genera solo la parte de libros; los archivos de data/ quedan "
            "marcados con entrevistas_incluidas=false"
        ),
    )
    args = parser.parse_args()

    if args.sin_entrevistas:
        path_entrevistas = None
        print(
            "[aviso] corpus PARCIAL: solo libros. Los archivos de data/ quedan "
            "con entrevistas_incluidas=false y no sirven para la comparación "
            "entrevista-libro que pide el taller."
        )
    else:
        path_entrevistas = args.entrevistas or localizar_entrevistas()
        if path_entrevistas is None:
            buscadas = "\n".join(f"    - {ruta}" for ruta in RUTAS_ENTREVISTAS)
            parser.error(
                "no se encontró el corpus de entrevistas. Rutas buscadas:\n"
                f"{buscadas}\n"
                "  Es un archivo de datos del taller y no está versionado en el "
                "repositorio; corpus/ solo contiene los libros segmentados.\n"
                "  Opciones:\n"
                "    - copiarlo a una de esas rutas,\n"
                "    - indicar dónde está con --entrevistas RUTA,\n"
                "    - o generar solo la parte de libros con --sin-entrevistas."
            )
        if not path_entrevistas.exists():
            parser.error(f"no existe el archivo de entrevistas: {path_entrevistas}")

    total_raw, total_preprocesados = construir_corpus(args.modelo, path_entrevistas)
    print(f"Documentos raw: {total_raw}")
    print(f"Documentos preprocesados: {total_preprocesados}")
    print(f"Raw: {RAW_PATH}")
    print(f"Preprocesado: {PREPROCESSED_PATH}")


if __name__ == "__main__":
    main()