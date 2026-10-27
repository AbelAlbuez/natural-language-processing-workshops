# Análisis exploratorio del corpus

Fecha: 2026-10-26. Fuente de todas las cifras: `notebooks/01_analisis_exploratorio.ipynb`, exportadas en `docs/analisis_corpus.json` (cada cifra indica la celda y el cálculo que la produce). Este documento no incluye texto de documentos: solo se leyeron conteos, longitudes, fechas, fuentes e idiomas.

| Entrada | Ruta | Columnas leídas |
|---|---|---|
| Corpus preparado | `data/documentos_rag.parquet` (`scripts/prepare_corpus.py --languages es en`) | `document_id`, `source`, `lang`, `lang_source`, `word_count`, `created_at_utc`, `dup_count`, `dup_sources`, `dup_document_ids` |
| Original | `~/.open_corpus_co_es/data/dragons_rag/dragons_rag.parquet` | `document_id`, `created_at`, `source` |

## 1. Carga y verificación (celda 1)

| Métrica | Preparado | Original | Referencia | ¿Coincide? |
|---|---:|---:|---:|:---:|
| Filas | 146.923 | 169.248 | 146.923 / 169.248 | Sí |
| Columnas | 41 | 33 | 41 / 33 | Sí |
| `document_id` repetidos | 0 | — | 0 | Sí |
| Tamaño del original | — | 256.941.261 bytes | 256.941.261 | Sí |
| SHA-256 del original | — | `f4a669f1…b181728` | `f4a669f1…b181728` | Sí |

Estadísticas de la regeneración: `docs/prepare_stats_es_en.json`. Se eliminaron 14.771 filas por duplicado, 7.050 por idioma y 504 por tener menos de 5 palabras. Las tres cifras coinciden con el §12 P2 de `docs/diagnostico_corpus.md`.

## 2. Composición (celda 2)

| Fuente | `es` | `en` | Total | % del corpus | % `en` en la fuente |
|---|---:|---:|---:|---:|---:|
| `media_cloud` | 59.125 | 35.176 | 94.301 | 64,18 % | 37,30 % |
| `bluesky` | 5.160 | 46.716 | 51.876 | 35,31 % | 90,05 % |
| `gdelt` | 381 | 365 | 746 | 0,51 % | 48,93 % |
| **Total** | **64.666** (44,01 %) | **82.257** (55,99 %) | **146.923** | 100 % | 55,99 % |

Las seis celdas `source × lang` coinciden exactamente con la tabla de referencia del diagnóstico (§12 P2).

Origen de la etiqueta de idioma:

| Fuente | Idioma | `language_base` | fastText |
|---|---|---:|---:|
| `bluesky` | `en` | 38.491 | 8.225 |
| `bluesky` | `es` | 3.230 | 1.930 |
| `media_cloud` | `en` / `es` | 35.176 / 59.125 | 0 / 0 |
| `gdelt` | `en` / `es` | 365 / 381 | 0 / 0 |

El 19,6 % de las filas de Bluesky (10.155 de 51.876) tiene un idioma asignado por fastText y no por la fuente.

## 3. Longitudes (celda 3)

Figura: `docs/figuras/longitudes_por_fuente.png` (histograma log-log de `word_count` por fuente).

| Fuente | n | p50 | p90 | p95 | p99 | Máximo | > 5.000 palabras |
|---|---:|---:|---:|---:|---:|---:|---:|
| `media_cloud` | 94.301 | 636 | 1.230 | 1.621 | 2.882 | 58.181 | 232 (0,246 %) |
| `bluesky` | 51.876 | 35 | 49 | 52 | 56 | 67 | 0 |
| `gdelt` | 746 | 492,5 | 1.205 | 1.508,75 | 3.205,45 | 5.330 | 1 (0,134 %) |
| **Total** | 146.923 | 423 | 1.040 | 1.363 | 2.455,78 | 58.181 | 233 (0,159 %) |

| Idioma | n | p50 | p90 | p99 | Máximo | > 5.000 palabras |
|---|---:|---:|---:|---:|---:|---:|
| `es` | 64.666 | 589 | 1.152 | 2.676,35 | 58.181 | 137 |
| `en` | 82.257 | 48 | 973 | 2.286,32 | 29.906 | 96 |

Los percentiles usan interpolación lineal (`quantile`), por eso algunos no son enteros.

## 4. Distribución temporal (celda 4)

Figura: `docs/figuras/documentos_por_anio.png` (documentos por año y fuente, escala log).

| Año | `media_cloud` | `bluesky` | `gdelt` | Total |
|---|---:|---:|---:|---:|
| 2006–2015 | 11 | 73 | 1 | 85 |
| 2016 | 1.367 | 21 | 6 | 1.394 |
| 2017 | 1.918 | 40 | 12 | 1.970 |
| 2018 | 2.874 | 36 | 55 | 2.965 |
| 2019 | 4.885 | 35 | 52 | 4.972 |
| 2020 | 5.554 | 43 | 19 | 5.616 |
| 2021 | 8.397 | 42 | 44 | 8.483 |
| 2022 | 11.063 | 0 | 81 | 11.144 |
| 2023 | 12.530 | 0 | 108 | 12.638 |
| 2024 | 21.045 | 2.447 | 97 | 23.589 |
| 2025 | 10.190 | 13.431 | 90 | 23.711 |
| 2026 | 14.444 | 35.708 | 181 | 50.333 |
| Sin fecha | 23 | 0 | 0 | 23 |

