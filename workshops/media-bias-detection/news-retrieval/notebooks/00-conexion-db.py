"""Comprobación de conexión a la base desde el JupyterLab del contenedor.

Celdas separadas con `# %%` (formato percent): se abre como notebook en
JupyterLab o VS Code, o se ejecuta directo con `python`.

Dentro del contenedor la base NO es `localhost:5433` sino `postgres:5432`:
5433 es sólo el puerto que docker-compose publica en el host. El servicio
`jupyter` ya exporta DB_HOST/DB_PORT correctos, así que `get_settings()`
resuelve la URL sola y este notebook funciona igual dentro y fuera de Docker.
"""

# %%
import pandas as pd
from sqlalchemy import text

from news_corpus.config.settings import get_settings
from news_corpus.db.session import get_engine

settings = get_settings()
engine = get_engine()

# La clave no se imprime.
print(f"Conectando a {settings.db_user}@{settings.db_host}:{settings.db_port}/{settings.db_name}")

with engine.connect() as conn:
    print(conn.execute(text("SELECT version()")).scalar_one())

# %% [markdown]
# ## Qué hay en la base

# %%
tablas = pd.read_sql(
    """
    SELECT relname AS tabla, n_live_tup AS filas_aprox
    FROM pg_stat_user_tables
    ORDER BY n_live_tup DESC
    """,
    engine,
)
print(tablas.to_string(index=False))

# %% [markdown]
# ## Una consulta de verdad
#
# `date_precision` y `title_source` no son decorativos: filtrar por ellos es lo
# que separa un hallazgo de un artefacto del archivo (ver `docs/02-consultas.md`).

# %%
df = pd.read_sql(
    """
    SELECT source_id,
           date_precision,
           COUNT(*)            AS articulos,
           MIN(published_date) AS desde,
           MAX(published_date) AS hasta
    FROM article
    GROUP BY source_id, date_precision
    ORDER BY source_id, date_precision
    """,
    engine,
)
print(df.to_string(index=False))

# %% [markdown]
# ## El export en Parquet
#
# Alternativa a SQL cuando el análisis cabe en memoria:
# `news-corpus export -o exports/corpus.parquet` (se puede lanzar desde una
# terminal de JupyterLab; `exports/` está montado, así que el archivo aparece
# también en el host).

# %%
from pathlib import Path

CORPUS = Path("/workspace/exports/corpus.parquet")
if CORPUS.exists():
    corpus = pd.read_parquet(CORPUS)
    print(f"{len(corpus):,} artículos · {corpus['source_id'].nunique()} medios")
else:
    print(f"No existe {CORPUS}. Ejecuta: news-corpus export -o exports/corpus.parquet")
