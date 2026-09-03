# Resumen técnico — cómo está construido el corpus y por qué

Documento de traspaso. Explica **qué se construyó, qué decisiones se tomaron y
con qué evidencia**, para que cualquiera pueda retomar el trabajo sin repetir el
análisis.

Complemento no técnico: [`05-resumen-del-proyecto.md`](05-resumen-del-proyecto.md).
Puesta en marcha: [`03-guia-del-equipo.md`](03-guia-del-equipo.md).

---

## 1. Qué es este servicio

Construye un corpus histórico de prensa colombiana para analizar después
diferencias de cobertura y framing entre medios. **Sólo adquiere datos.** El
análisis de parcialización es una etapa posterior y deliberadamente no vive aquí
(§32 del `CLAUDE.md`).

La prioridad de calidad, en este orden: reproducibilidad > trazabilidad >
comparabilidad > completitud > velocidad. Es preferible tener 10.000 artículos
bien identificados que 100.000 con metadata inconsistente.

---

## 2. Arquitectura

```text
config/*.yaml ──► catalog sync ──► tablas de catálogo (source, government, topic)

sitemap mensual ──► SitemapProvider ──► discovery_record ──► article
                          │                                    │
                    collection_chunk                      enrich (URL → título)
                    (checkpoint reanudable)                     │
                                                          extract (HTTP → titular,
                                                                   fecha, cuerpo)
                                                                │
                                                          clean_content
                                                                │
                                                            tag (topics.yaml)
                                                                │
                                                      export (parquet/csv/jsonl)
```

Stack: Python 3.12, SQLAlchemy 2 + Alembic, PostgreSQL 17 en Docker, Typer para
la CLI, httpx para red, trafilatura para el cuerpo, structlog para logs.

### Decisión central: sitemap-first, no GDELT

GDELT era el candidato obvio para 20 años de histórico. Se descartó como fuente
primaria tras medirlo, y los dos motivos están verificados empíricamente:

1. **Falla en silencio bajo saturación.** Devuelve `HTTP 200` con JSON válido
   pero con artículos de **otra época**. Cualquier integración tiene que validar
   que cada `seendate` caiga dentro de la ventana pedida; si no, mete ruido sin
   levantar ningún error.
2. **Sólo el 38 % de las consultas dentro de rango devuelven datos.** Los fallos
   son cuerpos vacíos con `HTTP 200`, indistinguibles de "no hubo noticias" si
   no se distingue explícitamente.

Los sitemaps mensuales de los medios, en cambio, son estables, gratuitos y
llegan mucho más atrás. Detalle completo en
[`01-research-and-architecture.md`](01-research-and-architecture.md), sección B.

---

## 3. Modelo de datos

```text
source ──< source_domain          un medio puede cambiar de dominio (RTVC)
  │
  ├──< collection_chunk           unidad reanudable: (medio, proveedor, año-mes)
  │        └──< discovery_record  observación cruda; se conserva aunque se rechace
  │                  └── article  entidad deduplicada
  │                        └──< article_topic   multi-etiqueta, versionado
  └──< archive_density            cuántas URLs ofreció cada medio cada mes

government   topic
```

Tres invariantes, y las tres tienen una razón concreta:

1. **Discovery y artículo están separados.** Permite responder "¿qué encontró
   cada proveedor?" y "¿qué se descartó y por qué?" sin adivinar.
2. **Nada se borra.** Los descartes se marcan con `rejected_reason`. Un artículo
   que ya no existe en el medio queda con `extraction_status = http_error`: la
   fila sigue documentando que se publicó.
3. **El etiquetado ocurre después del discovery**, no como filtro de búsqueda.
   Cambiar `topics.yaml` permite re-etiquetar todo sin volver a descargar nada
   (`tag --retag`), y `article_topic` guarda la versión de las reglas.

---

## 4. Las tres columnas que salvan el análisis

Son la parte del diseño que más veces evita una conclusión falsa. Cada una nació
de un problema real encontrado con los datos.

### `article.date_precision`

Los sitemaps traen `<lastmod>`, que es la fecha de **modificación**, no la de
publicación. En varios medios es un artefacto de migración del CMS:

| Medio | `lastmod` fuera del mes de su propio sitemap |
|---|---|
| Blu Radio | **100 %** |
| Noticias Caracol | 73 % |
| El Tiempo | 0 % |

Los sitemaps de Blu Radio de enero de 2013 traen `lastmod` de abril de 2016
mientras el slug dice `.../en-blu-jeans-1-de-enero-de-2013`. **El mes del
sitemap manda sobre `lastmod`.** De ahí los tres valores: `day` (fecha fiable),
`month` (sólo se conoce el mes), `unknown`.

