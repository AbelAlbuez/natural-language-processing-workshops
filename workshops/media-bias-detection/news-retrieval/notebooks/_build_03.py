"""Construye notebooks/03-analisis-del-corpus.ipynb."""

import json
from pathlib import Path

cells = []


def _lines(text):
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
# Analizar el corpus de prensa colombiana

Este notebook es el punto de partida para el análisis. No explica el esquema
—eso está en `02-guia-del-corpus.ipynb`— sino **qué preguntas puede responder
este corpus, cuáles todavía no, y qué filtro hace falta en cada caso para no
medir un artefacto del archivo web en lugar de una diferencia editorial**.

Requisitos: el corpus cargado (`./scripts/restore-db.sh`) y el paquete instalado
(`uv pip install -e ".[dev,export,notebook]"`). Ver `docs/03-guia-del-equipo.md`.

---

## La idea del proyecto en una frase

Queremos saber si distintos medios colombianos **cuentan el mismo hecho de forma
sistemáticamente distinta**, y si eso cambia según el gobierno de turno.

Lo que **no** vamos a hacer es tomar el análisis de sentimiento como medida de
parcialización. Que una noticia sea negativa no la hace parcializada: un
atentado se cuenta en negativo en todos los medios. Lo que buscamos son
diferencias en:

| Dimensión | Ejemplo |
|---|---|
| Framing | "Manifestantes exigen cambios" vs "Disturbios afectan la movilidad" |
| Elección léxica | "reforma" vs "polémica reforma" vs "ambiciosa reforma" |
| Actores | a quién se cita y a quién no |
| Énfasis temático | cuánto espacio recibe cada tema |
""")

code("""
import pandas as pd
from sqlalchemy import create_engine

from news_corpus.config.settings import get_settings

pd.set_option("display.max_colwidth", 80)
pd.set_option("display.width", 160)

engine = create_engine(get_settings().database_url)

