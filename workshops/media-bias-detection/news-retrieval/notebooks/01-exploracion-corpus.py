"""Exploración del corpus — punto de partida para el análisis NLP.

Ejecutar:
    news-corpus export -o exports/corpus.parquet
    python notebooks/01-exploracion-corpus.py

O abrirlo como notebook: las celdas están separadas con `# %%`, que VS Code y
Jupytext reconocen.

LÉASE ANTES DE SACAR CONCLUSIONES
---------------------------------
Este corpus trae tres campos de procedencia que NO son metadatos decorativos.
Ignorarlos produce hallazgos falsos:

  date_precision  'day' = fecha fiable · 'month' = sólo se conoce el mes,
                  porque el lastmod del sitemap era un artefacto de migración.
  title_source    'slug' = el título se reconstruyó desde la URL. Pierde
                  tildes, mayúsculas y puntuación. NO es el titular publicado.
  archive_density URLs que el medio ofreció ese mes. Una diferencia de volumen
                  entre medios o épocas puede ser diferencia de archivado.
"""

# %%
from pathlib import Path

import pandas as pd

CORPUS = Path("exports/corpus.parquet")
if not CORPUS.exists():
    raise SystemExit("Falta el export. Ejecuta: news-corpus export -o exports/corpus.parquet")

df = pd.read_parquet(CORPUS)
df["published_date"] = pd.to_datetime(df["published_date"])
df["mes"] = df["published_date"].dt.to_period("M")
print(f"{len(df):,} artículos · {df['source_id'].nunique()} medios")

# %% [markdown]
# ## 1. Qué se puede analizar y con cuánta confianza

# %%
print("Fiabilidad de la fecha:")
print(df["date_precision"].value_counts().to_string(), "\n")

print("Origen del título:")
print(df["title_source"].fillna("(sin título)").value_counts().to_string(), "\n")

print("Cobertura por medio:")
print(
    df.groupby("source_id")
    .agg(articulos=("article_id", "count"),
         desde=("published_date", "min"),
         hasta=("published_date", "max"),
         con_titulo=("title", "count"))
    .to_string()
)

# %% [markdown]
# ## 2. El sesgo de archivo, medido
#
# El Tiempo pasa de decenas de URLs al mes a miles en marzo de 2016. Si se
# compara "cuánto publicó cada medio" sin esto, se mide el archivado.

# %%
volumen = df.groupby(["source_id", "mes"]).size().unstack(0).fillna(0).astype(int)
print(volumen.to_string())

# %% [markdown]
# ## 3. Subconjunto analizable
#
# Para cualquier análisis léxico o de framing, quedarse con lo que tiene título
# real (aunque sea derivado del slug) y descartar lo que no.

# %%
analizable = df[df["title"].notna()].copy()
print(f"{len(analizable):,} de {len(df):,} artículos tienen título "
      f"({len(analizable)/len(df):.0%})")

# Para comparar entre medios, restringirse a un período común.
comun = analizable[
    (analizable["published_date"] >= "2013-01-01")
    & (analizable["published_date"] < "2013-04-01")
]
print(f"\nVentana comparable 2013-Q1: {len(comun):,} artículos")
print(comun["source_id"].value_counts().to_string())

# %% [markdown]
# ## 4. Elección léxica — la pregunta del proyecto
#
# Qué palabras usa cada medio. Esto es lo más cercano al objetivo de framing
# que permiten los datos actuales (sin cuerpo del artículo todavía).

# %%
import re
from collections import Counter

VACIAS = {
    "de","la","el","en","y","a","los","las","del","por","con","un","una","para",
    "que","se","su","al","es","lo","como","mas","o","sus","le","ya","no","sobre",
    "este","esta","son","fue","ser","hay","tras","entre","asi","desde","sin",
}

def palabras(serie: pd.Series) -> Counter:
    c = Counter()
    for t in serie.dropna():
        c.update(w for w in re.findall(r"[a-záéíóúñ]{4,}", t.lower()) if w not in VACIAS)
    return c

for medio in sorted(comun["source_id"].unique()):
    top = palabras(comun[comun["source_id"] == medio]["title"]).most_common(12)
    print(f"\n{medio}:")
    print("  " + " · ".join(f"{w} ({n})" for w, n in top))

# %% [markdown]
# ## 5. Énfasis temático por medio
#
# Proporción, no conteo: los medios tienen volúmenes muy distintos.

# %%
temas = (
    comun.assign(topic=comun["topics"].str.split(","))
    .explode("topic")
    .dropna(subset=["topic"])
    .query("topic != ''")
    .reset_index(drop=True)
)
# Un porcentaje sobre 3 artículos no es un porcentaje. Se excluyen los medios
# con muy pocos etiquetados en la ventana: El Tiempo llega aquí con ~100
# artículos con título frente a los 7.000 de Blu Radio, así que compararlos en
# proporción produciría cifras como "33% medio ambiente" sobre 3 notas.
MIN_ETIQUETADOS = 100

if len(temas):
    por_medio = temas["source_id"].value_counts()
    comparables = por_medio[por_medio >= MIN_ETIQUETADOS].index.tolist()
    excluidos = por_medio[por_medio < MIN_ETIQUETADOS]

    if len(excluidos):
        print(f"Excluidos por muestra insuficiente (<{MIN_ETIQUETADOS} etiquetados):")
        print("  " + ", ".join(f"{m} ({n})" for m, n in excluidos.items()) + "\n")

    sub = temas[temas["source_id"].isin(comparables)]
    if sub["source_id"].nunique() >= 2:
        tabla = (pd.crosstab(sub["topic"], sub["source_id"], normalize="columns") * 100).round(1)
        tabla["_total"] = pd.crosstab(sub["topic"], sub["source_id"]).sum(axis=1)
        print("Porcentaje de artículos etiquetados de cada medio (top 12):")
        print(tabla.sort_values("_total", ascending=False).head(12).to_string())
    else:
        print("Menos de dos medios con muestra suficiente: no hay comparación posible.")
else:
    print("Sin etiquetas. Ejecuta: news-corpus tag")

# %% [markdown]
# ## 6. Lo que TODAVÍA no se puede hacer
#
# - **Sentimiento / tono**: no hay cuerpo del artículo, sólo titular. Y el
#   `CLAUDE.md` §32 excluye el análisis de bias de este servicio.
# - **Comparar volumen entre gobiernos**: el corpus actual sólo cubre Santos I.
# - **Framing fino**: los títulos derivados del slug pierden tildes y
#   puntuación; sirven para frecuencias, no para análisis de matiz.
# - **Entidades nombradas**: posible sobre los títulos, pero con la reserva
#   anterior; será mucho mejor tras la fase de extracción de contenido.