| Métrica | Valor |
|---|---|
| Rango de `created_at_utc` | 2006-08-24 → 2026-09-21 18:03:56 UTC |
| Documentos desde 2025 | 50,40 % del corpus |
| … por fuente | `bluesky` 94,72 %, `gdelt` 36,33 %, `media_cloud` 26,12 % |
| Filas sin fecha | 23, todas de `media_cloud` |

## 5. Duplicados (celda 5)

Figura: `docs/figuras/dup_count_distribucion.png`.

| Tamaño de grupo (`dup_count`) | Grupos |
|---|---:|
| 1 (sin duplicados) | 142.748 |
| 2 | 2.782 |
| 3–5 | 1.182 |
| 6–10 | 95 |
| 11–50 | 88 |
| 51–200 | 20 |
| > 200 | 8 |

| Métrica | Preparado (es + en) | Corpus completo (diagnóstico §12 P1) |
|---|---:|---:|
| Grupos con más de una copia | 4.175 | 4.434 |
| Filas en esos grupos | 17.654 | 19.205 |
| Copias descartadas | 13.479 | 14.771 |
| Grupo más grande | 839 | 839 |
| Grupos que mezclan fuentes | 14 | 18 |

Las diferencias entre las dos columnas no son discrepancias. La columna del preparado solo cuenta los grupos cuya fila conservada pasó el filtro de idioma: 259 grupos y 1.292 copias quedaron fuera porque su fila conservada no era `es` ni `en`.

Los 10 grupos más grandes, solo con conteos:

| # | `dup_count` | Fuente conservada | Idioma | Fuentes distintas |
|---:|---:|---|---|---:|
| 1 | 839 | `bluesky` | `en` | 1 |
| 2 | 674 | `bluesky` | `en` | 1 |
| 3 | 526 | `media_cloud` | `es` | 1 |
| 4 | 399 | `bluesky` | `en` | 1 |
| 5 | 347 | `bluesky` | `en` | 1 |
| 6 | 268 | `media_cloud` | `es` | 1 |
| 7 | 255 | `bluesky` | `en` | 1 |
| 8 | 214 | `bluesky` | `en` | 1 |
| 9 | 171 | `bluesky` | `en` | 1 |
| 10 | 159 | `bluesky` | `en` | 1 |

Ninguno de los 10 grupos mezcla fuentes. En todos, todas las copias son de la fuente conservada.

## 6. Propagación de noticia a red (celda 6): n = 0

**Hallazgo: no hay ningún grupo de texto idéntico que tenga a la vez una copia de `media_cloud` y una de `bluesky`.** No se puede medir la propagación noticia → red con copias exactas (`text_sha256`), porque el resultado es n = 0. No es un error del cálculo: la celda registra el resultado y no genera la figura de propagación.

| Combinación de fuentes en un grupo | Grupos |
|---|---:|
| `gdelt + media_cloud` | 14 |
| `bluesky + media_cloud` | **0** |
| `bluesky + gdelt` | 0 |
| `bluesky + gdelt + media_cloud` | 0 |
| **Total de grupos con más de una fuente** | **14** |

| Métrica | Valor |
|---|---|
| Grupos con `media_cloud` y `bluesky` | 0 |
| n con ambas fechas | 0 |
| Mediana, p25 y p75 del desfase (horas y días) | no aplica (`null` en el JSON) |
| Fechas de `media_cloud` solo con día (`AAAA-MM-DD`), en todo el original | **94,90 %** |
| Fechas de `bluesky` solo con día, en todo el original | 0,00 % |

**Por qué no hay copias exactas entre medios y redes:**

1. **Longitudes que no se solapan.** Un post de Bluesky tiene como máximo 67 palabras (p99 = 56), mientras que un artículo de `media_cloud` tiene una mediana de 636 (p90 = 1.230). Para que un post y un artículo coincidan byte a byte, el artículo entero tendría que caber en un post. Un post que cita o resume una noticia comparte palabras con ella, pero no el texto completo, y `text_sha256` solo agrupa textos idénticos.
2. **Los 14 grupos mixtos son de los rastreadores de prensa.** Son el mismo artículo capturado por `gdelt` y por `media_cloud`, que pertenecen a la misma colección (`url_crawls`). Es redundancia de rastreo, no propagación entre plataformas.
3. **Las fuentes se concentran en periodos distintos.** El 94,72 % de Bluesky es de 2025–2026, contra el 26,12 % de `media_cloud` (24.634 documentos), y Bluesky no tiene posts en 2022–2023.
4. **La resolución de las fechas impide medir en horas.** Aunque hubiera pares, el 94,90 % de las fechas de `media_cloud` tiene solo día. Un desfase "en horas" tendría una incertidumbre de ±24 h, así que la unidad realista es el día.