Consecuencia: con precisión `month`, un artículo de un mes de posesión
presidencial **no recibe gobierno asignado**. Elegir uno sería inventar el dato.

La extracción corrige esto: `article:published_time` da la fecha real y sube la
precisión de `month` a `day`, reasignando el gobierno.

### `article.title_source`

`slug` = el título se reconstruyó de la URL (sin tildes, capitalización
inventada). `extracted` = es el titular publicado. Mezclarlos en un análisis
léxico mide de dónde salió el título, no qué palabras usó el medio.

Detalle que costó encontrar: El Tiempo usa el sufijo `+articulo+ID` en sus URLs.
Sin quitarlo, **"articulo" salía como la palabra más frecuente del medio**.

### tabla `archive_density`

Cuántas URLs ofreció cada medio cada mes. Existe por este dato:

| Mes | URLs en el sitemap de El Tiempo |
|---|---|
| 2013-01 | 48 |
| 2016-01 | 48 |
| 2016-02 | 39 |
| **2016-03** | **4.793** |

Un salto de ~120× en un mes. Comparar volumen de cobertura entre gobiernos sin
tener esto en cuenta mide el archivado y lo presenta como hallazgo. Por eso
`sources.yaml` distingue `archive_from` (hay archivo) de `reliable_from` (el
archivo es denso).

---

## 5. Extracción de contenido

`news-corpus extract` abre la página del artículo y saca titular, fecha, autor,
descripción y cuerpo **en una sola petición**. Es deliberado: volver a rastrear
los mismos sitios más adelante sólo para pedir el cuerpo duplicaría la carga
sobre medios que nos están dando su archivo gratis.

Orden de preferencia del titular: `og:title` → `<h1>` → JSON-LD `headline` →
`<title>`. El `<title>` va de último porque suele traer una versión abreviada
para la pestaña; se vio "Frustan robo de bebé en Cali" donde el titular real era
"Policía rescata a bebé robado a una mujer en ladera del sur de Cali".

Hay una lista de **titulares que no lo son** (`_BOILERPLATE_TITLES`). Algunas
páginas de archivo de El Tiempo traen `og:title`, `h1`, JSON-LD y `<title>`
todos con el mismo texto de navegación — verificado en
`/archivo/documento/MAM-5920374`, cuyo `og:title` es literalmente "Síganos". No
es fallo del parser: es la página. Se prefiere no tener título a registrar eso.

### Commit cada 25 artículos

No es una optimización. Una tanda de 150 artículos a 1 req/s mantiene la
transacción abierta ~2,5 minutos, y un corte la pierde entera. Pasó: recrear el
contenedor de Postgres tumbó la conexión y se perdieron 150 artículos ya
descargados. Confirmar cada 25 acota la pérdida y evita repetir peticiones.

Esa decisión se ganó su sitio durante esta misma sesión: Docker Desktop se
detuvo dos veces a media corrida y no se perdió nada más allá de la tanda en
curso.

### Limpieza del cuerpo

`clean_content()` elimina las líneas que son interfaz y no texto publicado:
`Publicidad`, `Actualizado: …`, `Síguenos en:`, `Lea también: …` y artefactos de
puntuación sueltos. Sólo borra **líneas completas** que coinciden con el patrón;
nunca recorta dentro de una frase, así que un párrafo que *menciona* la
publicidad se conserva íntegro.

Importa porque Noticias Caracol intercala un marcador `Publicidad` por cada
espacio de anuncio dentro del cuerpo: sin filtrarlo sería uno de los términos
más frecuentes del medio sin que ningún periodista lo haya escrito.

Un artículo cuyo texto era **sólo** interfaz queda con `content = NULL`, que es
la representación honesta de "esta página no tiene cuerpo".

`news-corpus clean-content` reaplica las reglas al texto ya guardado y recalcula
`content_hash`. Existe para que el corpus no acabe con dos criterios de limpieza
según la fecha en que se extrajo cada fila.

---

## 6. El hallazgo que condiciona el análisis

**Buena parte del archivo de algunos medios no contiene el cuerpo del
artículo.** Verificado leyendo el HTML crudo, no inferido del comportamiento del
extractor: hay páginas de Blu Radio de 2013 sin un solo párrafo de artículo,
sólo un reproductor (`Reproducir audio`), y páginas de Caracol con 63
referencias a vídeo y ningún `<p>` que no sea navegación. En esos casos
`trafilatura` devuelve exactamente lo mismo en `favor_precision`, por defecto y
`favor_recall`: no hay más texto que sacar.

