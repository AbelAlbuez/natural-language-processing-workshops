# Diagnóstico del corpus `dragons_rag`

Fecha del diagnóstico: 2026-10-25. Inspección de solo lectura con `pyarrow` 23.0.1. El archivo no fue modificado.
Este reporte no incluye texto de documentos.

## 1. Archivo e integridad

| Campo | Valor |
|---|---|
| Conjunto (catálogo `open_corpus_co_es` 0.1.1a4) | `dragons_rag` |
| Versión del catálogo (`fecha_version`) | 2026-10-19 |
| Ruta local | `/Users/abelalbuez/.open_corpus_co_es/data/dragons_rag/dragons_rag.parquet` |
| Tamaño en disco | 256.941.261 bytes |
| Tamaño de referencia | 256.941.261 bytes |
| SHA-256 calculado (bloques de 1 MB) | `f4a669f17eaedd357f72b70c2192e685b6d534a94f6ffaeadbced7290b181728` |
| SHA-256 de referencia | `f4a669f17eaedd357f72b70c2192e685b6d534a94f6ffaeadbced7290b181728` |
| Resultado | **Coincide** |

La descarga se hizo con `download_corpus('dragons_rag', force=False)`. La librería también valida el tamaño y el SHA-256 antes de mover el archivo a su ruta final.

## 2. Dimensiones

| Métrica | Esperado | Real | ¿Coincide? |
|---|---:|---:|:---:|
| Filas | 169.248 | 169.248 | Sí |
| Columnas | 33 | 33 | Sí |
| Row groups | — | 83 | — |

## 3. Esquema

| # | Columna | Tipo |
|---:|---|---|
| 1 | `document_id` | string |
| 2 | `text` | string |
| 3 | `collection_name` | string |
| 4 | `title` | string |
| 5 | `url` | string |
| 6 | `source` | string |
| 7 | `source_type` | string |
| 8 | `language` | string |
| 9 | `country_key` | string |
| 10 | `created_at` | string |
| 11 | `synced_at` | string |
| 12 | `mongo_id` | string |
| 13 | `strategy` | string |
| 14 | `url_domain` | string |
| 15 | `final_url` | string |
| 16 | `language_base` | string |
| 17 | `publisher` | string |
| 18 | `author_id` | string |
| 19 | `author_name` | string |
| 20 | `author_handle` | string |
| 21 | `uri` | string |
| 22 | `section` | string |
| 23 | `event_id` | string |
| 24 | `event_context` | string |
| 25 | `keyword_family` | string |
| 26 | `collection_keyword` | string |
| 27 | `collection_keyword_label` | string |
| 28 | `collection_query` | string |
| 29 | `keyword_matches` | list\<string\> |
| 30 | `top_terms` | list\<struct\<term: string, count: int64\>\> |
| 31 | `word_count` | int64 |
| 32 | `char_count` | int64 |
| 33 | `text_sha256` | string |

**Columnas esenciales:** las 11 están presentes con el nombre exacto: `document_id`, `text`, `collection_name`, `title`, `url`, `source`, `language`, `created_at`, `text_sha256`, `word_count` y `char_count`. No falta ninguna.

## 4. Nulos en columnas esenciales

| Columna | Nulos | % | Cadenas vacías | Observación |
|---|---:|---:|---:|---|
| `document_id` | 0 | 0,00 % | 0 | |
| `text` | 0 | 0,00 % | 0 | |
| `collection_name` | 0 | 0,00 % | — | |
| `title` | 64.670 | 38,21 % | 4 | Los 64.670 nulos son de `bluesky` (todas sus filas) |
| `url` | 0 | 0,00 % | — | |
| `source` | 0 | 0,00 % | — | |
| `language` | 13.137 | 7,76 % | — | Todos de `bluesky` |
| `created_at` | 23 | 0,01 % | — | Todos de `media_cloud` |
| `text_sha256` | 0 | 0,00 % | 0 | |
| `word_count` | 0 | 0,00 % | — | |
| `char_count` | 0 | 0,00 % | — | |

## 5. Unicidad y duplicados

| Métrica | Esperado | Real | ¿Coincide? |
|---|---:|---:|:---:|
| Valores únicos de `document_id` | 169.248 | 169.248 | Sí |
| Filas con `document_id` duplicado | 0 | 0 | Sí |
| Valores únicos de `text_sha256` | 154.477 | 154.477 | Sí |
| Filas con `text_sha256` repetido (filas − únicos) | 14.771 | 14.771 | Sí |

Las 14.771 filas repetidas son las que sobran después de dejar una por cada `text_sha256`.

## 6. Distribución por fuente

### `source`