Medir la propagación con similitud de texto o con URLs compartidas cambia la definición de la medida. Queda como pregunta de investigación (PI3 en `docs/propuestas_investigacion.md`).

## 7. Cobertura y cuotas para el gold standard (celda 7)

| Dimensión | Proporción |
|---|---|
| Fuente | `media_cloud` 64,18 %, `bluesky` 35,31 %, `gdelt` 0,51 % |
| Idioma | `en` 55,99 %, `es` 44,01 % |
| Periodo | ≤ 2023: 33,53 %, 2024: 16,06 %, 2025: 16,14 %, 2026: 34,26 %, sin fecha: 0,02 % |

**Cuotas para 40 preguntas, proporcionales por fuente** (método del resto mayor, primero por fuente y después por idioma dentro de cada fuente):

| Fuente | `es` | `en` | Total |
|---|---:|---:|---:|
| `media_cloud` | 16 | 10 | 26 |
| `bluesky` | 1 | 13 | 14 |
| `gdelt` | 0 | 0 | 0 |
| **Total** | **17** | **23** (57,5 %) | **40** |

El mínimo de 15 % en inglés (6 preguntas) se cumple sin ajuste: 23 preguntas, 57,5 %.

**Variante con al menos 1 pregunta por fuente:** `media_cloud` 16 es + 9 en, `bluesky` 1 es + 13 en, `gdelt` 1 es. El total en inglés baja a 22 (55 %).

Referencia por periodo, sin las filas sin fecha: ≤ 2023: 13, 2024: 6, 2025: 7, 2026: 14.

## 8. Hallazgos que contradicen supuestos del enunciado o del diseño

| # | Supuesto | Hallazgo | Consecuencia |
|---:|---|---|---|
| H1 | El corpus es principalmente en español (diseño de chunking §8: "1,3 a 1,5 tokens por palabra en español") | El 55,99 % es en inglés, y el 90,05 % de Bluesky es en inglés | La estimación de tokens y chunks hay que medirla por idioma. Las preguntas en español sobre Bluesky tienen poca evidencia: 5.160 posts y 1 pregunta según la cuota. |
| H2 | Un mismo esquema de chunking sirve para todo el corpus (256 tokens, 48 de solapamiento, `min_tokens` 64) | Bluesky no pasa de 67 palabras (p99 = 56). *Hipótesis (pendiente de medir con el tokenizador de e5-small):* con un máximo de 67 palabras, se espera que cada post quepa en un chunk de 256 tokens | Si se confirma, el solapamiento y la regla de unión no aplicarían a Bluesky, y habría dos poblaciones de chunks (posts cortos y fragmentos de artículos) con densidad distinta, lo que puede sesgar la recuperación por plataforma (punto 6 del enunciado). Pendiente: medir `n_tokens` por fuente. |
| H3 | Se puede comparar prensa y Bluesky en la misma pregunta ("diversidad de fuentes", punto 1 del enunciado) | Solo coinciden de forma sustancial en 2025–2026: el 94,72 % de Bluesky es de esos años, contra el 26,12 % de `media_cloud` | Las preguntas comparativas entre fuentes deben limitarse a 2025–2026, o la falta de evidencia en una fuente se confundirá con un fallo de recuperación. |
| H4 | `created_at` permite análisis temporal fino (punto 6: fechas) | El 94,90 % de las fechas de `media_cloud` tiene solo día. Hay 290 posts de Bluesky fechados entre 2008 y 2021, antes de que la plataforma existiera, y ninguno en 2022–2023 | Hay que trabajar con resolución diaria. Las fechas de Bluesky anteriores a 2023 deberían marcarse como dudosas antes de usarlas en preguntas temporales o filtros. Que `created_at` dependa del cliente es una hipótesis por verificar. |
| H5 | La propagación noticia → red se puede medir con los grupos de duplicados | n = 0 grupos `media_cloud + bluesky`. Los 14 grupos mixtos son `gdelt + media_cloud` | La medida necesita otra definición (similitud de texto o URL compartida). Ver PI3. |
| H6 | Los duplicados son incidentales | 8 de los 10 grupos más grandes son posts de Bluesky en inglés repetidos entre 159 y 839 veces | El dedup ya los reduce a una fila, pero `dup_count` es una señal útil para el punto 6 del enunciado (contaminación, sesgos por plataforma) y conviene conservarla como metadato filtrable. |
| H7 | Cuotas "proporcionales por fuente" cubren todas las fuentes | `gdelt` (0,51 %) recibe 0 preguntas, y Bluesky en español solo 1 | Si se quiere cubrir `gdelt`, hay que usar la variante con mínimo 1 por fuente y declararlo como sobremuestreo deliberado. |

## 9. Reproducción

```bash
.venv/bin/python scripts/prepare_corpus.py --languages es en --output data/documentos_rag.parquet --stats docs/prepare_stats_es_en.json
.venv/bin/jupyter nbconvert --to notebook --execute notebooks/01_analisis_exploratorio.ipynb --output 01_analisis_exploratorio.ipynb
.venv/bin/nbstripout notebooks/01_analisis_exploratorio.ipynb
```

Dependencias del notebook: `requirements-dev.txt`.
