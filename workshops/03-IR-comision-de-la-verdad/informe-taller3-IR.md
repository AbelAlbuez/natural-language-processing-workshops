# Taller 3 — Recuperación de Información sobre la Comisión de la Verdad

**Autores:** Abel Albuez Sanchez · Kelly Joane Leon Torres · Juan Camilo Torres Peña · Jesús David Romero Melo
**Fecha de cierre:** 2026-09-11  
**Corpus:** 56.495 unidades de libro y 2.486 entrevistas.  
**Entrada de entrevistas:** archivo local verificado con SHA-256 `32bcc2cf100cf2873cf87d9897a308451a472d73a762a4293ed08adc7689afdf`.

## 1. Objetivo y unidad documental

El objetivo es relacionar entrevistas de la Comisión para el Esclarecimiento de la Verdad con unidades de los libros del Informe Final. Las entrevistas funcionan como consultas y cada unidad segmentada de libro como documento recuperable. Para resolver la diferencia de escala entre una entrevista completa y un fragmento de libro, las entrevistas se segmentaron en pasajes por turnos de hablante.

La cadena reproducible es:

```bash
.venv/bin/python preprocesar_corpus.py
.venv/bin/python analisis_exploratorio.py
.venv/bin/python segmentacion_entrevistas.py
.venv/bin/python modelo_ir.py --consultas pasajes
.venv/bin/python modelos_relevancia.py
.venv/bin/python comparacion_corpus.py
```

La entrada de entrevistas no se versiona por superar 100 MB. Su hash y procedimiento de verificación están documentados en `docs/README-base-datos.md`.

## 2. Extracción y preparación

Los nueve tomos con PDF se segmentan por tipografía, geometría, párrafos, títulos, subtítulos, testimonios y notas al pie. `CUANDO_LOS_PAJAROS_NO_CANTABAN` llegó ya segmentado y se integra desde `corpus/CUANDO_LOS_PAJAROS_NO_CANTABAN.json`; no se regenera porque su PDF no está disponible.

El preprocesamiento aplica la misma cadena a libros y entrevistas: tokenización, minúsculas, eliminación de puntuación y stopwords de spaCy español y lematización con `es_core_news_md`. Se generan `data/corpus_raw.json` y `data/corpus_preprocesado.json` con los mismos IDs. El corpus actual contiene 58.981 documentos y 379 entradas cuyo texto preprocesado queda vacío: 377 de libros y 2 entrevistas. Esas entradas se conservan para trazabilidad, pero se excluyen de los índices.

El identificador de cada documento permite volver desde un resultado a su origen: `libro:<nombre>:<posición>` para libros y `entrevista:<id_doc>` para entrevistas. Los pasajes usan IDs `pasaje:<id_doc>:<posición>`.

## 3. Análisis exploratorio

Las cifras siguientes provienen de `data/analisis_exploratorio.json`.

| Corpus | Versión | Documentos | Tokens | Vocabulario | TTR | Hapax |
|---|---|---:|---:|---:|---:|---:|
| Libros | Crudo | 56.495 | 2.214.055 | 51.091 | 0,0231 | 37,77 % |
| Libros | Preprocesado | 56.495 | 1.078.082 | 35.475 | 0,0329 | 37,54 % |
| Entrevistas | Crudo | 2.486 | 34.715.069 | 148.026 | 0,0043 | 35,50 % |
| Entrevistas | Preprocesado | 2.486 | 12.626.056 | 103.416 | 0,0082 | 40,45 % |

La mediana preprocesada es de 11 tokens por unidad de libro y 4.133,5 tokens por entrevista completa. Esta diferencia motivó segmentar las entrevistas antes de recuperar. El análisis también calcula Zipf, frecuencias, longitud, TTR, hapax y solapamiento léxico. Los vocabularios preprocesados comparten 25.506 términos, con Jaccard 0,22495.

El ruido de formato representa 6,39 % de los tokens preprocesados de libros y 11,03 % de los de entrevistas. Incluye etiquetas de hablante, marcas de transcripción, restos de URL y números; se excluye de las figuras de contenido y del índice, pero se conserva la información de auditoría.

Las figuras son:

- `figuras/zipf_preprocesado.png`.
- `figuras/zipf_crudo_vs_preprocesado.png`.
- `figuras/longitud_documentos.png`.
- `figuras/top_terminos.png`.
- `figuras/nube_libros.png`.
- `figuras/nube_entrevistas.png`.

## 4. Modelo TF-IDF y coseno

El ranking oficial está en `data/ranking_tfidf.json`. Usa 161.254 pasajes de 2.484 entrevistas, con 41.034 unidades de libro indexables y un vocabulario de 17.497 términos con `min_df=2`. Se excluyen 12.372 notas al pie, 2.355 unidades de menos de dos términos, 734 unidades sin términos y 382 pasajes cortos o vacíos; las dos entrevistas vacías no entran como consultas.

El pesado es:

```text
tf = 1 + log(frecuencia)
idf = log((1 + N) / (1 + df)) + 1
peso = tf * idf
```

Los vectores de consultas y documentos se normalizan en L2, por lo que el producto punto equivale a similitud coseno. Para cada entrevista se toma el máximo por unidad de libro entre sus pasajes y se guardan las 20 mejores unidades. La suma de las diez mejores unidades agrega resultados al nivel de libro.

El top-1 del ranking tiene media de similitud 0,5274, mediana 0,4809 y máximo 0,9866. Hay 1.801 unidades distintas en el top-1 y 9.950 unidades distintas en los top-20 guardados. La mediana de longitud de la unidad ganadora es 17 tokens.

La normalización no es decorativa: en una muestra de cinco entrevistas, quitarla cambió 4 de 5 posiciones del top-5 en una entrevista y las 5 de 5 en las otras cuatro, haciendo que dominaran las unidades largas. Por esa razón el ranking oficial usa exclusivamente L2×L2.

## 5. Rocchio y BM25

Las dos métricas están implementadas manualmente en `modelos_relevancia.py`. No se usa `sklearn` ni `rank_bm25`.

### Rocchio

No hay juicios humanos de relevancia, así que se usa pseudo-relevance feedback. Las cinco primeras unidades del ranking TF-IDF son pseudo-relevantes; cinco documentos fuera del top-20 se muestrean como pseudo-no-relevantes con semilla `20260911`.

La fórmula es:

```text
q' = alpha*q + beta*mean(R) - gamma*mean(N)
```

Los parámetros son `alpha=1.0`, `beta=0.75` y `gamma=0.15`. La salida está en `data/ranking_rocchio.json`: 2.484 resultados, top-20 y 1.761 unidades distintas en el top-1.

### Okapi BM25

BM25 parte de conteos crudos de términos preprocesados y longitudes documentales. No reutiliza los vectores TF-IDF normalizados L2. Sus parámetros son `k1=1.2` y `b=0.75`.

```text
idf(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
score(t,d) = idf(t) * ((k1 + 1) * f(t,d)) /
            (f(t,d) + k1 * (1 - b + b * |d| / avgdl))
```

La salida está en `data/ranking_bm25.json`: 2.484 resultados, top-20 y 1.705 unidades distintas en el top-1. Los documentos vacíos se excluyen antes de construir el vocabulario, los conteos y las longitudes.

### Comparación

`data/comparacion_metricas.json` y `data/comparacion_metricas.md` contienen diez consultas seleccionadas reproduciblemente. Rocchio compartió entre 1 y 3 elementos del top-3 con TF-IDF en esos ejemplos; BM25 compartió entre 0 y 1. Esto muestra que las métricas producen órdenes distintos, pero no permite afirmar que una tenga mayor precisión: no existe un conjunto de juicios humanos.

La interpretación metodológica es acotada. Rocchio permanece cercano a TF-IDF porque reformula a partir de sus primeros resultados. BM25 cambia la ponderación por IDF y normaliza su frecuencia por longitud, por lo que responde de otra manera a términos raros y documentos largos. Para una evaluación real sería necesario anotar relevancia para una muestra de consultas y calcular precisión, recall o métricas de ranking.

## 6. Comparación de corpus y heatmap

Se eligió TF-IDF como fuente del cuadro porque es la línea base oficial, reproducible y sin pseudo-relevancia. `data/cuadro_vinculos.json` contiene los top-3 libros y los puntajes agregados para las 2.484 entrevistas y los 10 libros.

