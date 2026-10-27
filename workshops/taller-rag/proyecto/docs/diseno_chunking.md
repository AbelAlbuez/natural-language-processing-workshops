# Diseño del chunking

Estado: **propuesta, sin ejecutar**. Entrada: `data/documentos_rag.parquet`, con 64.666 filas en la configuración actual (`--languages es`). Ver `docs/diagnostico_corpus.md`, secciones 11 y 12.

## 1. Punto de partida

| Elemento | Situación actual |
|---|---|
| Modelo de embeddings | `intfloat/multilingual-e5-small` (`app/core.py`, `EMBEDDING_MODEL`). Antepone `passage: ` a los documentos y `query: ` a las consultas. |
| Chunking actual | `scripts/ingest.py::split`: ventanas de **1.000 caracteres** con 150 de solapamiento, sin tokenizador. |
| Prueba existente | `tests/test_chunking.py` exige que `text[offset:offset+len(chunk)] == chunk`. Las dos estrategias de este diseño mantienen esa propiedad. |
| ID actual | `sha256(document_id|offset|size|overlap)[:32]` |
| Esquema Milvus actual | `chunk_id`, `vector`, `text` (max_length 12.000), `document_id`, `title`, `url`, `collection_name`, `source`, `position`. No tiene `created_at_utc`, `lang` ni `char_end`. |

Longitud del corpus preparado (en palabras, `word_count`):

| Fuente | Filas | p50 | p90 | p95 | p99 | Máx. |
|---|---:|---:|---:|---:|---:|---:|
| `media_cloud` | 59.125 | 618 | 1.194 | 1.584 | 2.736 | 58.181 |
| `gdelt` | 381 | 507 | 1.174 | 1.563 | 2.444 | 3.952 |
| `bluesky` | 5.160 | 31 | 46 | 49 | 53 | 60 |
| **Todas** | 64.666 | 589 | 1.152 | 1.537 | 2.676 | 58.181 |

Hay 8.865 documentos con más de 1.000 palabras, 137 con más de 5.000, 73 con más de 10.000 y 49 con más de 20.000, todos de `media_cloud`. En total suman 44.246.240 palabras.

## 2. Tokenizador

**Propuesta: el tokenizador del propio modelo de embeddings, `intfloat/multilingual-e5-small`** (SentencePiece de XLM-RoBERTa, vocabulario de unos 250.000 tokens, versión *fast* de `transformers`).

Justificación:

- **El límite que importa es el del modelo.** e5-small trunca en 512 tokens, contando `<s>`, `</s>` y el prefijo `passage: `. Si se mide con otro tokenizador (palabras, `tiktoken`, NLTK), un chunk "de 512" puede pasar de ese límite y el modelo cortaría el final sin avisar.
- **Es multilingüe.** Si después se agrega `en` (sección 12 del diagnóstico), no hay que cambiarlo.
- **La versión *fast* devuelve `offset_mapping`.** Con eso cada token se traduce a una posición de carácter en `text`, y los offsets se guardan en caracteres, que es lo que valida el test actual.
- **No requiere descarga adicional.** Viene con el modelo que se descargará para generar los embeddings. **Todavía no se ha descargado.**

Presupuesto por chunk: 512 − 2 (especiales) − tokens de `passage: ` (unos 3; medir) ≈ **507**. Como margen, se fija un **tope de 500 tokens de contenido**.

## 3. Estrategia A: tamaño fijo en tokens con solapamiento

| Parámetro | Valor inicial | Variante para experimentar |
|---|---:|---:|
| `chunk_tokens` | 256 | 384 / 500 |
| `overlap_tokens` | 48 (≈ 19 %) | 64 |
| `min_tokens` del último chunk | 64. Si es menor, se une al anterior, siempre que la suma no pase de 500. | — |
| `strategy` | `fixed_tok` | — |

**Algoritmo.**
1. Tokenizar `text` completo, sin truncar y sin tokens especiales, pidiendo `return_offsets_mapping=True`.
2. Tomar ventanas `[i, i + chunk_tokens)` con paso `chunk_tokens − overlap_tokens`.
3. Para cada ventana: `char_start = offsets[i][0]` y `char_end = offsets[j−1][1]`.
4. Guardar `chunk_text = text[char_start:char_end]`. Es un *slice* exacto del original, no texto reconstruido desde los tokens.

