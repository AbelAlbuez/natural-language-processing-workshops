"""Construye notebooks/02-guia-del-corpus.ipynb."""

import json
from pathlib import Path

cells = []


def _lines(text):
    """El formato .ipynb guarda el código como lista de líneas CON su salto."""
    parts = text.split("\n")
    return [ln + "\n" for ln in parts[:-1]] + [parts[-1]]


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {},
                  "source": _lines(text.strip())})


def code(text):
    cells.append({
        "cell_type": "code", "execution_count": None, "metadata": {},
        "outputs": [], "source": _lines(text.strip("\n")),
    })


# ─────────────────────────────────────────────────────────────────────────────
md("""
# Guía del corpus de prensa colombiana

Este notebook explica **qué guarda cada tabla y por qué existe**, con consultas
que puedes ejecutar y modificar.

El corpus está en PostgreSQL 17, en el contenedor Docker `news-corpus-db`.
Si no está arriba: `docker compose up -d` desde la raíz del proyecto.

---

## Antes de empezar: tres columnas que evitan conclusiones falsas

El corpus se construyó a partir de archivos web que tienen defectos reales.
Estas tres columnas registran esos defectos en lugar de esconderlos. **Ignorarlas
produce hallazgos que son artefactos del archivado, no de la cobertura.**

| Columna | Qué significa |
|---|---|
| `article.date_precision` | `day` = fecha real · `month` = sólo se conoce el mes |
| `article.title_source` | `extracted` = titular publicado · `slug` = reconstruido de la URL, sin tildes |
| tabla `archive_density` | cuántas URLs ofreció cada medio cada mes |

Cada una tiene su sección más abajo con el caso concreto que la motivó.
""")

code("""
import pandas as pd
from sqlalchemy import create_engine, text

from news_corpus.config.settings import get_settings

pd.set_option("display.max_colwidth", 70)
pd.set_option("display.width", 160)

# La URL sale de la configuración, no de una constante: dentro del contenedor
# la base es postgres:5432 y en el host localhost:5433. Así el notebook corre
# en los dos sitios sin editar nada.
engine = create_engine(get_settings().database_url)


def q(sql, **params):
    \"\"\"Ejecuta SQL y devuelve un DataFrame.\"\"\"
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


q("SELECT count(*) AS articulos, count(content) AS con_cuerpo FROM article")
""")

# ── mapa ─────────────────────────────────────────────────────────────────────
md("""
---
## 1. Mapa de las tablas

```
CATÁLOGO (espejo de config/*.yaml)        ADQUISICIÓN
  source ──< source_domain                  collection_chunk
  government                                     │
  topic                                          └──< discovery_record
                                                          │
RESULTADO                                                 ▼
  article ──< article_topic                            article
  archive_density
```

El flujo real de un artículo:

```
sitemap del medio  →  collection_chunk  →  discovery_record  →  article
                          (un mes)          (una URL vista)     (deduplicado)
```
""")

code("""
q(\"\"\"
SELECT c.relname AS tabla,
       c.reltuples::bigint AS filas_aprox,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS tamano
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC
\"\"\")
""")

# ── source ───────────────────────────────────────────────────────────────────
md("""
---
## 2. `source` y `source_domain` — los medios

**Qué guarda:** los 10 medios del proyecto y su estrategia de descarga.

Dos columnas merecen atención porque no significan lo mismo:

- **`archive_from`** — el mes más antiguo para el que *existe* archivo.
- **`reliable_from`** — desde cuándo ese archivo es *denso*.

En El Tiempo valen `1990-01` y `2016-03`. La diferencia no es un descuido: su
sitemap llega a 1990, pero ofrece 39 URLs en febrero de 2016 y 4.793 en marzo.
El archivo antiguo es un residuo, no un archivo.

`source_domain` es una tabla aparte porque **un medio puede cambiar de dominio
en 20 años**. RTVC es el caso real: `rtvc.gov.co` redirige a `inravision.gov.co`.
El mapeo dominio→medio es de muchos a uno.
""")

code("""
q(\"\"\"
SELECT s.id, s.name, s.source_type, s.active,
       s.archive_from, s.reliable_from,
       string_agg(d.domain, ', ' ORDER BY d.is_canonical DESC) AS dominios
FROM source s LEFT JOIN source_domain d ON d.source_id = s.id
GROUP BY s.id, s.name, s.source_type, s.active, s.archive_from, s.reliable_from
ORDER BY s.active DESC, s.id
\"\"\")
""")

