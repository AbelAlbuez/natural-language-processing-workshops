# Ampliar el corpus a 2018-08 → 2026-08 (gobiernos Duque y Petro)

## Por qué el corpus sólo tiene noticias de 2013

No es un límite del código. El volcado de `dumps/` viene de la primera
recolección de prueba: 12 bloques mensuales de 2013 de El Tiempo, Noticias
Caracol y Blu Radio. Además, todos los ejemplos usaban
`--from 2013-01 --to 2013-03`.

- El rango lo decide **sólo** `news-corpus collect --from/--to`
  (`cli_collect.py` → `planner.plan`). No hay fechas hardcodeadas.
- Sin `-s`, `collect` toma los **5** medios con sitemap mensual: El Tiempo,
  Noticias Caracol, Blu Radio, La República y Noticias RCN.
- El prototipo multiagente (`../orquestador.py`) no lee este corpus: hace
  búsqueda web de noticias actuales y no admite fechas.

2018-08-07 → 2026-08-07 coincide exactamente con los gobiernos `duque` y
`petro` de `config/governments.yaml`, y cae entero dentro del archivo denso de
los cinco medios. El Tiempo es denso desde 2016-03 y Caracol y Blu Radio
publican cuerpo escrito de forma consistente desde ~2018-2019.

## El riesgo de escala

5 medios × 97 meses = **485 bloques**, con cientos de miles de URLs. El
discovery es barato porque descarga un sitemap por mes. La extracción no:
`extract` abre cada artículo a 1 req/s, así que extraerlo todo tomaría semanas.
Por eso la extracción se hace **selectiva**, por período y por tema.

## Cambios de código que lo permiten

| Archivo | Cambio |
|---|---|
| `src/news_corpus/pipeline/extraction.py` | `extract_pending` acepta `date_from`, `date_to` y `topic_ids`. Nuevo `expand_topics`: un tema raíz incluye sus subtemas, y un tema desconocido da error en vez de no extraer nada |
| `src/news_corpus/cli_analyze.py` | `extract` expone `--from`, `--to` y `--topic` (repetible) |
| `src/news_corpus/cli_collect.py` | `_parse_month(..., last_day=True)` devolvía el día 28; ahora devuelve el último día real del mes |
| `tests/test_extraction.py` | Tests de `expand_topics` y del fin de mes |

## Pasos (PowerShell, desde `news-retrieval/`)

Con el entorno activado (`.venv\Scripts\Activate.ps1`) basta con
`news-corpus`; si no, usa `.venv\Scripts\news-corpus`.

### 1. Levantar la base

```powershell
copy .env.example .env          # la primera vez; cambia DB_PORT si el 5433 está ocupado
docker compose up -d            # Postgres en localhost:5433
docker ps --filter name=news-corpus-db
```

### 2. Preparar el esquema (elige una opción)

- **a) Conservar 2013 y sumar lo nuevo (recomendado).** Desde Git Bash, porque
  es un script de bash:
  ```bash
  ./scripts/restore-db.sh
  ```
- **b) Empezar con la base vacía:**
  ```powershell
  alembic upgrade head
  ```

En los dos casos, después:

```powershell
news-corpus catalog sync
```

### 3. Discovery (descarga los sitemaps)

```powershell
news-corpus collect --from 2018-08 --to 2026-08 --dry-run   # debe decir 485 bloques
news-corpus collect --from 2018-08 --to 2020-12
news-corpus collect --from 2021-01 --to 2023-12
news-corpus collect --from 2024-01 --to 2026-08
news-corpus retry-failed
news-corpus status
```

Es una petición por medio y mes. Si se corta, se repite el mismo comando: los
bloques ya completados se saltan.

### 4. Títulos y temas (sin descargas)

```powershell
news-corpus enrich    # título y sección a partir de la URL
news-corpus tag       # etiquetado temático con config/topics.yaml
```

### 5. Extracción selectiva del cuerpo

Hay que pasar `--all`. Desde 2016 casi todas las URLs traen slug y ya tienen
título derivado, y el `extract` por defecto las saltaría.

```powershell
# prueba pequeña
news-corpus extract --all --from 2018-08 --to 2026-08 --topic politica -n 200
# en serio (~1,5 h por cada 5.000 artículos)
news-corpus extract --all --from 2018-08 --to 2026-08 --topic politica -n 5000
```

Se puede ir medio por medio (`-s el_tiempo`) o tema por tema (`--topic seguridad`,
`--topic justicia`). Cada corrida sigue donde quedó la anterior.

### 6. Revisar y exportar

```powershell
news-corpus profile
news-corpus export -o exports/corpus_2018_2026.parquet --from 2018-08-01 --to 2026-08-31
```

`export` pide fechas completas (`2018-08-01`), no el mes como `collect`.

## Verificación

- El `--dry-run` muestra 485 bloques sin avisos de archivo adelgazado.
- `news-corpus status` muestra los bloques de 2018-2026 en COMPLETED.
- En SQL, `SELECT government_id, source_id, count(*) FROM article GROUP BY 1,2;`
  muestra filas de `duque` y `petro` para los cinco medios.
- `news-corpus profile` muestra qué proporción tiene cuerpo ≥500 caracteres.
- `pytest -q` pasa.

## Pendiente

- Generar un volcado nuevo y actualizar `dumps/MANIFEST.md` cuando termine la
  recolección.
- Opcional: un `AgenteBusqueda` que lea `exports/*.parquet`, para que
  `orquestador.py` analice artículos del corpus en vez de buscar en la web.