**Ventajas:** el tamaño es predecible, el costo de embeddings es fácil de calcular y es fácil compararla con `split()`.
**Desventajas:** corta oraciones y párrafos a la mitad.

## 4. Estrategia B: oraciones o párrafos con límite de tokens

| Parámetro | Valor inicial |
|---|---:|
| `max_tokens` | 256 (tope 500) |
| `min_tokens` | 64 (un chunk más corto se une al siguiente) |
| `overlap_units` | 1 oración (la última del chunk anterior se repite al inicio del siguiente) |
| `strategy` | `sent_tok` |

**Algoritmo.**
1. **Párrafos.** Se separa por `\n\s*\n` y, si no hay párrafos, por `\n`. Cada segmento conserva su `char_start` y `char_end` en `text`.
2. **Oraciones.** Dentro de cada párrafo se divide con una expresión regular sobre `[.!?…]` seguida de espacio y mayúscula o comilla, con excepciones para abreviaturas comunes en español (`Sr.`, `Dra.`, `EE. UU.`, `art.`, `núm.`). Se propone una expresión regular porque `punkt` de NLTK requiere descargar datos aparte. Se guardan los offsets de cada oración.
3. **Empaquetado.** Se acumulan oraciones mientras la suma de tokens no pase de `max_tokens`. Se intenta no cruzar el límite de un párrafo salvo que el chunk siga por debajo de `min_tokens`.
4. **Oración demasiado larga.** Si una oración pasa de `max_tokens` (tablas, listados o texto mal extraído), se parte con la Estrategia A solo dentro de esa oración.
5. El chunk es `text[char_start_primera_oración:char_end_última_oración]`, siempre un *slice* contiguo del original.

**Ventajas:** los fragmentos son coherentes y las citas, más legibles.
**Desventajas:** el tamaño varía y depende de la calidad de los saltos de línea, que en las páginas rastreadas por Media Cloud puede ser irregular.

## 5. Offsets

Igual en las dos estrategias:

| Campo | Tipo | Definición |
|---|---|---|
| `char_start` | int64 | Índice (en caracteres Python, no bytes) del primer carácter del chunk en `text` |
| `char_end` | int64 | Índice exclusivo del final: `chunk_text == text[char_start:char_end]` |
| `chunk_index` | int32 | Posición del chunk dentro del documento (0, 1, 2…) |
| `n_chunks` | int32 | Total de chunks del documento |
| `n_tokens` | int32 | Tokens de contenido según el tokenizador de e5 |

`char_start` reemplaza a `position` en Milvus, o se guarda en ese mismo campo. Se agrega `char_end`. Se amplía `tests/test_chunking.py` para que cubra las dos estrategias, texto con tildes y emojis (índices en caracteres, no en bytes), y documentos de un solo chunk.

## 6. ID estable

```
chunk_id = sha256(f"{document_id}|{strategy}|{params_version}|{chunk_index}|{char_start}|{char_end}").hexdigest()[:32]
```

- `strategy`: `fixed_tok` o `sent_tok`.
- `params_version`: cadena canónica de los parámetros, por ejemplo `t256-o48-m64-e5small`. Así dos configuraciones nunca comparten ID.
- Con los offsets en el hash, el ID cambia si cambia el texto del documento, y se evita reutilizar un ID para un contenido distinto.
- Es determinista: volver a ejecutar con la misma entrada y los mismos parámetros produce los mismos IDs, y `upsert` en Milvus es idempotente.
- 32 hex = 128 bits, dentro del `max_length=128` de la clave primaria.
- Se recomienda una colección de Milvus distinta por `strategy` + `params_version`, para no mezclar variantes al comparar (punto 3 de `docs/EVALUACION.md`).

## 7. Procedencia que hereda cada chunk

