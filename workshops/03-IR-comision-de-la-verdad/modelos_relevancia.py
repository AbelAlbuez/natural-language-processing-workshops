"""Rocchio y Okapi BM25 manuales sobre el corpus de pasajes del Taller 3.

Rocchio usa pseudo-relevance feedback: las cinco primeras unidades del ranking
TF-IDF oficial son relevantes y cinco unidades aleatorias fuera de su top-20
son no relevantes. BM25 se calcula desde conteos de términos y longitudes
documentales, sin reutilizar los vectores L2 del ranking oficial.
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse

from modelo_ir import (
    BLOQUE_CONSULTAS,
    MIN_DF,
    MIN_TOKENS_CONSULTA,
    MIN_TOKENS_DOCUMENTO,
    TOP_POR_LIBRO_AGREGADO,
    TOP_UNIDADES,
    agrupar_filas,
    cargar_documentos_y_consultas,
    cargar_fragmentos,
    cargar_pasajes,
    construir_vocabulario,
    matriz_tfidf,
    normas_l2,
    normalizar,
    top_k_de_fila,
)
from vocabulario import es_ruido_de_formato

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RANKING_TFIDF = DATA_DIR / "ranking_tfidf.json"
RANKING_ROCCHIO = DATA_DIR / "ranking_rocchio.json"
RANKING_BM25 = DATA_DIR / "ranking_bm25.json"
COMPARACION = DATA_DIR / "comparacion_metricas.json"
COMPARACION_MD = DATA_DIR / "comparacion_metricas.md"

ALPHA = 1.0
BETA = 0.75
GAMMA = 0.15
K1 = 1.2
B = 0.75
PSEUDO_RELEVANTES = 5
PSEUDO_NO_RELEVANTES = 5
SEMILLA = 20260911


def cargar_ranking_oficial():
    with RANKING_TFIDF.open(encoding="utf-8") as archivo:
        ranking = json.load(archivo)
    if ranking["parametros"]["normalizacion"] != "l2":
        raise SystemExit("El ranking oficial no usa normalización L2.")
    if ranking["parametros"]["consultas"] != "pasajes":
        raise SystemExit("El ranking oficial no usa consultas por pasajes.")
    return ranking


def matriz_conteos(textos, indice):
    """Construye una matriz dispersa de frecuencias enteras por término."""
    filas, columnas, valores = [], [], []
    for fila, tokens in enumerate(textos):
        cuentas = Counter(t for t in tokens if t in indice)
        for termino, cuenta in cuentas.items():
            filas.append(fila)
            columnas.append(indice[termino])
            valores.append(float(cuenta))
    return sparse.csr_matrix(
        (valores, (filas, columnas)),
        shape=(len(textos), len(indice)),
        dtype=np.float64,
    )


def matriz_bm25(conteos, df, k1=K1, b=B):
    """Calcula pesos documentales Okapi BM25 sin TF-IDF L2.

    Para cada término t y documento d:

        w(t,d) = IDF(t) * ((k1 + 1) * f(t,d)) /
                 (f(t,d) + k1 * (1 - b + b * |d| / avgdl))

    donde IDF(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5)). La matriz de
    entrada contiene conteos crudos y sus longitudes; no acepta vectores L2.
    """
    longitudes = np.asarray(conteos.sum(axis=1)).ravel()
    promedio = float(longitudes.mean())
    filas, columnas = conteos.nonzero()
    frecuencias = conteos.data
    total = conteos.shape[0]
    terminos = sorted(indice_global, key=lambda termino: indice_global[termino])
    idf = np.asarray([
        math.log(1.0 + (total - df[termino] + 0.5) / (df[termino] + 0.5))
        for termino in terminos
    ])
    factores = k1 * (1.0 - b + b * longitudes[filas] / promedio)
    valores = idf[columnas] * ((k1 + 1.0) * frecuencias / (frecuencias + factores))
    return sparse.csr_matrix((valores, (filas, columnas)), shape=conteos.shape)


def top_por_grupo(matriz_consultas, matriz_documentos, grupos):
    """Devuelve scores máximos por documento, agrupando filas por entrevista."""
    resultados = []
    ganadoras = []
    for numero, (_, inicio, fin) in enumerate(grupos, 1):
        mejores = None
        cual = None
        for bloque_inicio in range(inicio, fin, BLOQUE_CONSULTAS):
            bloque_fin = min(bloque_inicio + BLOQUE_CONSULTAS, fin)
            scores = (matriz_consultas[bloque_inicio:bloque_fin] @ matriz_documentos.T).toarray()
            maximos = scores.max(axis=0)
            argumentos = scores.argmax(axis=0) + bloque_inicio
            if mejores is None:
                mejores, cual = maximos, argumentos
            else:
                reemplaza = maximos > mejores
                mejores = np.where(reemplaza, maximos, mejores)
                cual = np.where(reemplaza, argumentos, cual)
        resultados.append(mejores)
        ganadoras.append(cual)
        if numero % 50 == 0:
            print(f"  grupos procesados: {numero}/{len(grupos)}", end="\r")
    print()
    return resultados, ganadoras


def construir_rocchio(
    consultas_tfidf, documentos_tfidf, grupos, documentos, ranking,
    alpha, beta, gamma,
):
    """Reformula cada pasaje con Rocchio y devuelve su matriz de consultas.

    La fórmula es:

        q' = alpha*q + beta/|R| * sum(d_r) - gamma/|N| * sum(d_n)

    Los centroides se forman con los documentos pseudo-relevantes y
    pseudo-no-relevantes definidos en la bitácora. La semilla fija hace que la
    selección negativa sea reproducible.
    """
    posiciones = {documento["id"]: posicion for posicion, documento in enumerate(documentos)}
    rng = np.random.default_rng(SEMILLA)
    base_por_grupo = []
    for resultado in ranking["resultados"]:
        top_ids = [unidad["id"] for unidad in resultado["unidades"]]
        relevantes = [posiciones[identificador] for identificador in top_ids[:PSEUDO_RELEVANTES]]
        excluidos = set(top_ids)
        disponibles = [
            posicion for identificador, posicion in posiciones.items()
            if identificador not in excluidos
        ]
        no_relevantes = rng.choice(disponibles, size=PSEUDO_NO_RELEVANTES, replace=False)
        centroidro_relevante = documentos_tfidf[relevantes].mean(axis=0)
        centroidro_no_relevante = documentos_tfidf[no_relevantes].mean(axis=0)
        base_por_grupo.append(
            beta * sparse.csr_matrix(centroidro_relevante)
            - gamma * sparse.csr_matrix(centroidro_no_relevante)
        )
    base = sparse.vstack(base_por_grupo).tocsr()
    grupo_por_fila = np.empty(consultas_tfidf.shape[0], dtype=np.int32)
    for grupo, (_, inicio, fin) in enumerate(grupos):
        grupo_por_fila[inicio:fin] = grupo
    return alpha * consultas_tfidf + base[grupo_por_fila]


def agregar_libros(scores, libros_por_documento, libros):
    agregados = {}
    for libro in libros:
        valores = scores[libros_por_documento == libro]
        mejores = np.partition(valores, -min(TOP_POR_LIBRO_AGREGADO, len(valores)))[-TOP_POR_LIBRO_AGREGADO:]
        agregados[libro] = float(mejores.sum())
    return agregados


def serializar_resultados(scores, ganadoras, grupos, consultas, documentos, libros_por_documento, libros):
    fragmentos = cargar_fragmentos({documento["id"] for documento in documentos})
    resultados = []
    for scores_grupo, filas_grupo, (consulta_id, inicio, fin) in zip(scores, ganadoras, grupos):
        unidades = []
        for posicion in map(int, top_k_de_fila(scores_grupo, TOP_UNIDADES)):
            documento = documentos[posicion]
            fila = int(filas_grupo[posicion])
            pasaje = consultas[fila]
            unidades.append({
                "id": documento["id"],
                "score": float(scores_grupo[posicion]),
                "libro": documento["metadatos"]["libro"],
                "parte": documento["metadatos"]["parte"],
                "capitulo": documento["metadatos"]["capitulo"],
                "titulo": documento["metadatos"]["titulo"],
                "es_relato": documento["metadatos"]["es_relato"],
                "tokens": len(documento["tokens"]),
                "pasaje": {
                    "id": pasaje["id"],
                    "indice": pasaje["indice"],
                    "fragmento": pasaje["fragmento"],
                },
                "fragmento": fragmentos.get(documento["id"], ""),
            })
        resultados.append({
            "consulta": consulta_id,
            "consultas_usadas": fin - inicio,
            "unidades": unidades,
            "libros": agregar_libros(scores_grupo, libros_por_documento, libros),
        })
    return resultados


def diagnostico(resultados):
    top1 = Counter(resultado["unidades"][0]["id"] for resultado in resultados)
    top_guardado = {unidad["id"] for resultado in resultados for unidad in resultado["unidades"]}
    return {
        "consultas": len(resultados),
        "unidades_distintas_en_top1": len(top1),
        "unidades_distintas_en_el_top_guardado": len(top_guardado),
        "top1_mas_repetido": top1.most_common(1)[0],
    }


def guardar(path, contenido):
    with path.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)


def construir_comparacion(ranking_oficial, ranking_rocchio, ranking_bm25):
    rng = np.random.default_rng(SEMILLA)
    indices = sorted(rng.choice(len(ranking_oficial["resultados"]), size=10, replace=False).tolist())
    ejemplos = []
    for indice in indices:
        filas = []
        for nombre, ranking in (("tfidf", ranking_oficial), ("rocchio", ranking_rocchio), ("bm25", ranking_bm25)):
            unidades = ranking["resultados"][indice]["unidades"]
            filas.append({
                "metrica": nombre,
                "top3": [unidad["id"] for unidad in unidades[:3]],
                "scores_top3": [unidad["score"] for unidad in unidades[:3]],
            })
        conjuntos = {fila["metrica"]: set(fila["top3"]) for fila in filas}
        ejemplos.append({
            "consulta": ranking_oficial["resultados"][indice]["consulta"],
            "indice_resultado": indice,
            "rankings": filas,
            "interseccion_top3_tfidf_rocchio": len(conjuntos["tfidf"] & conjuntos["rocchio"]),
            "interseccion_top3_tfidf_bm25": len(conjuntos["tfidf"] & conjuntos["bm25"]),
        })
    return {
        "semilla": SEMILLA,
        "criterio": "Diez entrevistas seleccionadas de forma reproducible; comparación de los tres top-3.",
        "ejemplos": ejemplos,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alpha", type=float, default=ALPHA)
    parser.add_argument("--beta", type=float, default=BETA)
    parser.add_argument("--gamma", type=float, default=GAMMA)
    parser.add_argument("--k1", type=float, default=K1)
    parser.add_argument("--b", type=float, default=B)
    args = parser.parse_args()

    documentos, _, descartados, modelo = cargar_documentos_y_consultas(MIN_TOKENS_DOCUMENTO)
    consultas, pasajes_vacios, parametros_pasajes = cargar_pasajes(MIN_TOKENS_CONSULTA)
    ranking_oficial = cargar_ranking_oficial()
    grupos = agrupar_filas(consultas)
    indice, idf, df = construir_vocabulario(documentos, MIN_DF)
    global indice_global
    indice_global = indice

    documentos_tfidf = matriz_tfidf([documento["tokens"] for documento in documentos], indice, idf)
    documentos_tfidf = normalizar(documentos_tfidf, "l2", 1.0, 1.0)
    consultas_tfidf = matriz_tfidf([consulta["tokens"] for consulta in consultas], indice, idf)
    consultas_tfidf = normalizar(consultas_tfidf, "l2", 1.0, 1.0)

    rocchio_queries = construir_rocchio(
        consultas_tfidf, documentos_tfidf, grupos, documentos, ranking_oficial,
        args.alpha, args.beta, args.gamma,
    )
    rocchio_scores, rocchio_filas = top_por_grupo(rocchio_queries, documentos_tfidf, grupos)

    conteos_documentos = matriz_conteos([documento["tokens"] for documento in documentos], indice)
    bm25_documentos = matriz_bm25(conteos_documentos, df, args.k1, args.b)
    conteos_consultas = matriz_conteos([consulta["tokens"] for consulta in consultas], indice)
    bm25_scores, bm25_filas = top_por_grupo(conteos_consultas, bm25_documentos, grupos)

    libros_por_documento = np.array([documento["metadatos"]["libro"] for documento in documentos])
    libros = sorted(set(libros_por_documento.tolist()))
    comunes = {
        "version": 1,
        "modelo_lematizacion": modelo,
        "parametros": {
            "consultas": "pasajes",
            "min_df": MIN_DF,
            "min_tokens_documento": MIN_TOKENS_DOCUMENTO,
            "min_tokens_consulta": MIN_TOKENS_CONSULTA,
            "top_unidades_por_consulta": TOP_UNIDADES,
            "documentos_vacios_excluidos": True,
            "documentos_indexados": len(documentos),
        },
        "corpus": {
            "documentos_indexados": len(documentos),
            "consultas": len(consultas),
            "entrevistas": len(grupos),
            "descartados": {**dict(descartados), "pasaje_corto_o_vacio": pasajes_vacios},
            "libros": libros,
        },
    }
    rocchio = {
        **comunes,
        "metrica": "Rocchio manual",
        "parametros": {
            **comunes["parametros"],
            "alpha": args.alpha,
            "beta": args.beta,
            "gamma": args.gamma,
            "pseudo_relevantes": PSEUDO_RELEVANTES,
            "pseudo_no_relevantes": PSEUDO_NO_RELEVANTES,
            "semilla": SEMILLA,
            "formula": "q'=alpha*q + beta*mean(R) - gamma*mean(N)",
        },
        "resultados": serializar_resultados(
            rocchio_scores, rocchio_filas, grupos, consultas, documentos,
            libros_por_documento, libros,
        ),
    }
    rocchio["diagnostico"] = diagnostico(rocchio["resultados"])
    bm25 = {
        **comunes,
        "metrica": "Okapi BM25 manual",
        "parametros": {
            **comunes["parametros"],
            "k1": args.k1,
            "b": args.b,
            "formula_idf": "log(1 + (N-df+0.5)/(df+0.5))",
            "formula_peso": "idf*((k1+1)*tf)/(tf+k1*(1-b+b*longitud/longitud_media))",
            "entrada": "conteos de términos preprocesados y longitudes documentales",
        },
        "resultados": serializar_resultados(
            bm25_scores, bm25_filas, grupos, consultas, documentos,
            libros_por_documento, libros,
        ),
    }
    bm25["diagnostico"] = diagnostico(bm25["resultados"])
    comparacion = construir_comparacion(ranking_oficial, rocchio, bm25)

    guardar(RANKING_ROCCHIO, rocchio)
    guardar(RANKING_BM25, bm25)
    guardar(COMPARACION, comparacion)
    lineas = ["# Comparación de métricas", "", "Comparación reproducible de diez consultas; semilla: 20260911.", ""]
    for ejemplo in comparacion["ejemplos"]:
        lineas.append(f"## {ejemplo['consulta']}")
        for fila in ejemplo["rankings"]:
            lineas.append(f"- **{fila['metrica']}**: " + ", ".join(fila["top3"]))
        lineas.append(
            f"- Coincidencias top-3: TF-IDF/Rocchio={ejemplo['interseccion_top3_tfidf_rocchio']}, "
            f"TF-IDF/BM25={ejemplo['interseccion_top3_tfidf_bm25']}."
        )
        lineas.append("")
    lineas += [
        "## Lectura", "",
        "TF-IDF usa L2×L2 y pasajes; Rocchio añade pseudo-relevance feedback con "
        "top-5 positivos y cinco negativos aleatorios; BM25 usa conteos y "
        "normalización propia por longitud. Las diferencias no son una métrica "
        "de precisión: no hay juicios humanos de relevancia.",
    ]
    COMPARACION_MD.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Rocchio: {RANKING_ROCCHIO}")
    print(f"BM25: {RANKING_BM25}")
    print(f"Comparación: {COMPARACION} y {COMPARACION_MD}")
    print("Diagnóstico Rocchio:", rocchio["diagnostico"])
    print("Diagnóstico BM25:", bm25["diagnostico"])


if __name__ == "__main__":
    main()