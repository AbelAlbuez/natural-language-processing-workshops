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
- Corte de vocabulario `MIN_DF = 2
# Un documento de un solo término no expresa un tema: con consultas cortas hace
# coseno 1,0 contra cualquier pasaje que mencione esa palabra. Con la entrevista
# completa como consulta el filtro era irrelevante (133 vs 135 unidades
# distintas en el top-1); con pasajes elimina todos los matches de score > 0,9.
MIN_TOKENS_DOCUMENTO = 2
# Lo mismo del lado de la consulta: un pasaje que tras limpiar queda en cuatro
# términos ("[INAD] Esta es mi [CORTE]") no expresa un tema y, como el puntaje
# de la entrevista es el máximo sobre sus pasajes, uno así puede secuestrar el
# top-1. Son 327 de 160.878 pasajes: quita los matches perfectos espurios, pero
# su efecto sobre la diversidad del ranking está dentro del ruido.
MIN_TOKENS_CONSULTA = 5`: un término que aparece en un solo
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
PASAJES_PATH = DATA_DIR / "corpus_pasajes.json"
SALIDA_PATH = DATA_DIR / "ranking_tfidf.json"  # normalización L2 (coseno)


def ruta_de_salida(modo, slope, alfa, consultas):
    """Un archivo por configuración: el ranking coseno sobre entrevistas
    completas es la línea base y no se debe pisar con el de una variante."""
    partes = []
    if modo != "l2":
        partes.append(f"{modo}_" + (f"s{slope:g}" if modo == "pivotada" else f"a{alfa:g}"))
    if consultas != "entrevistas":
        partes.append(consultas)
    if not partes:
        return SALIDA_PATH
    return DATA_DIR / ("ranking_tfidf_" + "_".join(partes) + ".json")

MIN_DF = 2
# Un documento de un solo término no expresa un tema: con consultas cortas hace
# coseno 1,0 contra cualquier pasaje que mencione esa palabra. Con la entrevista
# completa como consulta el filtro era irrelevante (133 vs 135 unidades
# distintas en el top-1); con pasajes elimina todos los matches de score > 0,9.
MIN_TOKENS_DOCUMENTO = 2
# Lo mismo del lado de la consulta: un pasaje que tras limpiar queda en cuatro
# términos ("[INAD] Esta es mi [CORTE]") no expresa un tema y, como el puntaje
# de la entrevista es el máximo sobre sus pasajes, uno así puede secuestrar el
# top-1. Son 327 de 160.878 pasajes: quita los matches perfectos espurios, pero
# su efecto sobre la diversidad del ranking está dentro del ruido.
MIN_TOKENS_CONSULTA = 5
TOP_UNIDADES = 20          # unidades que se guardan por entrevista
TOP_POR_LIBRO_AGREGADO = 10  # cuántas unidades suma cada libro (decisión de agregación)
LARGO_FRAGMENTO = 240      # caracteres del texto crudo que se guardan como evidencia
BLOQUE_CONSULTAS = 128     # consultas por bloque: acota la matriz densa intermedia


def cargar_documentos_y_consultas(min_tokens=MIN_TOKENS_DOCUMENTO):
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
            if len(tokens) < min_tokens:
                descartados["muy_corto" if tokens else "sin_terminos"] += 1
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


def cargar_pasajes(min_tokens=MIN_TOKENS_CONSULTA):
    """Pasajes de entrevista como consultas, agrupados por entrevista.

    Los produce segmentacion_entrevistas.py. Vienen ordenados por entrevista,
    así que cada grupo es un tramo contiguo de filas.
    """
    if not PASAJES_PATH.exists():
        raise SystemExit(
            f"no existe {PASAJES_PATH}.\n"
            "  Generalo con: .venv/bin/python segmentacion_entrevistas.py"
        )
    with PASAJES_PATH.open(encoding="utf-8") as archivo:
        corpus = json.load(archivo)

    pasajes, vacios = [], 0
    for registro in corpus["documentos"]:
        tokens = [t for t in registro["texto_preprocesado"].split() if not es_ruido_de_formato(t)]
        if len(tokens) < min_tokens:
            vacios += 1
            continue
        pasajes.append({
            "id": registro["id"],
            "entrevista": registro["entrevista"],
            "indice": registro["indice"],
            "tokens": tokens,
            "fragmento": registro["fragmento"],
        })
    return pasajes, vacios, corpus["parametros"]