| Campo | Origen | Uso |
|---|---|---|
| `document_id` | documento | Enlace con el gold standard y deduplicación de resultados |
| `url` | documento | Cita |
| `title` | documento (vacío en Bluesky; ver §9) | Cita y visualización |
| `source` | documento | Análisis de sesgo por plataforma |
| `collection_name` | documento | Ya existe en el esquema |
| `created_at_utc` | documento | Filtros y análisis por fecha. En Milvus se guarda como INT64 (epoch en segundos) o VARCHAR ISO 8601. 23 documentos no tienen fecha; se usa un valor centinela documentado, como −1 o "". |
| `lang`, `lang_source` | documento | Análisis por idioma |
| `text_sha256` | documento | Vínculo con el grupo de duplicados |
| `dup_count` | documento (solo si se aprueba P1 del diagnóstico) | Peso o análisis de duplicados; las listas completas quedan en el parquet, no en Milvus |
| `strategy`, `params_version` | configuración | Reproducibilidad |
| `char_start`, `char_end`, `chunk_index`, `n_chunks`, `n_tokens` | chunking | Trazabilidad de la cita |

Además del índice en Milvus, se propone guardar los chunks en `data/chunks_<strategy>_<params_version>.parquet` (ignorado por git), para auditar sin depender del contenedor.

## 8. Documentos muy largos

El máximo es 58.181 palabras. Con unos 1,3 a 1,5 tokens por palabra en español (estimación; se medirá con el tokenizador), eso equivale a entre 75.000 y 90.000 tokens, es decir, cerca de 360 a 430 chunks de 256 tokens con la Estrategia A. Para el corpus completo (44,2 millones de palabras), la estimación gruesa es de 250.000 a 320.000 chunks.

Propuesta:

1. **No truncar el texto en el chunking.** Todos los offsets siguen siendo válidos sobre `text`.
2. **Revisar antes los 137 documentos de más de 5.000 palabras.** Muchos pueden ser páginas rastreadas con menús, comentarios o varios artículos juntos. Se revisa una muestra a mano (sin copiar texto en reportes) y se decide si se excluyen con una regla explícita; por ejemplo, `word_count > N` o una proporción alta de líneas repetidas.
3. **Límite de chunks por documento** (`max_chunks_per_doc`, por ejemplo 64) solo para la ingesta piloto, registrando cuántos documentos se recortaron. En la ingesta final, sin límite o con un límite justificado.
4. **Recuperación:** como un documento largo aporta muchos chunks, se propone agrupar los resultados por `document_id` (máximo 2 chunks por documento en el top-k), para que un solo documento no ocupe todo el contexto (`MAX_CONTEXT_CHARS=8500`).
5. **Tokenización por lotes:** los documentos se tokenizan uno a la vez, sin cargar todo el corpus tokenizado en memoria.

## 9. Bluesky sin título

Los 5.160 posts de Bluesky no tienen `title`. Además, son cortos: como máximo 60 palabras y 307 caracteres, así que caben en **un solo chunk** con cualquiera de las dos estrategias.

Propuesta:

- **No inventar un título** ni copiar el inicio del texto en `title`. Se guarda `title = ""` y se mantiene la distinción entre "sin título" y "título real".
- **Para mostrar y citar** en la interfaz, se construye una etiqueta a partir de metadatos: `Bluesky · @author_handle · AAAA-MM-DD`. Esto requiere agregar `author_handle` a las columnas que lee la ingesta.
- **Embeddings:** el texto que se vectoriza es `passage: ` + chunk, sin título, en las dos fuentes. Variante para experimentar más adelante: anteponer `title` al chunk solo en el texto a vectorizar de las noticias (`passage: {title}\n{chunk}`), manteniendo `chunk_text` y los offsets sin el título. Bluesky queda igual porque no tiene título.
- **No unir varios posts** en un mismo chunk: cada post es un documento con su propia procedencia.

## 10. Decisiones pendientes antes de ejecutar

1. Idiomas: `es` o `es en` (diagnóstico, §12 P2). Esto cambia el corpus de 64.666 a 146.923 documentos.
2. Aplicar o no la trazabilidad de duplicados (diagnóstico, §12 P1) antes de regenerar el parquet.
3. Estrategia inicial (A, B o ambas en colecciones separadas) y parámetros (`chunk_tokens` 256 o 384).
4. Regla para documentos de más de 5.000 palabras y `max_chunks_per_doc` para el piloto.
5. Cambios en el esquema de Milvus (`app/core.py`): `char_end`, `created_at_utc`, `lang`, `chunk_index`, `strategy`.
6. Nombre de la colección. `.env.example` usa `rag_demo_bge_small_v1`, pero el modelo configurado es e5-small, y el nombre debería reflejar el modelo y la estrategia.