| Medio | Página de archivo de 2013 | Artículos con cuerpo ≥500 car. |
|---|---|---|
| El Tiempo | la nota completa | **99 %** |
| Noticias Caracol | mezcla: notas escritas y fichas de vídeo | 19 % (ene) → 36 % (mar) |
| Blu Radio | mezcla: notas escritas y posts de audio | 10 % (ene) → 21 % (mar) |

No es un corte por año: es una proporción que sube, y se ve incluso dentro de
2013. Un muestreo de años posteriores (4 artículos por junio) sugiere que
Caracol es sólido hacia 2018 y Blu Radio hacia 2019; con n=4 eso orienta pero no
calibra. La medida buena es la del propio corpus (`news-corpus profile`).

**Consecuencia, y es más sutil que "faltan datos".** Sí existen 1.481 artículos
de Caracol y 1.090 de Blu Radio con cuerpo analizable en 2013. Pero **no son una
muestra aleatoria de su cobertura**: son las notas que ese medio publicó
escritas, frente a las que publicó como vídeo o audio. Analizar ese subconjunto
y presentarlo como "el lenguaje de Blu Radio en 2013" mide el subgénero de las
notas escritas, no al medio.

Para 2013 la comparación defendible entre los tres medios es sobre **titular y
sumario**, que existen para todos. Para comparar cuerpo contra cuerpo hay que
recolectar de 2019 en adelante.

---

## 7. Export

El dataset lleva, además de la metadata: `author`, `description`,
`extraction_status`, `content`, `content_hash` y `content_chars`, más las marcas
de procedencia `title_source`, `date_precision` y `archive_density_month`.

`--no-content` omite `content` y `content_hash` y nada más — aligera el archivo
sin perder trazabilidad. `content_chars` sobrevive al filtro a propósito, para
poder seleccionar los artículos analizables sin volver a exportar el texto.

> Nota de mantenimiento: el export nació **sin** `content`, `description` ni
> `author`. Todo el texto extraído se quedaba en la base y no llegaba al
> análisis. `tests/test_export_columns.py` fija el contrato de campos para que
> no vuelva a pasar.

---

## 8. Estado actual

| Fase | Estado |
|---|---|
| 1 · Research & Architecture | ✅ |
| 2 · Foundation (config, modelos, Postgres, CLI) | ✅ |
| 3 · `SitemapProvider` + bloques mensuales + checkpoints | ✅ |
| 4 · Normalización (fechas, URLs, mapeo de medios) | ✅ |
| 5 · Deduplicación (canonical URL + hash) | ✅ |
| 6 · `GDELTProvider` con validación de ventana | 🔴 |
| 7 · Enriquecimiento, etiquetado y export | ✅ (falta la API HTTP) |
| 8 · Métricas de densidad de archivo | ✅ |
| 9 · Extracción de contenido | ✅ |
| 9b · Common Crawl / Wayback como respaldo | 🔴 |

Cifras vigentes: [`dumps/MANIFEST.md`](../dumps/MANIFEST.md) y `news-corpus profile`.

---

## 9. Qué falta, en orden de utilidad

1. **Ampliar la ventana temporal.** Es lo que más valor añade y no requiere
   código nuevo: `collect` de 2019 en adelante, donde los tres medios tienen
   cuerpo, permitiría por fin la comparación de framing que motiva el proyecto.
2. **Agrupador de acontecimientos.** Hoy se aproxima en el notebook con
   coincidencia de palabras en titulares del mismo día. Un agrupador de verdad
   habilita el análisis de omisión y énfasis.
3. **API HTTP** (§21). La CLI cubre el uso actual; la API queda pendiente.
4. **`GDELTProvider`** (fase 6). Antes hay que barrer el espaciado (25/60/120 s)
   para encontrar el punto de operación real: el 38 % se midió con un solo
   dominio y un solo espaciado.
5. **Más medios.** `sources.yaml` tiene los 10 configurados con su estrategia de
   discovery verificada; sólo 3 están recolectados.

---

## 10. Cosas que conviene no repetir

- **No asumir que un `HTTP 200` significa éxito.** GDELT devuelve 200 con cuerpo
  vacío y con datos de otra época.
- **No tratar `lastmod` como fecha de publicación.**
- **No comparar volúmenes entre medios sin mirar `archive_density`.**
- **No mezclar títulos `slug` y `extracted` en un análisis léxico.**
- **No suponer que hay cuerpo porque hay artículo.**
- **No usar análisis de sentimiento como medida de parcialización.** Es, como
  mucho, una característica más.