def agrupar_filas(consultas):
    """[(id de la consulta lógica, primera fila, última fila + 1)].

    Con entrevistas completas cada grupo es una fila; con pasajes, el grupo
    reúne todos los pasajes de una entrevista.
    """
    grupos, inicio = [], 0
    for fila in range(1, len(consultas) + 1):
        fin_de_grupo = (
            fila == len(consultas)
            or consultas[fila].get("entrevista", consultas[fila]["id"])
            != consultas[inicio].get("entrevista", consultas[inicio]["id"])
        )
        if fin_de_grupo:
            grupos.append(
                (consultas[inicio].get("entrevista", consultas[inicio]["id"]), inicio, fila)
            )
            inicio = fila
    return grupos


def mejor_por_documento(matriz_consultas, documentos_m, inicio, fin):
    """Máximo por documento sobre las filas [inicio, fin) y qué fila lo logró.

    Una entrevista se relaciona con una unidad si **algún** pasaje suyo se
    parece a ella; promediar sobre todos los pasajes diluiría justamente la
    coincidencia que se busca. Se acumula por trozos porque una entrevista
    puede tener más de mil pasajes.
    """
    mejores = None
    cual = None
    for bloque_inicio in range(inicio, fin, BLOQUE_CONSULTAS):
        bloque_fin = min(bloque_inicio + BLOQUE_CONSULTAS, fin)
        similitudes = (matriz_consultas[bloque_inicio:bloque_fin] @ documentos_m.T).toarray()
        maximos = similitudes.max(axis=0)
        argumentos = similitudes.argmax(axis=0) + bloque_inicio
        if mejores is None:
            mejores, cual = maximos, argumentos
        else:
            reemplaza = maximos > mejores
            mejores = np.where(reemplaza, maximos, mejores)
            cual = np.where(reemplaza, argumentos, cual)
    return mejores, cual


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
    """Matriz dispersa (documentos x términos) con pesos tf-idf SIN normalizar."""
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

    return sparse.csr_matrix(
        (valores, (filas, columnas)),
        shape=(len(textos_tokenizados), len(indice)),
        dtype=np.float64,
    )


def normas_l2(matriz):
    normas = np.sqrt(matriz.multiply(matriz).sum(axis=1)).A.ravel()
    normas[normas == 0] = 1.0
    return normas


