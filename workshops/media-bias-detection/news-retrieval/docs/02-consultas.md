# Dónde están los artículos y cómo consultarlos

## Conexión

Los artículos están en **PostgreSQL 17**, dentro del contenedor Docker
`news-corpus-db` que levanta `docker-compose.yml`. Los datos persisten en el
volumen `news_corpus_data`: sobreviven a `docker compose down`.

| | |
|---|---|
| Host | `localhost` |
| Puerto | **5433** (no 5432 — ese ya lo ocupa otro Postgres tuyo) |
| Base | `news_corpus` |
| Usuario / clave | `news_corpus` / `news_corpus` (en `.env`) |

```bash
# psql dentro del contenedor (no necesitas psql instalado)
docker exec -it news-corpus-db psql -U news_corpus -d news_corpus

# desde un cliente externo (DBeaver, TablePlus, DataGrip…)
postgresql://news_corpus:news_corpus@localhost:5433/news_corpus
```

Desde Python:

```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg://news_corpus:news_corpus@localhost:5433/news_corpus")
df = pd.read_sql("SELECT * FROM article LIMIT 100", engine)
```

---

## Las tablas

| Tabla | Qué guarda |
|---|---|
| **`article`** | La entidad deduplicada. Es la que vas a consultar casi siempre. |
| `discovery_record` | Cada vez que un proveedor vio una URL. Incluye lo rechazado. |
| `collection_chunk` | Un bloque `(medio, proveedor, año-mes)` y su estado. |
| `archive_density` | Cuántas URLs ofreció cada medio cada mes. **Léela antes de comparar volúmenes.** |
| `article_topic` | Etiquetas temáticas (multi-etiqueta, versionadas). |
| `source`, `source_domain`, `government`, `topic` | Catálogo, espejo de `config/*.yaml`. |

### Columnas de `article` que conviene entender

| Columna | Ojo con esto |
|---|---|
| `title` | Puede venir de tres sitios distintos — mira `title_source`. |
| `title_source` | `extracted` = titular real publicado · `slug` = reconstruido de la URL, **sin tildes ni puntuación** · `sitemap` = declarado por el medio. |
| `published_date` | Su fiabilidad la da `date_precision`, no la columna. |
| `date_precision` | `day` = fecha real · `month` = sólo se conoce el mes (el `lastmod` era un artefacto de migración del CMS). |
| `government_id` | `NULL` cuando la fecha no basta para decidirlo — p. ej. precisión de mes en agosto de posesión. |
| `content` | Cuerpo del artículo. Sólo presente si pasó por `news-corpus extract`. |
| `extraction_status` | `ok`, `no_title`, `http_error` (404: el artículo ya no existe), `failed` (red, reintentable), `robots_denied`. |

---

## Consultas útiles

### Radiografía rápida

```sql
SELECT source_id, count(*) AS articulos,
       count(*) FILTER (WHERE title_source = 'extracted') AS titulo_real,
       count(*) FILTER (WHERE title_source = 'slug')      AS titulo_del_slug,
       count(*) FILTER (WHERE title IS NULL)              AS sin_titulo,
       count(content)                                     AS con_cuerpo
FROM article GROUP BY source_id ORDER BY 2 DESC;
```

### Buscar en los titulares

```sql
SELECT source_id, published_date, title
FROM article
WHERE title ILIKE '%reforma%'
  AND date_precision = 'day'            -- sólo fechas fiables
ORDER BY published_date;
```

Para búsqueda de texto completo en español (más rápida y con lematización):

```sql
SELECT source_id, published_date, title
FROM article
WHERE to_tsvector('spanish', coalesce(title,'') || ' ' || coalesce(content,''))
      @@ plainto_tsquery('spanish', 'proceso de paz')
LIMIT 50;
```

### Artículos de un tema, por medio

```sql
SELECT a.source_id, count(*) AS n
FROM article a
JOIN article_topic t ON t.article_id = a.id
WHERE t.topic_id = 'protestas'
GROUP BY a.source_id ORDER BY n DESC;
```

### Énfasis temático comparable entre medios

Proporción, no conteo: los medios tienen volúmenes muy distintos.

```sql
WITH etiquetados AS (
  SELECT a.source_id, t.topic_id
  FROM article a JOIN article_topic t ON t.article_id = a.id
  WHERE a.published_date BETWEEN '2013-01-01' AND '2013-03-31'
)
SELECT topic_id,
       round(100.0 * count(*) FILTER (WHERE source_id='blu_radio')
             / nullif(sum(count(*)) FILTER (WHERE source_id='blu_radio') OVER (), 0), 1) AS blu_pct,
       round(100.0 * count(*) FILTER (WHERE source_id='noticias_caracol')
             / nullif(sum(count(*)) FILTER (WHERE source_id='noticias_caracol') OVER (), 0), 1) AS caracol_pct
FROM etiquetados GROUP BY topic_id ORDER BY 2 DESC NULLS LAST LIMIT 15;
```

### Cobertura por gobierno

```sql
SELECT g.president, a.source_id, count(*) AS articulos
FROM article a JOIN government g ON g.id = a.government_id
WHERE a.date_precision = 'day'          -- si no, el corte por gobierno no es sólido
GROUP BY g.president, a.source_id, g.start_date
ORDER BY g.start_date, articulos DESC;
```

### Antes de comparar volúmenes: mira la densidad de archivo

```sql
SELECT source_id, to_char(period_start,'YYYY-MM') AS mes, n_urls_offered
FROM archive_density
WHERE source_id = 'el_tiempo'
ORDER BY period_start;
```

Si un medio ofrece 39 URLs en un mes y 4.793 al siguiente, la diferencia está en
el archivado del medio, no en su cobertura. Ese salto es real y está en los
datos: El Tiempo, febrero → marzo de 2016.

### Auditar por qué un artículo quedó en un tema

```sql
SELECT a.title, t.topic_id, t.matched_keyword, t.matched_on, t.rule_version
FROM article a JOIN article_topic t ON t.article_id = a.id
WHERE a.id = 1234;
```

### Qué se descartó y por qué

```sql
SELECT rejected_reason, count(*)
FROM discovery_record
WHERE rejected_reason IS NOT NULL
GROUP BY 1;
```

### Reproducibilidad: cómo se construyó un tramo

```sql
SELECT source_id, to_char(period_start,'YYYY-MM') AS mes, status,
       n_found, n_new, n_duplicates, attempts, request_url, completed_at
FROM collection_chunk
WHERE source_id = 'blu_radio' ORDER BY period_start;
```

---

## Dos advertencias antes de sacar conclusiones

**1. Filtra por `date_precision` en cualquier corte temporal.** Ahora mismo la
mayoría del corpus está en precisión `month`: los sitemaps de Blu Radio traían
`lastmod` de 2016-2024 para artículos de 2013. Un corte por gobierno sobre esos
datos no es sólido. `news-corpus extract` va ascendiendo artículos a `day` a
medida que corre.

**2. Un porcentaje sobre pocos artículos no es un porcentaje.** El Tiempo tiene
hoy ~200 títulos utilizables frente a los 7.214 de Blu Radio. Compararlos en
proporción produce cifras como "33 % medio ambiente" sobre 3 notas.