md("""
`rtvc` aparece **inactivo a propósito**: no se encontró un mecanismo de descarga
utilizable, y se prefirió desactivarlo antes que fingir cobertura.

Los medios con `archive_from` vacío (Semana, El Espectador, W Radio) migraron al
CMS Arc, que dejó sus archivos anteriores fuera de alcance. Su columna
`discovery_config` declara de dónde habría que completarlos.
""")

code("""
q(\"\"\"
SELECT id,
       discovery_config->>'strategy'  AS estrategia,
       discovery_config->'fallback'   AS fuentes_alternativas
FROM source WHERE discovery_config->>'archive_from' IS NULL
\"\"\")
""")

# ── government ───────────────────────────────────────────────────────────────
md("""
---
## 3. `government` — los cinco gobiernos

**Qué guarda:** los períodos presidenciales que delimitan el corpus. Son el eje
de comparación del proyecto: "¿cambia la cobertura según quién gobierna?".

Cubren exactamente el horizonte 2006-08-07 → 2026-08-07. La posesión en Colombia
es siempre el 7 de agosto, y el intervalo es **semiabierto**: el día de posesión
pertenece al gobierno que entra.

`source_note` está vacío a propósito: marca que las fechas **aún no se han
validado contra fuente citable**, como pide el documento del proyecto.
""")

code("""
q(\"\"\"
SELECT id, president, term, start_date, end_date,
       (end_date - start_date) AS dias,
       coalesce(source_note, '⚠️ pendiente de verificar') AS fuente
FROM government ORDER BY start_date
\"\"\")
""")

md("""
### Cuidado con los meses de posesión

Agosto de 2010, 2014, 2018 y 2022 contienen **dos gobiernos**. Por eso un
artículo con `date_precision = 'month'` en uno de esos meses queda con
`government_id = NULL`: elegir uno sería inventarse el dato.
""")

code("""
q(\"\"\"
SELECT date_precision,
       count(*) AS articulos,
       count(government_id) AS con_gobierno,
       count(*) - count(government_id) AS sin_gobierno
FROM article GROUP BY date_precision ORDER BY 2 DESC
\"\"\")
""")

# ── topic ────────────────────────────────────────────────────────────────────
md("""
---
## 4. `topic` — la jerarquía temática

**Qué guarda:** 7 temas raíz y 35 subtemas, con las palabras clave que los
detectan. Es un espejo de `config/topics.yaml`.

Punto importante de método: **las keywords NO son parámetros de búsqueda**. El
descargador baja el mes completo de cada medio y el etiquetado se aplica después.
Así, cambiar `topics.yaml` re-etiqueta el corpus sin volver a descargar nada.
""")

code("""
q(\"\"\"
SELECT p.name AS tema_raiz,
       count(h.id) AS subtemas,
       string_agg(h.name, ' · ' ORDER BY h.name) AS detalle
FROM topic p JOIN topic h ON h.parent_id = p.id
WHERE p.parent_id IS NULL
GROUP BY p.name ORDER BY p.name
\"\"\")
""")

code("""
# Las palabras clave de un tema concreto
q("SELECT id, name, keywords FROM topic WHERE id = :t", t="protestas")
""")

# ── chunk ────────────────────────────────────────────────────────────────────
md("""
---
## 5. `collection_chunk` — la unidad de descarga

**Qué guarda:** un bloque `(medio, proveedor, año-mes)` y cómo le fue.

Es lo que hace la descarga **reanudable**. El corpus no se baja de una vez:
son ~2.400 bloques mensuales independientes. Un bloque `completed` no se repite;
uno `failed` se reintenta con `news-corpus retry-failed`.

También es la tabla de **reproducibilidad**: guarda la URL exacta que se pidió,
cuándo, cuántas URLs devolvió y cuántas eran nuevas. Con eso se puede explicar
cómo se construyó cualquier tramo del corpus.

| Estado | Significado |
|---|---|
| `pending` | planificado, sin ejecutar |
| `running` | en curso |
| `completed` | el proveedor respondió (aunque fueran 0 artículos) |
| `failed` | el proveedor **no** respondió — se reintenta |
| `partial` | respondió a medias |

La distinción entre `completed` con 0 artículos y `failed` es deliberada: un mes
genuinamente vacío no es lo mismo que un fallo de red. Confundirlos deja huecos
silenciosos en el corpus.
""")