| Fuente | Esperado | Real | % | ¿Coincide? |
|---|---:|---:|---:|:---:|
| `media_cloud` | 103.380 | 103.380 | 61,08 % | Sí |
| `bluesky` | 64.670 | 64.670 | 38,21 % | Sí |
| `gdelt` | 1.198 | 1.198 | 0,71 % | Sí |
| **Total** | 169.248 | 169.248 | 100,00 % | Sí |

### `collection_name`

| Valor | Filas | % |
|---|---:|---:|
| `url_crawls` | 104.578 | 61,79 % |
| `bluesky_posts` | 64.670 | 38,21 % |

`url_crawls` = `media_cloud` + `gdelt` (103.380 + 1.198).

### `source_type`

| Valor | Filas | % |
|---|---:|---:|
| (nulo) | 99.326 | 58,69 % |
| `social_post` | 64.670 | 38,21 % |
| `news_article` | 5.252 | 3,10 % |

## 7. Idioma

### `language` (valor original)

La columna tiene 118 valores distintos, sin contar el nulo. Mezcla códigos de idioma y de región, y usa mayúsculas y minúsculas sin uniformidad (`en-gb`/`en-GB`, `en-us`/`en-US`). También aparecen códigos que parecen de país (`co`, `mx`, `us`, `au`, …).

| Valor | Filas | % |
|---|---:|---:|
| `en` | 76.642 | 45,28 % |
| `es` | 54.918 | 32,45 % |
| (nulo) | 13.137 | 7,76 % |
| `es-co` | 4.668 | 2,76 % |
| `hu` | 4.108 | 2,43 % |
| `en-global` | 3.720 | 2,20 % |
| `es-mx` | 3.698 | 2,18 % |
| `es-es` | 2.011 | 1,19 % |
| `en-gb` | 1.174 | 0,69 % |
| `es-ar` | 809 | 0,48 % |
| Otros 109 valores | 4.363 | 2,58 % |

### `language_base` (columna normalizada incluida en el corpus)

| Valor | Filas | % |
|---|---:|---:|
| `en` | 82.682 | 48,85 % |
| `es` | 66.908 | 39,53 % |
| (nulo) | 13.137 | 7,76 % |
| `hu` | 4.133 | 2,44 % |
| `de` | 557 | 0,33 % |
| `pt` | 468 | 0,28 % |
| `fr` | 307 | 0,18 % |
| `nl` | 204 | 0,12 % |
| Otros | 852 | 0,50 % |

## 8. Fechas (`created_at`)

`created_at` está guardada como **texto** (string), no como timestamp. Tiene al menos 10 formatos distintos; el más común es `AAAA-MM-DD` (99.297 filas), seguido de ISO 8601 con hora y zona horaria en variantes como `Z`, `±HH:MM`, sin zona o con 3 a 9 decimales. Todos los valores no nulos se pudieron convertir a fecha con `pandas.to_datetime(format="mixed", utc=True)`, sin errores.

| Fuente | Mínimo | Máximo |
|---|---|---|
| **Global** | 2006-08-24 | 2026-09-21 18:03:56 UTC |
| `bluesky` | 2008-07-19 22:26:45 UTC | 2026-09-11 23:58:04 UTC |
| `media_cloud` | 2011-01-07 | 2026-09-20 |
| `gdelt` | 2006-08-24 | 2026-09-21 18:03:56 UTC |

| Corte | Filas |
|---|---:|
| `created_at` anterior a 2025-01-01 | 77.967 |
| `created_at` anterior a 2026-01-01 | 106.829 |
| `created_at` nulo | 23 |

## 9. Longitud del texto

| Métrica | Mínimo | Máximo | Media |
|---|---:|---:|---:|
| `word_count` | 1 | 58.181 | 473,30 |
| `char_count` | 40 | 363.528 | 2.976,63 |

## 10. Resumen de discrepancias

- Filas, columnas, fuentes, `document_id` únicos y textos únicos **coinciden** con el catálogo.
- No falta ninguna columna esencial.
- Observaciones para el preprocesamiento. No son discrepancias con el catálogo:
  - `title` es nulo en todos los posts de Bluesky (64.670).
  - `language` es nulo en 13.137 posts de Bluesky. Además tiene 118 valores sin normalizar; `language_base` es más limpia.
  - `created_at` es texto con formatos mezclados y 23 nulos (Media Cloud). Hay que convertirla antes de filtrar por fecha.
  - Hay 14.771 filas con texto duplicado (`text_sha256`) que conviene deduplicar antes del chunking.
  - Los textos son muy largos en algunos casos: hasta 58.181 palabras y 363.528 caracteres.

## 11. Preparación para RAG (`scripts/prepare_corpus.py`)

Fecha: 2026-10-25. El parquet original no se modifica; el resultado se escribe en un archivo nuevo.

