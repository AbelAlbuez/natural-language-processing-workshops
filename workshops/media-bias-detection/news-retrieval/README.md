# News Corpus — corpus histórico de prensa colombiana

Servicio de adquisición de un corpus histórico de noticias de medios
tradicionales colombianos (2006–2026), para análisis posterior de NLP.

**Este servicio sólo construye el corpus.** El análisis de framing, léxico o
parcialización pertenece a una etapa posterior y no se implementa aquí (§32 del
`CLAUDE.md`).

---

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Research & Architecture | ✅ Completado — [`docs/01-research-and-architecture.md`](docs/01-research-and-architecture.md) |
| 2 | Foundation: configuración, modelos, Postgres, CLI | ✅ Completado |
| 3 | `SitemapProvider` + bloques mensuales + checkpoints | ✅ Completado |
| 4 | Normalización (fechas, URLs, mapeo de medios) | ✅ Completado |
| 5 | Deduplicación (canonical URL + hash) | ✅ Completado |
| 6 | `GDELTProvider` con validación de ventana | 🔴 Pendiente |
| 7 | Enriquecimiento, etiquetado temático y export | ✅ Completado (falta API) |
| 8 | Métricas de densidad de archivo | ✅ Completado |
| 9 | Extracción de contenido (titular, fecha y cuerpo reales) | ✅ Completado |
| 9b | Common Crawl / Wayback como respaldo | 🔴 Pendiente |

---

## ¿Sólo quieres los datos?

No hace falta recolectar nada. El corpus viaja como volcado de la base:

```bash
docker compose up -d
./scripts/restore-db.sh
news-corpus profile
```

Paso a paso en [`docs/03-guia-del-equipo.md`](docs/03-guia-del-equipo.md).

---

## Puesta en marcha