code("""
q(\"\"\"
SELECT source_id, to_char(period_start,'YYYY-MM') AS mes, status,
       n_found AS urls_vistas, n_new AS nuevos, n_duplicates AS duplicados,
       attempts AS intentos, completed_at
FROM collection_chunk ORDER BY source_id, period_start
\"\"\")
""")

code("""
# La URL exacta que se pidió para cada bloque: trazabilidad completa
q("SELECT source_id, to_char(period_start,'YYYY-MM') AS mes, request_url "
  "FROM collection_chunk ORDER BY source_id, period_start LIMIT 5")
""")

# ── discovery_record ─────────────────────────────────────────────────────────
md("""
---
## 6. `discovery_record` — lo que vio cada proveedor

**Qué guarda:** una fila por cada vez que un proveedor vio una URL, *antes* de
deduplicar y **aunque se haya rechazado**.

Por qué existe separada de `article`: permite responder dos preguntas que un
corpus académico tiene que poder responder — *"¿qué encontró cada fuente?"* y
*"¿qué quedó fuera y por qué?"*. Aquí **nada se borra nunca**; los descartes se
marcan en `rejected_reason`.

`raw_payload` (JSONB) conserva lo que dijo la fuente original, incluida la
procedencia de la fecha.
""")

code("""
q(\"\"\"
SELECT id, provider, substring(url, 1, 62) AS url,
       published_at_raw AS lastmod_del_sitemap,
       raw_payload->>'date_source'   AS origen_fecha,
       raw_payload->>'date_in_period' AS fecha_dentro_del_mes,
       rejected_reason
FROM discovery_record ORDER BY id LIMIT 6
\"\"\")
""")

code("""
# ¿Se descartó algo? (rejected_reason no nulo)
q(\"\"\"
SELECT coalesce(rejected_reason, '(aceptado)') AS motivo, count(*)
FROM discovery_record GROUP BY 1 ORDER BY 2 DESC
\"\"\")
""")

# ── article ──────────────────────────────────────────────────────────────────
md("""
---
## 7. `article` — la tabla principal

**Qué guarda:** el artículo deduplicado. Es la que vas a consultar casi siempre.
La clave de deduplicación es `url_hash`: SHA-256 de la URL normalizada, de forma
que `http://www.eltiempo.com/nota` y `https://eltiempo.com/nota/` son el mismo.

### `title_source`: de dónde salió el título

| Valor | Qué es |
|---|---|
| `extracted` | El titular publicado, leído de la página. **Con tildes y puntuación.** |
| `slug` | Reconstruido desde la URL. Sin tildes ni signos. Sirve para frecuencias, no para matices. |
| `sitemap` | Declarado por el medio en el sitemap. |
| `NULL` | No hay título: la URL era un identificador como `/archivo/documento/CMS-16551020`. |
""")

code("""
q(\"\"\"
SELECT source_id,
       count(*) AS articulos,
       count(*) FILTER (WHERE title_source = 'extracted') AS titular_real,
       count(*) FILTER (WHERE title_source = 'slug')      AS desde_slug,
       count(*) FILTER (WHERE title IS NULL)              AS sin_titulo,
       count(content) AS con_cuerpo
FROM article GROUP BY source_id ORDER BY 2 DESC
\"\"\")
""")

md("""
La diferencia entre un titular extraído y uno reconstruido se ve mejor con
ejemplos que con una explicación:
""")

code("""
q(\"\"\"
(SELECT 'extracted' AS origen, title FROM article
 WHERE title_source='extracted' AND title IS NOT NULL LIMIT 3)
UNION ALL
(SELECT 'slug', title FROM article WHERE title_source='slug' LIMIT 3)
\"\"\")
""")

md("""
### `date_precision`: cuánto vale la fecha

Los sitemaps traen `<lastmod>`, que es fecha de **modificación**, no de
publicación. En varios medios resultó ser la marca de una migración masiva del
CMS: los sitemaps de Blu Radio de enero de 2013 traen `lastmod` de abril de
2016, mientras el slug de la URL dice `...-1-de-enero-de-2013`.

Medido sobre el corpus: **100 %** de las fechas de Blu Radio caían fuera del mes
de su propio sitemap, **73 %** en Caracol, **0 %** en El Tiempo.

La regla que se aplicó: si `lastmod` cae dentro del mes del sitemap se cree
(`day`); si no, manda el mes del archivo y la fecha se degrada a `month`.
La extracción de la página recupera la fecha real y asciende el artículo a `day`.
""")