```
.venv/bin/python scripts/prepare_corpus.py
# equivalente a: --languages es --lid-model models/lid.176.bin --lid-threshold 0.5 --min-words 5 \
#                --output data/documentos_rag.parquet
```

Para incluir inglés más adelante, sin cambiar código: `--languages es en`.

### Reglas aplicadas

| Paso | Regla |
|---|---|
| 1. Duplicados | Una fila por `text_sha256`. Se conserva primero la que tiene `title` no vacío y, si empatan, la de `created_at` más antiguo (los nulos van al final). |
| 2. Idioma | Se usa `language_base`. Si es nulo, se detecta con fastText `lid.176.bin` (`fasttext-numpy2` 0.10.4). Si la probabilidad es menor que 0,5, se marca como `und` y se excluye. Se conservan solo los idiomas de `--languages` (por defecto `es`). |
| 3. Fecha | Se agrega `created_at_utc` (timestamp UTC, precisión de ns) a partir de `created_at`. No se filtra por fecha. |
| 4. Longitud | Se descartan las filas con `word_count` < 5. |

### Filas eliminadas en cada paso

| Paso | Filas antes | Eliminadas | Filas después |
|---|---:|---:|---:|
| Entrada | — | — | 169.248 |
| 1. Duplicados por `text_sha256` | 169.248 | 14.771 | 154.477 |
| 2. Idioma distinto de `es` (incluye las `und`) | 154.477 | 89.781 | 64.696 |
| 3. Normalización de fecha | 64.696 | 0 | 64.696 |
| 4. Menos de 5 palabras | 64.696 | 30 | **64.666** |

### Detección con fastText (filas sin `language_base`, tras deduplicar)

Las 12.005 filas sin `language_base` eran todas de `bluesky`.

| Resultado | Filas | % de las detectadas |
|---|---:|---:|
| `es` (probabilidad ≥ 0,5) | 1.930 | 16,08 % |
| Otro idioma (probabilidad ≥ 0,5) | 8.402 | 69,99 % |
| `und` (probabilidad < 0,5) | 1.673 | 13,94 % |
| **Total** | 12.005 | 100,00 % |

En las 1.930 filas conservadas, `lang_prob` va de 0,530 a 1, con una mediana de 0,925.

### Aclaración sobre `und`

`und` **no se conserva**. La etiqueta de la fila 2 en la versión anterior de la tabla ("Idioma distinto de `es` o `und`") se prestaba a leer que sí. En el código (`scripts/prepare_corpus.py`, función `detect` y filtro `meta.lang.isin(args.languages)`), una detección con probabilidad < 0,5 recibe `lang = 'und'`. Como `und` no está en `--languages` (por defecto `['es']`), esas filas se eliminan en el **paso 2**, junto con los demás idiomas.

Desglose de las 89.781 filas eliminadas en el paso 2:

| Motivo | Filas |
|---|---:|
| `language_base` distinto de `es` | 79.706 |
| fastText detectó otro idioma (probabilidad ≥ 0,5) | 8.402 |
| fastText con probabilidad < 0,5 → `und` | 1.673 |
| **Total** | **89.781** |

Comprobación en `data/documentos_rag.parquet`: hay 0 filas con `lang = 'und'` y 0 filas con `lang_source` distinto de `language_base` o `fasttext`. De las 1.673 filas `und`, 1.667 tienen 5 palabras o más, así que pasarían el filtro de longitud si se decidiera conservarlas.

## 12. Pendientes

### P1. Las copias eliminadas por duplicado no dejan rastro (sin corregir; requiere confirmación)

**Hallazgo.** En el paso 1, `scripts/prepare_corpus.py` aplica `drop_duplicates('text_sha256', keep='first')` y conserva solo los metadatos de la fila elegida. Los `document_id`, `url` y `source` de las otras copias **no se guardan** en ninguna columna. El parquet de salida no permite saber qué documentos se fusionaron.

Magnitud en el corpus completo, antes del filtro de idioma:

| Métrica | Valor |
|---|---:|
| Grupos de `text_sha256` con más de una fila | 4.434 |
| Filas en esos grupos | 19.205 |
| Copias descartadas | 14.771 |
| Grupo más grande | 839 filas |
| Grupos con más de una `url` distinta | 4.420 |
| Grupos con más de una `source` | 18 |

Esto afecta la trazabilidad de las citas y el análisis de duplicados que pide el punto 6 de `docs/EVALUACION.md`.

**Cambio propuesto.** Agregar cuatro columnas: `dup_count` (int64), `dup_document_ids`, `dup_urls` y `dup_sources` (list\<string\>, en el orden original de filas e incluyendo la fila conservada). El resto del pipeline no cambia; el número de filas sería el mismo (64.666) y el parquet pasaría de 37 a 41 columnas.