El heatmap `figuras/heatmap_vinculos_tfidf.png` trabaja a nivel de libro, no de unidad. Cada celda contiene el puntaje agregado de las diez mejores unidades de ese libro, normalizado por el máximo de la entrevista únicamente para facilitar la visualización.

Los libros ganadores más frecuentes son:

| Libro | Entrevistas ganadoras |
|---|---:|
| `CUANDO_LOS_PAJAROS_NO_CANTABAN` | 778 |
| `HASTA_LA_GUERRA_TIENE_LIMITES` | 710 |
| `LA_COLOMBIA_FUERA_DE_COLOMBIA` | 214 |
| `NO_MATARAS` | 161 |
| `RESISTIR_NO_ES_AGUANTAR` | 155 |
| `HALLAZGOS_Y_RECOMENDACIONES` | 154 |
| `MI_CUERPO_ES_LA_VERDAD` | 133 |
| `NO_ES_UN_MAL_MENOR` | 105 |
| `SUFRIR_LA_GUERRA_Y_REHACER_LA_VIDA` | 74 |
| `CONVOCATORIA_A_LA_PAZ_GRANDE` | 0 |

## 7. Limitaciones

- El salto histórico de 188 a 379 documentos vacíos no puede descomponerse completamente porque los JSON de la ejecución anterior no están versionados. Sí está demostrado que 1.809 unidades adicionales provienen del décimo tomo.
- La asimetría original entre entrevistas completas y unidades de libro era extrema: mediana de 4.133,5 frente a 11 tokens preprocesados. La segmentación en pasajes y la normalización L2 fueron necesarias para evitar que el tamaño dominara el ranking.
- La pseudo-relevancia de Rocchio hereda posibles errores del top-5 de TF-IDF y los negativos aleatorios pueden ser relevantes.
- No hay metadatos suficientes de persona, fecha o lugar en las entrevistas para evaluar o agrupar por esos campos.
- No hay juicios humanos; las diferencias entre métricas son comparativas, no una validación de relevancia externa.
- La etiqueta `es_relato` no tiene exactamente la misma semántica en el décimo tomo, cuya segmentación usa títulos y subtítulos.
- El archivo de entrevistas es un insumo local no versionado; la reproducibilidad depende de verificar su hash y de instalar el modelo spaCy documentado.

## 8. Conclusiones y mejoras

El taller queda con una cadena reproducible que va desde unidades estructuradas y preprocesamiento común hasta tres rankings comparables, un cuadro por libro y un heatmap. TF-IDF por pasajes resuelve el colapso observado con entrevistas completas y ofrece una base trazable para los métodos siguientes. Rocchio y BM25 están implementados de forma manual y muestran órdenes diferentes bajo parámetros explícitos.

Las siguientes mejoras deben priorizar una evaluación anotada de relevancia, calibración de `k1`, `b`, `alpha`, `beta` y `gamma`, comparación con consultas segmentadas de distintos tamaños y revisión humana de los vínculos de baja puntuación. También conviene versionar un manifiesto de hashes de todos los insumos y automatizar una prueba que confirme que los documentos vacíos nunca entran en los índices.

## 9. Entregables finales

| Entregable | Ruta |
|---|---|
| Corpus extraído y preprocesado | `corpus/*.json`, `data/corpus_raw.json`, `data/corpus_preprocesado.json` |
| Informe de análisis exploratorio | `data/analisis_exploratorio.json` y `figuras/` |
| Código y resultados TF-IDF | `modelo_ir.py` y `data/ranking_tfidf.json` |
| Rocchio y BM25 manuales | `modelos_relevancia.py`, `data/ranking_rocchio.json`, `data/ranking_bm25.json` |
| Cuadro y gráfico de relacionamiento | `data/cuadro_vinculos.json`, `figuras/heatmap_vinculos_tfidf.png` |
| Informe final integrador | `informe-taller3-IR.md` |

Los entregables están completos para una entrega técnica reproducible. Quedan como pendientes metodológicos la evaluación humana de relevancia y la explicación histórica completa del salto de 188 a 379 vacíos; deben declararse como limitaciones, no como resultados cerrados.
