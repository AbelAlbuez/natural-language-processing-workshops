"""Modelo de recuperación TF-IDF del Taller 3 (actividad 3 del enunciado).

Relaciona cada **entrevista** (consulta) con las **unidades de libro**
(documentos) por similitud coseno sobre vectores TF-IDF, y agrega el resultado
al nivel de libro para el cuadro y el heatmap de la actividad 5.

DECISIONES DEL MODELO (registradas en docs/bitacora-taller.md)

- Documentos: unidades de libro **sin las notas al pie**. Las notas son
  mayormente referencias bibliográficas; coinciden con las entrevistas por
  apellidos y topónimos, no por contenido narrativo. Siguen en el corpus, solo
  no se indexan.
- Consultas: cada entrevista completa.
- Se excluye del índice el **ruido de formato** (vocabulario.py): etiquetas de
  hablante, marcas de transcripción, dígitos y restos de URL. Su IDF ya sería
  casi cero por aparecer en todas las entrevistas, pero infla la longitud del
  documento, que es justo lo que BM25 normaliza en la actividad 4.
- Corte de vocabulario `MIN_DF = 2`: un término que aparece en un solo
  documento no puede emparejar nada. El análisis exploratorio midió que el
  36 % del vocabulario de libros son hapax.

PESADO (implementado aquí, sin sklearn, para que la actividad 4 reutilice
estas mismas estructuras)

    tf   = 1 + log(frecuencia del término en el documento)
    idf  = log((1 + N) / (1 + df)) + 1        (suavizado: ningún idf es 0)
    peso = tf * idf, con normalización L2 por documento

Con los vectores normalizados en L2, la similitud coseno es el producto punto,
así que el ranking es un producto de matrices dispersas.

Uso:
    .venv/bin/python modelo_ir.py
    .venv/bin/python modelo_ir.py --top 50 --min-df 3
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse

from vocabulario import es_ruido_de_formato

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_PATH = DATA_DIR / "corpus_raw.json"
PREPROCESSED_PATH = DATA_DIR / "corpus_preprocesado.json"
SALIDA_PATH = DATA_DIR / "ranking_tfidf.json"

MIN_DF = 2
TOP_UNIDADES = 20          # unidades que se guardan por entrevista
TOP_POR_LIBRO_AGREGADO = 10  # cuántas unidades suma cada libro (decisión de agregación)
LARGO_FRAGMENTO = 240      # caracteres del texto crudo que se guardan como evidencia
BLOQUE_CONSULTAS = 128     # consultas por bloque: acota la matriz densa intermedia


def cargar_documentos_y_consultas():
    """Documentos indexables (unidades de libro sin notas) y consultas."""
    with PREPROCESSED_PATH.open(encoding="utf-8") as archivo:
        corpus = json.load(archivo)

    documentos, consultas, descartados = [], [], Counter()
    for registro in corpus["documentos"]:
        tokens = [t for t in registro["texto_preprocesado"].split() if not es_ruido_de_formato(t)]
        if registro["tipo"] == "libro":
            if registro["metadatos"].get("pie_de_pagina"):
                descartados["nota_al_pie"] += 1
                continue
            if not tokens:
                descartados["sin_terminos"] += 1
                continue
            documentos.append({"id": registro["id"], "tokens": tokens,
                               "metadatos": registro["metadatos"]})
        else:
            if not tokens:
                descartados["consulta_vacia"] += 1
                continue
            consultas.append({"id": registro["id"], "tokens": tokens,
                              "metadatos": registro["metadatos"]})
    return documentos, consultas, descartados, corpus.get("modelo")


def construir_vocabulario(documentos, min_df):
    """Términos con df >= min_df, con su idf suavizado.

    El vocabulario y el idf salen SOLO de los documentos: una consulta no puede
    cambiar el peso de un término del índice.
    """
    df = Counter()
    for documento in documentos:
        df.update(set(documento["tokens"]))

    terminos = sorted(t for t, cuenta in df.items() if cuenta >= min_df)
    indice = {termino: i for i, termino in enumerate(terminos)}
    total = len(documentos)
    idf = np.array(
        [math.log((1 + total) / (1 + df[t])) + 1 for t in terminos], dtype=np.float64
    )
    return indice, idf, df


def matriz_tfidf(textos_tokenizados, indice, idf):
    """Matriz dispersa (documentos x términos) con tf-idf normalizado en L2."""
    filas, columnas, valores = [], [], []
    for fila, tokens in enumerate(textos_tokenizados):
        cuentas = Counter(t for t in tokens if t in indice)
        if not cuentas:
            continue
        for termino, cuenta in cuentas.items():
            columna = indice[termino]
            filas.append(fila)
            columnas.append(columna)
            valores.append((1.0 + math.log(cuenta)) * idf[columna])

    matriz = sparse.csr_matrix(
        (valores, (filas, columnas)),
        shape=(len(textos_tokenizados), len(indice)),
        dtype=np.float64,
    )
    normas = np.sqrt(matriz.multiply(matriz).sum(axis=1)).A.ravel()
    normas[normas == 0] = 1.0
    return sparse.diags(1.0 / normas) @ matriz


def top_k_de_fila(similitudes_fila, k):
    """Índices de los k mayores, ya ordenados de mayor a menor.

    argpartition evita ordenar las ~40.000 columnas para quedarse con k.
    """
    k = min(k, similitudes_fila.size)
    candidatos = np.argpartition(-similitudes_fila, k - 1)[:k]
    return candidatos[np.argsort(-similitudes_fila[candidatos])]


def agregar_por_libro(similitudes_fila, libros_por_documento, libros, top_por_libro):
    """Puntaje de cada libro = suma de sus `top_por_libro` mejores unidades.

    Alternativas descartadas: el máximo deja que una coincidencia aislada
    defina el vínculo, y el promedio sobre todas las unidades castiga a los
    libros grandes (de 277 a 12.288 unidades).
    """
    agregados = {}
    for libro in libros:
        mascara = libros_por_documento == libro
        valores = similitudes_fila[mascara]
        if valores.size == 0:
            agregados[libro] = 0.0
            continue
        k = min(top_por_libro, valores.size)
        mejores = np.partition(valores, -k)[-k:]
        agregados[libro] = float(mejores.sum())
    return agregados


def diagnosticar(resultados):
    """Señales de que el ranking discrimina entre consultas, o de que no.

    Con consultas de ~4.100 tokens y documentos de ~18, la similitud coseno
    tiende a premiar a unos pocos documentos cortos y genéricos para TODAS las
    consultas. Estas cifras hacen visible ese colapso: si el número de
    documentos distintos en el top-1 es mucho menor que el de consultas, el
    modelo no está discriminando por tema.
    """
    mejores = np.array([r["unidades"][0]["score"] for r in resultados])
    top1 = Counter(r["unidades"][0]["id"] for r in resultados)
    en_top = Counter(u["id"] for r in resultados for u in r["unidades"])
    return {
        "consultas": len(resultados),
        "unidades_distintas_en_top1": len(top1),
        "unidades_distintas_en_el_top_guardado": len(en_top),
        "consultas_del_documento_top1_mas_repetido": top1.most_common(1)[0][1],
        "documento_top1_mas_repetido": top1.most_common(1)[0][0],
        "score_top1": {
            "media": float(mejores.mean()),
            "mediana": float(np.median(mejores)),
            "min": float(mejores.min()),
            "max": float(mejores.max()),
        },
        "consultas_cuyo_top1_es_testimonio": sum(
            1 for r in resultados if r["unidades"][0]["es_relato"]
        ),
    }


def cargar_fragmentos(ids_necesarios):
    """Fragmento del texto crudo de cada unidad, como evidencia del ranking."""
    if not RAW_PATH.exists():
        return {}
    with RAW_PATH.open(encoding="utf-8") as archivo:
        raw = json.load(archivo)
    fragmentos = {}
    for documento in raw["documentos"]:
        if documento["id"] in ids_necesarios:
            texto = " ".join(documento["texto"].split())
            fragmentos[documento["id"]] = (
                texto[:LARGO_FRAGMENTO] + "…" if len(texto) > LARGO_FRAGMENTO else texto
            )
    return fragmentos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=TOP_UNIDADES,
                        help="unidades guardadas por entrevista (%(default)s)")
    parser.add_argument("--min-df", type=int, default=MIN_DF,
                        help="frecuencia de documento mínima de un término (%(default)s)")
    parser.add_argument("--sin-fragmentos", action="store_true",
                        help="no guardar el texto de evidencia (salida más liviana)")
    args = parser.parse_args()

    documentos, consultas, descartados, modelo = cargar_documentos_y_consultas()
    print(f"Documentos indexables: {len(documentos)}  (descartados: {dict(descartados)})")
    print(f"Consultas: {len(consultas)}")

    indice, idf, df = construir_vocabulario(documentos, args.min_df)
    print(f"Vocabulario: {len(indice)} términos con df >= {args.min_df} "
          f"(de {len(df)} distintos)")

    documentos_m = matriz_tfidf([d["tokens"] for d in documentos], indice, idf)
    consultas_m = matriz_tfidf([c["tokens"] for c in consultas], indice, idf)
    print(f"Matriz documentos: {documentos_m.shape}, {documentos_m.nnz} no-ceros")
    print(f"Matriz consultas:  {consultas_m.shape}, {consultas_m.nnz} no-ceros")

    libros_por_documento = np.array([d["metadatos"]["libro"] for d in documentos])
    libros = sorted(set(libros_por_documento.tolist()))

    # un solo producto por bloque: de cada fila salen el top-k y la agregación
    # por libro, que necesita la fila completa y no solo el top-k
    resultados = []
    for inicio in range(0, consultas_m.shape[0], BLOQUE_CONSULTAS):
        bloque = (consultas_m[inicio : inicio + BLOQUE_CONSULTAS] @ documentos_m.T).toarray()
        for desplazamiento in range(bloque.shape[0]):
            fila = inicio + desplazamiento
            similitudes = bloque[desplazamiento]
            resultados.append({
                "consulta": consultas[fila]["id"],
                "pages": consultas[fila]["metadatos"].get("pages"),
                "unidades": [
                    {
                        "id": documentos[pos]["id"],
                        "score": float(similitudes[pos]),
                        "libro": documentos[pos]["metadatos"]["libro"],
                        "parte": documentos[pos]["metadatos"]["parte"],
                        "capitulo": documentos[pos]["metadatos"]["capitulo"],
                        "titulo": documentos[pos]["metadatos"]["titulo"],
                        "es_relato": documentos[pos]["metadatos"]["es_relato"],
                    }
                    for pos in map(int, top_k_de_fila(similitudes, args.top))
                ],
                "libros": agregar_por_libro(
                    similitudes, libros_por_documento, libros, TOP_POR_LIBRO_AGREGADO,
                ),
            })
        print(f"  consultas procesadas: {min(inicio + BLOQUE_CONSULTAS, len(consultas))}"
              f"/{len(consultas)}", end="\r")
    print()

    if not args.sin_fragmentos:
        necesarios = {u["id"] for r in resultados for u in r["unidades"]}
        fragmentos = cargar_fragmentos(necesarios)
        for resultado in resultados:
            for unidad in resultado["unidades"]:
                unidad["fragmento"] = fragmentos.get(unidad["id"], "")

    salida = {
        "version": 1,
        "modelo_lematizacion": modelo,
        "parametros": {
            "pesado": "tf=1+log(f), idf=log((1+N)/(1+df))+1, normalización L2, coseno",
            "min_df": args.min_df,
            "top_unidades_por_consulta": args.top,
            "agregacion_por_libro": f"suma de las {TOP_POR_LIBRO_AGREGADO} mejores unidades",
            "documentos_excluidos": "notas al pie y unidades sin términos",
            "ruido_de_formato": "excluido del índice (vocabulario.py)",
        },
        "corpus": {
            "documentos_indexados": len(documentos),
            "consultas": len(consultas),
            "vocabulario": len(indice),
            "descartados": dict(descartados),
            "libros": libros,
        },
        "diagnostico": diagnosticar(resultados),
        "resultados": resultados,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporal = SALIDA_PATH.with_suffix(".json.tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)
    temporal.replace(SALIDA_PATH)

    diagnostico = salida["diagnostico"]
    puntaje = diagnostico["score_top1"]
    ganadores = Counter(max(r["libros"], key=r["libros"].get) for r in resultados)
    print("\n=== Ranking TF-IDF ===")
    print(f"Similitud del top-1: media {puntaje['media']:.3f}  mediana "
          f"{puntaje['mediana']:.3f}  min {puntaje['min']:.3f}  max {puntaje['max']:.3f}")
    print(f"Consultas cuyo top-1 es un testimonio: "
          f"{diagnostico['consultas_cuyo_top1_es_testimonio']} de {len(resultados)}")
    print(f"Unidades distintas en el top-1: {diagnostico['unidades_distintas_en_top1']} "
          f"(una sola gana en {diagnostico['consultas_del_documento_top1_mas_repetido']} "
          f"consultas)")
    print(f"Unidades distintas en todo el top guardado: "
          f"{diagnostico['unidades_distintas_en_el_top_guardado']} de {len(documentos)}")
    print("Libro ganador por entrevista:")
    for libro, cuenta in ganadores.most_common():
        print(f"  {cuenta:5d}  {libro}")
    print(f"\nRanking: {SALIDA_PATH}")


if __name__ == "__main__":
    main()