def normalizar(matriz, modo, slope, alfa):
    """Divide cada fila por un factor de longitud.

    - `l2`: la norma euclídea. Es la similitud coseno de siempre.
    - `pivotada`: forma canónica de Singhal (1996),
          factor = (1 - slope) * pivote + slope * ||d||,   pivote = media(||d||)
      Interpola entre no normalizar (slope=0) y la coseno (slope=1). Corrige el
      sesgo de la coseno CONTRA los documentos largos, que es el caso habitual
      con consultas cortas.
    - `potencia`: extiende la misma idea más allá de la coseno,
          factor = pivote * (||d|| / pivote) ** alfa
      con alfa=1 se reduce exactamente a la coseno y con alfa>1 penaliza la
      longitud MÁS que ella. Es la dirección que necesita este corpus, donde la
      consulta es casi exhaustiva y los documentos largos ganan por cobertura.
    """
    normas = normas_l2(matriz)
    if modo == "l2":
        factor = normas
    elif modo == "pivotada":
        factor = (1.0 - slope) * normas.mean() + slope * normas
    elif modo == "potencia":
        pivote = normas.mean()
        factor = pivote * (normas / pivote) ** alfa
    else:
        raise ValueError(f"normalización desconocida: {modo}")
    factor[factor <= 0] = 1.0
    return sparse.diags(1.0 / factor) @ matriz


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
        "tokens_mediana_top1": float(
            np.median([r["unidades"][0]["tokens"] for r in resultados])
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


def barrer(documentos_crudos, consultas_m, documentos, consultas, args):
    """Compara normalizaciones sobre una muestra de consultas.

    La métrica es el diagnóstico de 6.4 de la bitácora: cuántos documentos
    distintos ocupan el top-1. Si son muchos menos que las consultas, el modelo
    no discrimina por tema.
    """
    generador = np.random.default_rng(20260910)
    filas = np.sort(generador.choice(
        consultas_m.shape[0], size=min(args.muestra, consultas_m.shape[0]), replace=False
    ))
    bloque_consultas = consultas_m[filas]
    longitudes = np.array([len(d["tokens"]) for d in documentos])

    configuraciones = [("l2", 1.0, 1.0)]
    configuraciones += [("pivotada", s, 1.0) for s in (0.2, 0.5, 0.8)]
    configuraciones += [("potencia", 1.0, a) for a in (1.25, 1.5, 1.75, 2.0, 2.5, 3.0)]

    print(f"\n=== Barrido de normalización ({len(filas)} consultas de muestra) ===")
    print(f"{'normalización':>22}  {'top-1 distintos':>15}  {'más repetido':>12}  "
          f"{'mediana tokens top-1':>20}")
    for modo, slope, alfa in configuraciones:
        matriz = normalizar(documentos_crudos, modo, slope, alfa)
        ganadores, tokens_ganadores = [], []
        for inicio in range(0, bloque_consultas.shape[0], BLOQUE_CONSULTAS):
            similitudes = (bloque_consultas[inicio : inicio + BLOQUE_CONSULTAS] @ matriz.T).toarray()
            mejores = similitudes.argmax(axis=1)
            ganadores.extend(mejores.tolist())
            tokens_ganadores.extend(longitudes[mejores].tolist())
        cuenta = Counter(ganadores)
        etiqueta = modo if modo == "l2" else (
            f"{modo} s={slope}" if modo == "pivotada" else f"{modo} α={alfa}"
        )
        print(f"{etiqueta:>22}  {len(cuenta):>15}  {cuenta.most_common(1)[0][1]:>12}  "
              f"{np.median(tokens_ganadores):>20.0f}")
    print("\nMediana de tokens del corpus indexado:", int(np.median(longitudes)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=TOP_UNIDADES,
                        help="unidades guardadas por entrevista (%(default)s)")
    parser.add_argument("--min-tokens", type=int, default=MIN_TOKENS_DOCUMENTO,
                        help="tokens mínimos de una unidad para indexarla (%(default)s)")
    parser.add_argument("--min-tokens-consulta", type=int, default=MIN_TOKENS_CONSULTA,
                        help="tokens mínimos de un pasaje para usarlo como consulta (%(default)s)")
    parser.add_argument("--min-df", type=int, default=MIN_DF,
                        help="frecuencia de documento mínima de un término (%(default)s)")
    parser.add_argument("--sin-fragmentos", action="store_true",
                        help="no guardar el texto de evidencia (salida más liviana)")
    parser.add_argument("--normalizacion", choices=("l2", "pivotada", "potencia"),
                        default="l2", help="normalización de longitud (%(default)s)")
    parser.add_argument("--slope", type=float, default=0.2,
                        help="pendiente de la normalización pivotada (%(default)s)")
    parser.add_argument("--alfa", type=float, default=1.0,
                        help="exponente de la normalización de potencia (%(default)s)")
    parser.add_argument("--consultas", choices=("entrevistas", "pasajes"),
                        default="entrevistas",
                        help="unidad de consulta (%(default)s); los pasajes los "
                             "produce segmentacion_entrevistas.py")
    parser.add_argument("--barrido", action="store_true",
                        help="compara normalizaciones sobre una muestra y no escribe el ranking")
    parser.add_argument("--muestra", type=int, default=300,
                        help="consultas usadas en el barrido (%(default)s)")
    args = parser.parse_args()

    documentos, consultas, descartados, modelo = cargar_documentos_y_consultas(args.min_tokens)
    parametros_pasajes = None
    if args.consultas == "pasajes":
        consultas, pasajes_cortos, parametros_pasajes = cargar_pasajes(args.min_tokens_consulta)
        descartados["pasaje_corto_o_vacio"] = pasajes_cortos
    print(f"Documentos indexables: {len(documentos)}  (descartados: {dict(descartados)})")
    grupos = agrupar_filas(consultas)
    print(f"Consultas: {len(consultas)} ({args.consultas}) en {len(grupos)} entrevistas")

    indice, idf, df = construir_vocabulario(documentos, args.min_df)
    print(f"Vocabulario: {len(indice)} términos con df >= {args.min_df} "
          f"(de {len(df)} distintos)")

    documentos_crudos = matriz_tfidf([d["tokens"] for d in documentos], indice, idf)
    consultas_crudas = matriz_tfidf([c["tokens"] for c in consultas], indice, idf)
    print(f"Matriz documentos: {documentos_crudos.shape}, {documentos_crudos.nnz} no-ceros")
    print(f"Matriz consultas:  {consultas_crudas.shape}, {consultas_crudas.nnz} no-ceros")

    # la normalización de la consulta es una constante por fila: no altera el
    # orden dentro de una consulta, solo deja los puntajes en una escala legible
    consultas_m = normalizar(consultas_crudas, "l2", 1.0, 1.0)

    if args.barrido:
        barrer(documentos_crudos, consultas_m, documentos, consultas, args)
        return

    documentos_m = normalizar(documentos_crudos, args.normalizacion, args.slope, args.alfa)

    libros_por_documento = np.array([d["metadatos"]["libro"] for d in documentos])
    libros = sorted(set(libros_por_documento.tolist()))

    # una fila combinada por entrevista: con entrevistas completas es su propia
    # fila; con pasajes, el máximo por documento sobre todos sus pasajes
    resultados = []
    for numero, (consulta_id, inicio, fin) in enumerate(grupos, 1):
        similitudes, fila_ganadora = mejor_por_documento(
            consultas_m, documentos_m, inicio, fin
        )
        unidades = []
        for pos in map(int, top_k_de_fila(similitudes, args.top)):
            unidad = {
                "id": documentos[pos]["id"],
                "score": float(similitudes[pos]),
                "libro": documentos[pos]["metadatos"]["libro"],
                "parte": documentos[pos]["metadatos"]["parte"],
                "capitulo": documentos[pos]["metadatos"]["capitulo"],
                "titulo": documentos[pos]["metadatos"]["titulo"],
                "es_relato": documentos[pos]["metadatos"]["es_relato"],
                "tokens": len(documentos[pos]["tokens"]),
            }
            if args.consultas == "pasajes":
                # de qué parte de la entrevista salió la coincidencia
                pasaje = consultas[int(fila_ganadora[pos])]
                unidad["pasaje"] = {
                    "id": pasaje["id"],
                    "indice": pasaje["indice"],
                    "fragmento": pasaje["fragmento"],
                }
            unidades.append(unidad)
        resultados.append({
            "consulta": consulta_id,
            "consultas_usadas": fin - inicio,
            "unidades": unidades,
            "libros": agregar_por_libro(
                similitudes, libros_por_documento, libros, TOP_POR_LIBRO_AGREGADO,
            ),
        })
        if numero % 50 == 0 or numero == len(grupos):
            print(f"  entrevistas procesadas: {numero}/{len(grupos)}", end="\r")
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
            "consultas": args.consultas,
            "pasajes": parametros_pasajes,
            "combinacion_de_pasajes": (
                "máximo por documento entre los pasajes de la entrevista"
                if args.consultas == "pasajes" else None
            ),
            "pesado": "tf=1+log(f), idf=log((1+N)/(1+df))+1, normalización L2, coseno",
            "normalizacion": args.normalizacion,
            "slope": args.slope if args.normalizacion == "pivotada" else None,
            "alfa": args.alfa if args.normalizacion == "potencia" else None,
            "min_df": args.min_df,
            "min_tokens_documento": args.min_tokens,
            "min_tokens_consulta": (
                args.min_tokens_consulta if args.consultas == "pasajes" else None
            ),
            "top_unidades_por_consulta": args.top,
            "agregacion_por_libro": f"suma de las {TOP_POR_LIBRO_AGREGADO} mejores unidades",
            "documentos_excluidos": "notas al pie y unidades sin términos",
            "ruido_de_formato": "excluido del índice (vocabulario.py)",
        },
        "corpus": {
            "documentos_indexados": len(documentos),
            "consultas": len(consultas),
            "entrevistas": len(grupos),
            "vocabulario": len(indice),
            "descartados": dict(descartados),
            "libros": libros,
        },
        "diagnostico": diagnosticar(resultados),
        "resultados": resultados,
    }
    salida_path = ruta_de_salida(args.normalizacion, args.slope, args.alfa, args.consultas)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporal = salida_path.with_suffix(".json.tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)
    temporal.replace(salida_path)

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
    print(f"Longitud mediana del top-1: {diagnostico['tokens_mediana_top1']:.0f} tokens")
    print(f"\nRanking: {salida_path}")


if __name__ == "__main__":
    main()