```diff
--- a/scripts/prepare_corpus.py
+++ b/scripts/prepare_corpus.py
@@ def main():
-    meta = table.select(['text_sha256', 'title', 'created_at', 'language_base', 'word_count', 'source']).to_pandas()
+    meta = table.select(['text_sha256', 'title', 'created_at', 'language_base', 'word_count', 'source',
+                         'document_id', 'url']).to_pandas()
     meta['row'] = range(len(meta))
 
     # 1. Duplicados por text_sha256: primero la fila con title no vacío, luego la de created_at más antiguo.
     meta['created_at_utc'] = pd.to_datetime(meta.created_at, utc=True, errors='coerce', format='mixed')
     meta['has_title'] = meta.title.fillna('').str.strip().str.len() > 0
+    # Procedencia de todas las copias (incluida la conservada), para no perder trazabilidad.
+    copies = meta.groupby('text_sha256', sort=False).agg(
+        dup_document_ids=('document_id', list), dup_urls=('url', list), dup_sources=('source', list))
+    copies['dup_count'] = copies.dup_document_ids.str.len()
     meta = (meta.sort_values(['has_title', 'created_at_utc', 'row'], ascending=[False, True, True], na_position='last')
                 .drop_duplicates('text_sha256', keep='first').sort_values('row'))
+    meta = meta.join(copies, on='text_sha256')
     stats['rows_after_dedup'] = len(meta)
@@ def main():
     out = out.append_column('created_at_utc', pa.array(meta.created_at_utc, pa.timestamp('ns', tz='UTC')))
+    out = out.append_column('dup_count', pa.array(meta.dup_count.to_numpy(), pa.int64()))
+    for c in ('dup_document_ids', 'dup_urls', 'dup_sources'):
+        out = out.append_column(c, pa.array(meta[c].tolist(), pa.list_(pa.string())))
     os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
```

`groupby` mantiene el orden original de las filas dentro de cada grupo porque `meta` aún no se ha reordenado en ese punto. Aplicarlo exige volver a ejecutar el script y regenerar `data/documentos_rag.parquet`.

### P2. Decisión de idiomas (pendiente del equipo)

Cifras calculadas en memoria sobre `dragons_rag.parquet`, con la misma lógica del script (dedup → idioma → ≥ 5 palabras), sin escribir archivos:

| Escenario | Eliminadas por idioma | Eliminadas por longitud | Filas finales |
|---|---:|---:|---:|
| `--languages es` (actual) | 89.781 | 30 | 64.666 |
| `--languages es en` | 7.050 | 504 | 146.923 |

Desglose de `es en`:

| Fuente | `es` | `en` | Total |
|---|---:|---:|---:|
| `media_cloud` | 59.125 | 35.176 | 94.301 |
| `bluesky` | 5.160 (3.230 `language_base` + 1.930 fastText) | 46.716 (38.491 `language_base` + 8.225 fastText) | 51.876 |
| `gdelt` | 381 | 365 | 746 |
| **Total** | **64.666** | **82.257** | **146.923** |

Fuera de `es` y `en` quedan 6.989 filas con 5 palabras o más. Las más comunes: `hu` 3.084, `und` 1.667, `pt` 507, `de` 504, `fr` 277, `nl` 166, `ja` 99 e `it` 95. Por fuente: bluesky 3.838, media_cloud 2.811 y gdelt 340.

### Resultado: `data/documentos_rag.parquet`

| Campo | Valor |
|---|---|
| Ruta | `data/documentos_rag.parquet` (ignorado por git: regla `data/`) |
| Tamaño | 117.491.207 bytes (compresión zstd) |
| Filas | 64.666 |
| Columnas | 37: las 33 originales + `lang`, `lang_source`, `lang_prob`, `created_at_utc` |
| `text_sha256` / `document_id` duplicados | 0 / 0 |
| `created_at_utc` nulo | 23 (todos de `media_cloud`) |
| Rango de `created_at_utc` | 2010-06-12 16:43:39 UTC → 2026-09-21 18:03:56 UTC |

| Fuente | Idioma | Origen del idioma | Filas | % |
|---|---|---|---:|---:|
| `media_cloud` | `es` | `language_base` | 59.125 | 91,43 % |
| `bluesky` | `es` | `language_base` | 3.230 | 4,99 % |
| `bluesky` | `es` | `fasttext` | 1.930 | 2,98 % |
| `gdelt` | `es` | `language_base` | 381 | 0,59 % |
| **Total** | | | **64.666** | 100,00 % |

Por fuente: `media_cloud` 59.125 (91,43 %), `bluesky` 5.160 (7,98 %), `gdelt` 381 (0,59 %). `title` es nulo en las 5.160 filas de Bluesky.