Requisitos: Docker, Python 3.12+, [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env          # ajustar si el puerto 5433 está ocupado
uv venv --python 3.12
uv pip install -e ".[dev,export]"
source .venv/bin/activate

docker compose up -d          # Postgres 17 en localhost:5433
alembic upgrade head          # crea el esquema
news-corpus catalog sync      # carga config/*.yaml en la base
```

Comprobación:

```bash
news-corpus catalog check         # valida los YAML sin tocar la base
news-corpus catalog sources       # medios y su cobertura verificada
news-corpus catalog governments   # los cinco gobiernos del horizonte
news-corpus which-government 2013-05-20
news-corpus status                # bloques y artículos
pytest -q
```

## Recolectar

```bash
# Ver el plan sin ejecutar nada
news-corpus collect -s el_tiempo --from 2013-01 --to 2013-03 --dry-run

# Recolectar de verdad (bloques mensuales, reanudable e idempotente)
news-corpus collect -s el_tiempo -s noticias_caracol -s blu_radio \
  --from 2013-01 --to 2013-03

news-corpus retry-failed          # reintenta los bloques en FAILED
```

## Analizar

```bash
news-corpus enrich                # deriva título y sección desde la URL
news-corpus extract               # abre la página: titular, fecha y cuerpo reales
news-corpus extract --all         # también los que ya tenían título de slug
news-corpus clean-content         # re-limpia el cuerpo con las reglas actuales
news-corpus tag                   # etiqueta con config/topics.yaml
news-corpus profile               # radiografía: qué se puede analizar y qué no
news-corpus export -o exports/corpus.parquet     # parquet | csv | jsonl
news-corpus export -o exports/meta.csv -F csv --no-content   # sólo metadata

uv pip install -e ".[notebook]"
jupyter lab notebooks/02-guia-del-corpus.ipynb   # guía tabla por tabla
python notebooks/01-exploracion-corpus.py        # exploración rápida en consola
```

### JupyterLab en Docker

Alternativa a instalar nada en el host: el servicio `jupyter` del
`docker-compose.yml` levanta JupyterLab ya conectado a la base.

```bash
docker compose up -d jupyter        # construye la imagen la primera vez
open http://localhost:8888/lab?token=news-corpus
```

| | |
|---|---|
| Puerto | `JUPYTER_PORT` en `.env` (8888) |
| Token | `JUPYTER_TOKEN` en `.env` (`news-corpus`) — cámbialo si expones el puerto |
| Raíz del árbol | el repo completo, montado en `/workspace` |

Lo que hay que saber:

- **El repo entero va montado**, no sólo `notebooks/`: editar en el host se ve
  al instante en el contenedor y al revés. Un `news-corpus export -o
  exports/corpus.parquet` lanzado desde la terminal de JupyterLab deja el
  archivo en `exports/` del host.
- **`src/` se ejecuta desde el montaje** (`PYTHONPATH=/workspace/src`), así que
  tocar el código no obliga a reconstruir la imagen. Sí hay que reconstruir al
  cambiar dependencias: `docker compose build jupyter`.
- **Dentro del contenedor la base es `postgres:5432`, no `localhost:5433`.** El
  servicio ya exporta `DB_HOST`/`DB_PORT` correctos y esas variables ganan al
  `.env`, de modo que `get_settings()` resuelve la URL sola: el mismo notebook
  corre dentro y fuera de Docker. `psql` y la CLI `news-corpus` están
  instalados en la imagen.
- `notebooks/00-conexion-db.py` comprueba la conexión de punta a punta.
- El `.venv` del host queda tapado por un volumen anónimo: son binarios de
  macOS, inservibles dentro del contenedor.

| Documento | Para qué |
|---|---|
| [`docs/03-guia-del-equipo.md`](docs/03-guia-del-equipo.md) | **Empieza aquí.** Cargar el corpus en 6 pasos, sin recolectar nada |
| [`docs/04-resumen-tecnico.md`](docs/04-resumen-tecnico.md) | Cómo está construido y por qué: decisiones y evidencia |
| [`docs/05-resumen-del-proyecto.md`](docs/05-resumen-del-proyecto.md) | Lo mismo sin tecnicismos, para retomar el trabajo |
| [`notebooks/03-analisis-del-corpus.ipynb`](notebooks/03-analisis-del-corpus.ipynb) | Qué preguntas puede responder el corpus y con qué filtros |
| [`notebooks/02-guia-del-corpus.ipynb`](notebooks/02-guia-del-corpus.ipynb) | Qué guarda cada tabla y por qué, con consultas ejecutables |
| [`notebooks/00-conexion-db.py`](notebooks/00-conexion-db.py) | Comprobar la conexión a la base desde el notebook |
| [`docs/02-consultas.md`](docs/02-consultas.md) | Conexión y recetario de SQL |
| [`dumps/MANIFEST.md`](dumps/MANIFEST.md) | Qué contiene el volcado del corpus |

Consultar directamente la base también es válido:

```bash
docker exec -it news-corpus-db psql -U news_corpus -d news_corpus
```

Repetir un rango ya recolectado no vuelve a descargar ni duplica artículos: los
bloques completados se saltan. `--force` los reprocesa.

---

## Configuración

Todo lo variable vive en `config/` y se recarga con `catalog sync`. No hay
medios, fechas ni palabras clave dentro del código (§20).

| Archivo | Contenido |
|---|---|
| `config/sources.yaml` | Los 10 medios, sus dominios y la **estrategia de discovery verificada** en Fase 1 |
| `config/governments.yaml` | Los 5 gobiernos que delimitan el corpus |
| `config/topics.yaml` | Jerarquía temática de 7 raíces y 42 temas |

Dos campos de `sources.yaml` merecen atención:

- **`archive_from`** — la fecha más antigua para la que existe archivo.
- **`reliable_from`** — desde cuándo ese archivo es *denso*.

En El Tiempo valen **1990-01** y **2016-03**, y esa diferencia es deliberada.
Medido con la tabla `archive_density` del propio corpus:

| Mes | URLs en el sitemap |
|---|---|
| 2013-01 | 48 |
| 2016-01 | 48 |
| 2016-02 | 39 |
| **2016-03** | **4.793** |

El salto es de ~120× en un solo mes. Comparar volumen de cobertura entre
gobiernos sin tener en cuenta esa brecha mide el archivado y lo presenta como
hallazgo. Ver el riesgo #2 del documento de Fase 1.

---

## Esquema

```text
source ──< source_domain          many-to-one: un medio puede cambiar de dominio
  │                                (RTVC → inravision.gov.co)
  ├──< collection_chunk            unidad reanudable: (medio, proveedor, año-mes)
  │        └──< discovery_record   observación cruda, se conserva aunque se rechace
  │                  └── article   entidad deduplicada
  │                        └──< article_topic   etiquetado multi-etiqueta, versionado
  └──< archive_density             cuántas URLs ofreció cada medio cada mes

government   topic
```

Tres invariantes del diseño:

1. **Discovery y artículo están separados.** Permite responder "¿qué encontró
   cada proveedor?" y "¿qué se descartó y por qué?" (§18).
2. **Nada se borra.** Los descartes se marcan con `rejected_reason`.
3. **El etiquetado temático ocurre después del discovery**, no como filtro de
   búsqueda. Cambiar `topics.yaml` debe permitir re-etiquetar el corpus sin
   volver a descargar nada.

---

## Advertencias heredadas de la Fase 1

Antes de implementar el `GDELTProvider` (fase 6), leer la sección B del
documento de investigación. GDELT tiene **dos modos de fallo silencioso**
verificados empíricamente:

1. Bajo saturación devuelve `HTTP 200` + JSON válido con artículos de **otra
   época**. Hay que validar que cada `seendate` caiga en la ventana pedida.
2. Sólo el **38%** de las consultas dentro de su rango soportado devuelven
   datos; los fallos son cuerpos vacíos con `HTTP 200`. Un bloque vacío se
   reintenta, nunca se marca completado.

Por eso `RATE_GDELT` viene en `0.04` req/s (una cada 25 s) en `.env.example`.

### Las fechas de los sitemaps no son fechas de publicación

Descubierto al recolectar por primera vez. Los sitemaps traen `<lastmod>`, que
es la fecha de **modificación**. En varios medios es un artefacto de migración
del CMS, no la fecha real de la nota:

| Medio | `lastmod` fuera del mes de su propio sitemap |
|---|---|
| Blu Radio | **100 %** |
| Noticias Caracol | 73 % |
| El Tiempo | 0 % |

Los sitemaps de Blu Radio de enero de 2013 traen `lastmod` de abril de 2016,
mientras el slug dice `.../en-blu-jeans-1-de-enero-de-2013`. **El archivo
mensual manda sobre `lastmod`.**

Por eso `article.date_precision` distingue:

- `day` — `lastmod` cayó dentro del mes del sitemap; es fiable.
- `month` — `lastmod` era un artefacto; sólo se conoce el mes.
- `unknown` — no había fecha utilizable.

Consecuencia para el análisis: con precisión `month`, un artículo de un mes de
posesión (agosto de 2010, 2014, 2018, 2022) **no recibe gobierno asignado** —
elegir uno sería inventar el dato. Cualquier corte por gobierno debería filtrar
por `date_precision` o tratar los dos grupos por separado.

### No todos los medios tienen cuerpo de artículo

Descubierto al correr `extract --all` sobre los tres medios. La extracción
funciona; lo que falta es el texto en la página de origen.

| Medio | Página de archivo de 2013 | Artículos con cuerpo ≥500 car. |
|---|---|---|
| El Tiempo | la nota completa | **99 %** |
| Noticias Caracol | mezcla: notas escritas y fichas de vídeo | 19 % (ene) → 36 % (mar) |
| Blu Radio | mezcla: notas escritas y posts de audio | 10 % (ene) → 21 % (mar) |

Verificado leyendo el HTML crudo, no inferido del extractor: hay páginas de Blu
Radio de 2013 que no contienen ningún párrafo de artículo, sólo un reproductor
(`Reproducir audio`), y páginas de Caracol con 63 referencias a vídeo y ningún
`<p>` que no sea navegación. En esos casos `trafilatura` devuelve lo mismo en
modo `favor_precision`, por defecto y `favor_recall`: no hay nada más que sacar.

**No es un corte por año ni un "este medio no tiene texto": es una proporción
que sube.** Dentro del propio 2013, Blu Radio pasa del 10 % al 21 % en tres
meses. Un muestreo de años posteriores (4 artículos por junio) sugiere que
Caracol es sólido hacia 2018 y Blu Radio hacia 2019, pero con n=4 eso orienta y
no calibra. La medida buena es la del propio corpus: `news-corpus profile`.

**Consecuencia para el análisis, y es la importante.** Sí hay cuerpo de Caracol
y Blu Radio en 2013 —1.481 y 1.090 artículos— pero **no es una muestra
aleatoria**: son precisamente las notas que se publicaron escritas, frente a las
que se publicaron como vídeo o audio. Comparar ese subconjunto contra el 99 % de
El Tiempo compara cosas distintas. Para 2013, la comparación honesta entre los
tres medios es sobre **titular y sumario**, que sí existen para todos. Para
comparar cuerpo contra cuerpo conviene recolectar de 2019 en adelante.

### Qué lleva el export

Además de la metadata y las marcas de procedencia (`title_source`,
`date_precision`, `archive_density_month`, `extraction_status`), el dataset
lleva `author`, `description`, `content` y `content_hash`, más `content_chars`
para poder filtrar los artículos analizables sin cargar el texto entero.

`--no-content` omite `content` y `content_hash` y nada más: aligera el archivo
sin perder trazabilidad.

### El cuerpo se limpia antes de guardarse

`clean_content()` elimina las líneas que son interfaz de la página y no texto
publicado: `Publicidad`, `Actualizado: …`, `Síguenos en:`, `Lea también: …` y
los artefactos de puntuación sueltos. Sólo borra líneas completas que coinciden
con el patrón; nunca recorta dentro de una frase, de modo que un párrafo que
*menciona* la publicidad se conserva íntegro.

Importa porque Noticias Caracol intercala un marcador `Publicidad` por cada
espacio de anuncio dentro del cuerpo: sin filtrarlo sería uno de los términos
más frecuentes del medio sin que ningún periodista lo haya escrito. Un artículo
cuyo texto era **sólo** interfaz queda con `content = NULL`, que es la
representación honesta de "esta página no tiene cuerpo".

`news-corpus clean-content` reaplica las reglas al texto ya almacenado y
recalcula `content_hash`. Existe para que el corpus no acabe con dos criterios
de limpieza según la fecha en que se extrajo cada artículo.