code("""
q(\"\"\"
SELECT source_id, date_precision, count(*),
       min(published_date) AS desde, max(published_date) AS hasta
FROM article GROUP BY source_id, date_precision ORDER BY source_id, 3 DESC
\"\"\")
""")

# ── article_topic ────────────────────────────────────────────────────────────
md("""
---
## 8. `article_topic` — el etiquetado temático

**Qué guarda:** qué temas se detectaron en cada artículo. Es **multi-etiqueta**:
un artículo sobre las FARC en la frontera con Venezuela pertenece a varios temas
a la vez.

Guarda además **por qué** se etiquetó — `matched_keyword` y `matched_on` — para
poder auditar cualquier resultado. Y `rule_version` es la huella de las keywords
vigentes: si cambias `topics.yaml`, cambia la versión y sabes qué reglas
produjeron qué etiquetas.

Es un emparejamiento por palabras clave, no un clasificador. Sirve para
**segmentar** el corpus, no para afirmar de qué trata un artículo.
""")

code("""
q(\"\"\"
SELECT t.topic_id, count(*) AS articulos,
       count(DISTINCT t.matched_keyword) AS keywords_distintas,
       mode() WITHIN GROUP (ORDER BY t.matched_keyword) AS keyword_mas_comun,
       mode() WITHIN GROUP (ORDER BY t.matched_on) AS campo_habitual
FROM article_topic t GROUP BY t.topic_id ORDER BY 2 DESC LIMIT 12
\"\"\")
""")

code("""
# Auditar un artículo: por qué quedó en esos temas
q(\"\"\"
SELECT a.title, t.topic_id, t.matched_keyword, t.matched_on
FROM article a JOIN article_topic t ON t.article_id = a.id
WHERE a.title IS NOT NULL
ORDER BY a.id LIMIT 8
\"\"\")
""")

# ── archive_density ──────────────────────────────────────────────────────────
md("""
---
## 9. `archive_density` — la defensa metodológica

**Qué guarda:** cuántas URLs ofreció realmente cada medio en cada mes.

Esta tabla no es una métrica operativa: es una **defensa contra una conclusión
falsa**. El sitemap de El Tiempo pasa de 39 URLs en febrero de 2016 a 4.793 en
marzo — un factor de ~120 en un mes, sin que ocurriera nada en el mundo que lo
explique. Cambió el archivado.

Si alguien comparara *"cuánto cubrió El Tiempo bajo Santos frente a bajo Duque"*
sin mirar esta tabla, estaría midiendo el archivo y presentándolo como hallazgo.
""")

code("""
q(\"\"\"
SELECT source_id, to_char(period_start,'YYYY-MM') AS mes,
       n_urls_offered AS urls_ofrecidas, n_articles_stored AS almacenados
FROM archive_density ORDER BY source_id, period_start
\"\"\")
""")

code("""
import matplotlib.pyplot as plt

d = q("SELECT source_id, period_start, n_urls_offered FROM archive_density ORDER BY period_start")
piv = d.pivot_table(index="period_start", columns="source_id",
                    values="n_urls_offered", fill_value=0)

ax = piv.plot(kind="bar", figsize=(11, 4), width=0.8)
ax.set_ylabel("URLs en el sitemap")
ax.set_xlabel("")
ax.set_title("Densidad de archivo por medio y mes\\n"
             "El salto de El Tiempo en 2016-03 es archivado, no cobertura",
             loc="left", fontsize=10)
ax.legend(title=None, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()
""")

# ── alembic ──────────────────────────────────────────────────────────────────
md("""
---
## 10. `alembic_version` — el control de versiones del esquema

Una sola fila con el identificador de la última migración aplicada. La gestiona
Alembic; no se toca a mano. Sirve para saber si tu base está al día con el
código (`alembic upgrade head`).
""")

code("""
q("SELECT version_num FROM alembic_version")
""")

# ── análisis ─────────────────────────────────────────────────────────────────
md("""
---
## 11. Consultas de análisis

Ahora que están claras las tablas, esto es lo que se puede preguntar hoy.

### Buscar en titulares y cuerpo (full-text en español)

Postgres lematiza: buscar `"protesta"` encuentra también `"protestas"`.
""")

code("""
q(\"\"\"
SELECT source_id, published_date, date_precision, substring(title,1,70) AS titulo
FROM article
WHERE to_tsvector('spanish', coalesce(title,'') || ' ' || coalesce(content,''))
      @@ plainto_tsquery('spanish', :busqueda)
ORDER BY published_date LIMIT 15
\"\"\", busqueda="proceso de paz")
""")