df = pd.read_sql(\"\"\"
    select a.id, a.source_id, s.name as medio, a.government_id,
           a.title, a.title_source, a.description, a.section,
           a.published_date, a.date_precision,
           a.content, coalesce(length(a.content), 0) as content_chars
    from article a join source s on s.id = a.source_id
\"\"\", engine, parse_dates=["published_date"])

print(f"{len(df):,} artículos")
df.head(3)
""")

# ── 1. lo primero: qué es analizable ────────────────────────────────────────
md("""
---

## 1. Antes de cualquier análisis: qué parte del corpus es analizable

Esta es la celda más importante del notebook. Saltársela lleva a conclusiones
falsas con mucha facilidad.

El corpus se construyó leyendo archivos web reales, y esos archivos tienen
huecos. Tres columnas registran esos huecos en lugar de esconderlos:

| Columna | Qué significa | Qué pasa si la ignoras |
|---|---|---|
| `date_precision` | `day` = fecha real · `month` = sólo el mes | Asignas artículos al gobierno equivocado |
| `title_source` | `extracted` = titular publicado · `slug` = reconstruido de la URL | Analizas léxico sobre texto sin tildes que nadie escribió |
| `content_chars` | longitud del cuerpo | Comparas medios con texto contra medios sin texto |
""")

code("""
resumen = df.groupby("medio").agg(
    articulos=("id", "count"),
    fecha_fiable=("date_precision", lambda s: (s == "day").sum()),
    titular_real=("title_source", lambda s: (s == "extracted").sum()),
    con_cuerpo=("content_chars", lambda s: (s > 0).sum()),
    cuerpo_analizable=("content_chars", lambda s: (s >= 500).sum()),
    mediana_car=("content_chars", lambda s: int(s[s > 0].median()) if (s > 0).any() else 0),
).sort_values("articulos", ascending=False)

resumen
""")

md("""
### Léelo así

Mira la columna `cuerpo_analizable` frente a `articulos`. Si un medio tiene
miles de artículos pero casi ninguno con cuerpo, **ese medio no puede entrar en
un análisis de texto completo** — no porque falle la extracción, sino porque su
página de archivo no contiene el artículo.

Verificado leyendo el HTML crudo de esa época: hay páginas de Blu Radio sin un
solo párrafo de artículo, sólo un reproductor de audio, y páginas de Caracol con
decenas de referencias a vídeo y ningún `<p>` que no sea navegación.

| Medio | Página de archivo de 2013 | Con cuerpo ≥500 car. |
|---|---|---|
| El Tiempo | la nota completa | **99 %** |
| Noticias Caracol | mezcla de notas escritas y fichas de vídeo | 19 % (ene) → 36 % (mar) |
| Blu Radio | mezcla de notas escritas y posts de audio | 10 % (ene) → 21 % (mar) |

**No es un corte por año: es una proporción que sube**, y se ve ya dentro de
2013. Hacia 2018–2019 los tres medios publican mayoritariamente texto. La medida
buena es siempre la de la tabla que acabas de calcular, sobre lo que realmente
tienes cargado.

**Consecuencia para la ventana de 2013, y es más sutil que "faltan datos":** sí
hay cuerpo de Caracol y Blu Radio, pero **no es una muestra aleatoria** — son
las notas que se publicaron escritas, frente a las que se publicaron en vídeo o
audio. Compararlas contra el 99 % de El Tiempo compara cosas distintas. Para
2013 la comparación honesta entre los tres medios es sobre **titular y
sumario**.
""")

code("""
# Los dos subconjuntos con los que vas a trabajar. Nómbralos explícitamente:
# mezclarlos sin darte cuenta es el error más fácil de cometer aquí.

CUERPO_MINIMO = 500

texto_completo = df[df.content_chars >= CUERPO_MINIMO]
titulares      = df[df.title.notna()]

print(f"texto completo : {len(texto_completo):>6,} artículos · "
      f"{texto_completo.medio.nunique()} medios")
print(f"titulares      : {len(titulares):>6,} artículos · "
      f"{titulares.medio.nunique()} medios")
print()
print(texto_completo.medio.value_counts().to_string())
""")

# ── 2. cobertura temática ───────────────────────────────────────────────────
md("""
---

## 2. Énfasis temático: ¿a qué le da espacio cada medio?

Esta pregunta **sí** se puede responder con los tres medios, porque el
etiquetado temático se hace sobre el titular y no necesita cuerpo.

Pero tiene una trampa propia, y es grande: **no compares números absolutos.**
Si El Tiempo tiene 5.048 artículos y Blu Radio 7.214, cualquier tema saldrá
"más cubierto" por Blu Radio. Lo que se compara es la **proporción dentro de
cada medio**.
""")

code("""
temas = pd.read_sql(\"\"\"
    select a.source_id, s.name as medio, t.id as tema, t.name as tema_nombre,
           coalesce(p.name, t.name) as raiz
    from article_topic at
    join article a on a.id = at.article_id
    join source  s on s.id = a.source_id
    join topic   t on t.id = at.topic_id
    left join topic p on p.id = t.parent_id
\"\"\", engine)

# Proporción, no conteo: cada columna suma 100 % dentro de su medio.
total_por_medio = df.groupby("medio").size()
tabla = (temas.groupby(["tema", "medio"]).size().unstack(fill_value=0))
proporcion = (tabla / total_por_medio * 100).round(2)

proporcion.loc[tabla.sum(axis=1).sort_values(ascending=False).head(12).index]
""")

md("""
### Cómo interpretar esta tabla

Una diferencia entre columnas es una **hipótesis**, no un hallazgo. Antes de
darla por buena hay que descartar dos explicaciones alternativas:

1. **¿Es una diferencia de archivado?** Consulta la tabla `archive_density`:
   quizá ese medio simplemente conservó menos URLs de ese mes.
2. **¿Es una diferencia de etiquetado?** El etiquetado se hace por palabras
   clave sobre el titular. Un medio cuyos titulares son más cortos recibe menos
   etiquetas por razones puramente mecánicas. Contrasta con `title_source`.
""")

code("""
densidad = pd.read_sql(\"\"\"
    select s.name as medio, d.period_start as mes, d.n_urls_offered as urls
    from archive_density d join source s on s.id = d.source_id
    order by d.period_start
\"\"\", engine, parse_dates=["mes"])

densidad.pivot_table(index="mes", columns="medio", values="urls", aggfunc="sum")
""")

# ── 3. léxico ───────────────────────────────────────────────────────────────
md("""
---

## 3. Elección léxica: ¿qué palabras usa cada medio?

Aquí es donde importa la separación del paso 1. Hacemos dos análisis distintos
y **no** los mezclamos:

- **Sobre titulares** — se puede con los tres medios.
- **Sobre el cuerpo** — sólo El Tiempo tiene material suficiente en 2013.

El método es deliberadamente simple: frecuencia relativa y comparación entre
medios. Sin embeddings ni modelos: primero hay que ver los datos crudos.
""")

code("""
import re
import unicodedata
from collections import Counter

# Lista corta de palabras vacías del español. No pretende ser exhaustiva:
# es suficiente para que el ranking deje de estar dominado por preposiciones.
VACIAS = set(\"\"\"
a al algo alguna algunas alguno algunos ante antes como con contra cual cuando
de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese
eso esos esta estan estas este esto estos fue fueron ha habia han hasta hay la
las le les lo los mas me mi mientras muy nada ni no nos o os otra otras otro
otros para pero poco por porque que quien se sea segun ser si sin sobre son su
sus tambien tan tanto te tiene tienen todo todos tras tu un una uno unos y ya
tras sera seran ante bajo cabe hacia mediante durante
\"\"\".split())


def tokenizar(texto):
    \"\"\"Minúsculas, sin tildes, sólo letras. Quita vacías y palabras de 1-2 letras.

    Se quitan las tildes a propósito: parte del corpus tiene titulares
    reconstruidos del slug de la URL, que llegan sin tildes. Sin normalizar,
    'polemica' y 'polémica' contarían como dos palabras distintas y el análisis
    mediría de qué medio salió el titular, no qué palabras usó.
    \"\"\"
    if not isinstance(texto, str):
        return []
    plano = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    return [p for p in re.findall(r"[a-zñ]+", plano)
            if len(p) > 2 and p not in VACIAS]
""")

code("""
def frecuencias(serie):
    c = Counter()
    for t in serie:
        c.update(tokenizar(t))
    total = sum(c.values()) or 1
    return pd.Series(c) / total * 1000   # apariciones por cada mil palabras


lexico = pd.DataFrame({
    medio: frecuencias(grupo.title)
    for medio, grupo in titulares.groupby("medio")
}).fillna(0)

# Las 20 palabras más frecuentes del corpus, medio a medio.
lexico.loc[lexico.sum(axis=1).sort_values(ascending=False).head(20).index].round(2)
""")

md("""
### Palabras distintivas de cada medio

Lo interesante no son las palabras frecuentes —serán parecidas en todos— sino
las que un medio usa **mucho más que los otros**. Se calcula como la razón entre
su frecuencia en un medio y su frecuencia en el resto.
""")

code("""
def distintivas(lexico, medio, minimo=0.15, n=15):
    \"\"\"Palabras con mayor razón de frecuencia frente al resto de medios.

    `minimo` descarta las palabras raras: sin ese filtro, el ranking lo copan
    términos que aparecen dos veces en un medio y ninguna en los demás, lo que
    da una razón enorme y ningún significado.
    \"\"\"
    otros = [c for c in lexico.columns if c != medio]
    suficientes = lexico[lexico[medio] >= minimo]
    razon = suficientes[medio] / (suficientes[otros].mean(axis=1) + 0.01)
    return razon.sort_values(ascending=False).head(n).round(1)


for medio in lexico.columns:
    print(f"── {medio} ──")
    print(distintivas(lexico, medio).to_string())
    print()
""")

md("""
**Cuidado al leer esto.** Buena parte de lo que aparezca serán marcas de la
casa (`blu`, `caracol`, nombres de programas) y secciones, no posicionamiento
editorial. Eso es información útil —dice cómo se autodenomina cada medio— pero
no es framing. El análisis de framing empieza cuando comparas cómo describen
**el mismo hecho**, que es la sección 5.
""")

# ── 4. actores ──────────────────────────────────────────────────────────────
md("""
---

## 4. Actores: ¿a quién nombra cada medio?

Sin un modelo de reconocimiento de entidades, una lista explícita de actores
del período da resultados suficientemente buenos para empezar — y tiene la
ventaja de ser auditable: sabes exactamente qué estás contando.

Amplía la lista según el período que analices.
""")

code("""
ACTORES = {
    "Santos":     r"\\bsantos\\b",
    "Uribe":      r"\\buribe\\b",
    "Farc":       r"\\bfarc\\b",
    "ELN":        r"\\beln\\b",
    "Petro":      r"\\bpetro\\b",
    "Maduro":     r"\\bmaduro\\b",
    "Chávez":     r"\\bch[aá]vez\\b",
    "Gobierno":   r"\\bgobierno\\b",
    "Oposición":  r"\\boposici[oó]n\\b",
    "Fiscalía":   r"\\bfiscal[ií]a\\b",
    "Congreso":   r"\\bcongreso\\b",
}

texto_busqueda = (titulares.title.fillna("") + " " +
                  titulares.description.fillna("")).str.lower()

menciones = pd.DataFrame({
    actor: texto_busqueda.str.contains(patron, regex=True)
    for actor, patron in ACTORES.items()
})
menciones["medio"] = titulares.medio.values

# Por mil artículos del propio medio: de nuevo, proporción y no conteo.
tasa = (menciones.groupby("medio").mean() * 1000).round(1).T
tasa.assign(_orden=tasa.mean(axis=1)).sort_values("_orden", ascending=False).drop(columns="_orden")
""")

# ── 5. mismo hecho ──────────────────────────────────────────────────────────
md("""
---

## 5. El mismo hecho contado por dos medios

Esta es **la** comparación que motiva el proyecto: mismo acontecimiento,
distintos medios, distinto framing.

Todavía no hay un agrupador de acontecimientos —es trabajo pendiente— pero se
puede aproximar: artículos publicados **el mismo día** por **medios distintos**
que comparten palabras poco comunes en el titular. No es perfecto; sirve para
encontrar casos que leer a mano, que es como debe empezar un análisis de framing.
""")

code("""
def candidatos_mismo_hecho(df, minimo_comunes=3, max_resultados=15):
    \"\"\"Pares de artículos de medios distintos, mismo día, titulares solapados.

    Sólo se usan artículos con `date_precision == 'day'`: con precisión de mes
    'el mismo día' no significa nada.
    \"\"\"
    fiables = df[(df.date_precision == "day") & df.title.notna()].copy()
    fiables["tokens"] = fiables.title.map(lambda t: set(tokenizar(t)))

    pares = []
    for dia, grupo in fiables.groupby(fiables.published_date.dt.date):
        if grupo.medio.nunique() < 2:
            continue
        filas = grupo.to_dict("records")
        for i, a in enumerate(filas):
            for b in filas[i + 1:]:
                if a["medio"] == b["medio"]:
                    continue
                comunes = a["tokens"] & b["tokens"]
                if len(comunes) >= minimo_comunes:
                    pares.append({
                        "fecha": dia, "comunes": len(comunes),
                        "palabras": " ".join(sorted(comunes)),
                        "medio_a": a["medio"], "titular_a": a["title"],
                        "medio_b": b["medio"], "titular_b": b["title"],
                    })
    return (pd.DataFrame(pares)
            .sort_values("comunes", ascending=False)
            .head(max_resultados)
            .reset_index(drop=True))


pares = candidatos_mismo_hecho(df)
print(f"{len(pares)} pares candidatos\\n")
for _, p in pares.head(8).iterrows():
    print(f"[{p.fecha}] palabras en común: {p.palabras}")
    print(f"  {p.medio_a:<18} {p.titular_a}")
    print(f"  {p.medio_b:<18} {p.titular_b}")
    print()
""")

md("""
### Qué hacer con estos pares

Léelos. En serio: el análisis de framing empieza leyendo. Para cada par,
pregúntate:

- ¿Quién es el sujeto de la frase? ("La policía dispersó" vs "Manifestantes
  fueron dispersados" — el segundo borra al actor.)
- ¿Qué se nombra y qué se omite?
- ¿Qué adjetivos aparecen?
- ¿A quién se cita como fuente?

Cuando tengas 20 o 30 leídos, tendrás una hipótesis concreta que sí vale la
pena medir a escala. Ese es el orden correcto: leer primero, medir después.
""")

# ── 6. límites ──────────────────────────────────────────────────────────────
md("""
---

## 6. Qué **no** puede responder este corpus todavía

Vale tanto como lo que sí puede. Si presentas resultados, esta lista debería
aparecer en el informe.

| Pregunta | Por qué no, todavía |
|---|---|
| ¿Cómo cambia la cobertura entre gobiernos? | La ventana cargada es demasiado corta. Hace falta `collect` de más años. |
| ¿Qué medio es más parcializado? | No es una pregunta que un corpus responda. Se miden dimensiones concretas —léxico, actores, framing— y se describen. |
| ¿Cómo enmarca Blu Radio un hecho, en cuerpo? | Sólo el 10–21 % de su archivo de 2013 conserva texto, y ese subconjunto son las notas escritas, no una muestra de su cobertura. |
| ¿Cuánto espacio le dio cada medio a un tema? | Se aproxima con proporciones, pero sin longitud del artículo no es "espacio" real. |
| ¿Qué hechos cubrió un medio y otro omitió? | Requiere agrupar acontecimientos, que aún no está implementado. |

### Para ampliar el corpus

```bash
# Más años, donde los tres medios sí tienen cuerpo
news-corpus collect -s el_tiempo -s noticias_caracol -s blu_radio \\
  --from 2019-01 --to 2019-12
news-corpus extract --all
news-corpus tag --retag
./scripts/dump-db.sh     # y compartir el dump actualizado
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

out = Path("notebooks/03-analisis-del-corpus.ipynb")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{out} · {len(cells)} celdas")