md("""
### Énfasis temático comparable entre medios

Proporción, no conteo — los medios tienen volúmenes muy distintos. Y sólo entre
medios con muestra suficiente: un porcentaje sobre 3 artículos no es un
porcentaje.
""")

code("""
df = q(\"\"\"
SELECT a.source_id, t.topic_id
FROM article a JOIN article_topic t ON t.article_id = a.id
WHERE a.published_date >= '2013-01-01' AND a.published_date < '2013-04-01'
\"\"\")

MIN_ETIQUETADOS = 100
tam = df["source_id"].value_counts()
comparables = tam[tam >= MIN_ETIQUETADOS].index

excluidos = tam[tam < MIN_ETIQUETADOS]
if len(excluidos):
    print("Excluidos por muestra insuficiente:",
          ", ".join(f"{m} ({n})" for m, n in excluidos.items()), "\\n")

sub = df[df["source_id"].isin(comparables)]
pct = (pd.crosstab(sub["topic_id"], sub["source_id"], normalize="columns") * 100).round(1)
pct["total"] = pd.crosstab(sub["topic_id"], sub["source_id"]).sum(axis=1)
pct.sort_values("total", ascending=False).head(12)
""")

md("""
### Elección léxica por medio

Qué palabras usa cada medio para hablar de lo mismo. Es lo más cercano al
objetivo de *framing* que permiten los datos actuales.

Nota: tras la extracción, los 17.201 títulos son el titular publicado
(`title_source = 'extracted'`). Aun así se comparan formas normalizadas sin
tildes, para que el análisis siga siendo válido si se amplía el corpus y vuelven
a aparecer títulos reconstruidos del slug.
""")

code("""
import re
from collections import Counter

VACIAS = {
    "de","la","el","en","y","a","los","las","del","por","con","un","una","para",
    "que","se","su","al","es","lo","como","mas","o","sus","le","ya","no","sobre",
    "este","esta","son","fue","ser","hay","tras","entre","asi","desde","sin","dice",
}

t = q(\"\"\"
SELECT source_id, title FROM article
WHERE title IS NOT NULL
  AND published_date >= '2013-01-01' AND published_date < '2013-04-01'
\"\"\")

for medio, grupo in t.groupby("source_id"):
    if len(grupo) < 100:
        continue
    c = Counter()
    for titulo in grupo["title"]:
        c.update(w for w in re.findall(r"[a-záéíóúñ]{4,}", titulo.lower()) if w not in VACIAS)
    print(f"\\n{medio}  ({len(grupo)} títulos)")
    print("  " + " · ".join(f"{w} ({n})" for w, n in c.most_common(12)))
""")

md("""
### Cobertura por gobierno

Sólo con fechas fiables: si se incluyen las de precisión `month`, el corte por
gobierno no se sostiene.
""")

code("""
q(\"\"\"
SELECT g.president, a.source_id, count(*) AS articulos
FROM article a JOIN government g ON g.id = a.government_id
WHERE a.date_precision = 'day'
GROUP BY g.president, a.source_id, g.start_date
ORDER BY g.start_date, articulos DESC
\"\"\")
""")

# ── límites ──────────────────────────────────────────────────────────────────
md("""
---
## 12. Qué **no** se puede hacer todavía

Conviene tenerlo presente para no forzar los datos:

- **Comparar entre gobiernos.** El corpus actual cubre casi sólo Santos I
  (2013) más un trimestre de 2016. Se resuelve descargando más:
  `news-corpus collect -s el_tiempo --from 2019-01 --to 2019-12`.

- **Análisis de tono o sentimiento.** El documento del proyecto excluye
  explícitamente el análisis de parcialización de este servicio: aquí se
  construye el corpus, no se interpreta.

- **Cuerpo entre medios.** El Tiempo conserva el texto en el 99 % de sus páginas
  de archivo; Caracol y Blu Radio, entre el 10 % y el 36 % en 2013, porque buena
  parte de su archivo son notas de vídeo y audio. Ese subconjunto con texto **no
  es una muestra aleatoria** de su cobertura. Detalle en el `README.md`.

### Para avanzar

```bash
news-corpus collect -s el_tiempo --from 2019-01 --to 2019-12   # más gobiernos
news-corpus tag --retag              # re-etiquetar tras cambiar topics.yaml
```
""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = Path("notebooks/02-guia-del-corpus.ipynb")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{out} · {len(cells)} celdas")
