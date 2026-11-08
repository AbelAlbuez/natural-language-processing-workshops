# Tratamiento del slug — titular, sección y piezas no informativas

Registro del procesamiento aplicado el 2026-11-04 sobre el corpus unificado del
2026-10-04 (`dumps/news_corpus_unificado_2026-10-04.dump`). Está escrito para
poder trasladarlo al artículo: decisiones, reglas, cifras de antes y después,
validación y limitaciones. La última sección trae un borrador de texto.

## 1. Decisión: trabajar con el slug

Descargar el artículo completo resultó inviable a escala: de 1.733.421 URLs
sólo ~15.900 tienen cuerpo, todas de El Tiempo, Blu Radio y Caracol, y RCN, La
República, Cambio y El Espectador no tienen ninguno. El slug, en cambio, está en
el 100 % de las URLs y estos medios lo escriben como el titular:

    https://www.noticiascaracol.com/politica/no-apoyamos-la-prorroga-para-nosotros-mininterior-rg10
                                   └ sección ┘└──────────────── titular ───────────────┘└ código CMS ┘

Por eso la unidad de análisis es el **titular reconstruido desde la URL**
(`title_source = 'slug'`), con la sección tomada del primer segmento del path.

## 2. Pipeline

```bash
alembic upgrade head            # añade article.non_news_reason (migración 7b3f9c1d2e40)
news-corpus enrich --all        # titular + sección + non_news_reason para todo el corpus
news-corpus tag --retag         # etiquetado temático (config/topics.yaml) sobre los titulares nuevos
news-corpus export -o exports/corpus.parquet   # el export lleva non_news_reason
```

En Docker: `docker exec -w /workspace news-corpus-jupyter news-corpus enrich --all`.
`enrich --all` tarda ~4 min y `tag --retag` ~11 min sobre 1,73 M de URLs.

Para cada URL, `derive_from_url` (`src/news_corpus/pipeline/enrich.py`):

1. Limpia el último segmento del path: extensión (`.html`), prefijos de plantilla
   (`articulo-`, `MAM-`), **código del CMS de Blu Radio y Caracol** (§3.1) e ID
   numérico final (`-3942567`, `+articulo+12567802`).
2. Parte por `-`, `_` y `+`, descarta números sueltos y restos de plantilla, y
   capitaliza la primera letra. Un slug de menos de 8 caracteres no da titular.
3. Toma la **sección** del primer segmento (§3.2).
4. Clasifica el titular ya limpio y su sección: si es una pieza no informativa
   guarda el motivo en `non_news_reason` (§3.3).

**Nada se borra.** Todas las URLs conservan titular y sección; las no
informativas sólo quedan marcadas. El análisis filtra con
`non_news_reason IS NULL`. Los titulares `extracted` (leídos de la página) nunca
se sobrescriben; con `--all` sí se vuelven a derivar los de `slug`, para que todo
el corpus use la misma versión de las reglas.

## 3. Correcciones

### 3.1 Código del CMS al final del slug

Blu Radio y Caracol (mismo CMS) cierran el slug con dos letras y dos dígitos:
`-rg10`, `-so35`, `-cb20`, `-pr30`, `-rs15`, a veces repetido (`-rg10-rg10`,
`-so35-rg10`). Lo llevaban **219.959 URLs de Blu Radio (58 %)** y **102.746 de
Caracol (49 %)**. Sin quitarlo, era la palabra más frecuente de ambos medios:

| Medio | Top 5 de palabras antes | Top 5 después |
|---|---|---|
| Blu Radio | rg10, so35, cb20, no, pr30 | no, colombia, bogota, resultado*, contra |
| Caracol | rg10, so35, video, bogota, no | no, bogota, video, colombia, anos |

\* "resultado" sale de los boletines de chance, que luego se marcan (§3.3).

La regla sólo se aplica a `bluradio.com` y `noticiascaracol.com`, y sólo a los
prefijos observados (`rg so cb pr rs ex cm ah si`), porque hay colas legítimas
con la misma forma: `asteroide-da14`, `vuelo mh17`, `ub40`, `bb10`. Quedan 2
URLs con el código pegado con otro separador (`_pr30`, `- rg10`).

### 3.2 Sección

Antes sólo se aceptaba una lista cerrada de 29 secciones. Secciones enteras se
quedaban sin asignar: `nacion` (60k URLs de Blu Radio), `globoeconomia` (66k de
La República), `tendencias` (RCN), `pais` y `poder` (Cambio). Ahora:

- Con **dos o más segmentos** en el path, el primero nunca es el slug, así que se
  toma tal cual, sin tildes (Caracol publica a la vez `/politica/` y `/política/`).
  Se excluyen segmentos de plantilla (`documento`, `articulo`), números y URLs
  mal formadas (`don-juanhttps:`).
- Con **un solo segmento**, sigue exigiéndose la lista conocida.

Cobertura de sección con la regla anterior → con la nueva:

| Medio | Antes | Después |
|---|---|---|
| El Tiempo | 94,8 % | 100,0 % |
| Blu Radio | 49,7 % | 99,9 % |
| Noticias RCN | 82,4 % | 100,0 % |
| Noticias Caracol | 86,9 % | 99,9 % |
| La República | 41,7 % | 100,0 % |
| Cambio | 32,5 % | 99,6 % |

Las secciones son la **taxonomía propia de cada medio** (8 en RCN, 74 en Blu
Radio). No están armonizadas entre medios: comparar "economía" de un medio con
la de otro exige un mapeo explícito.

### 3.3 Piezas no informativas (`non_news_reason`)

Los sitemaps listan todo lo que publica el medio. Con el titular del slug, los
formatos de servicio repiten el mismo texto miles de veces ("Caricatura de
Rodrigo Guerreros" 362 veces; "Emisión p. m. … de" en RCN) y distorsionan
frecuencias y volúmenes por tema. Se marcan con estas reglas:

| Motivo | Regla | Ejemplo |
|---|---|---|
| `emision` | sección `emisiones`; titular que empieza por "emisión", contiene "programa completo" o empieza por "reviva el capítulo" | `Bla bla blu programa completo del … de noviembre` |
| `servicio` | horóscopo; titular que **empieza** por "pico y placa"; nombre de un juego de azar (lotería, chance, baloto, miloto, chontico, dorado mañana…) **y** "resultado/ganador/sorteo"; sección `loterias` | `Chontico día resultado del último sorteo hoy…` |
| `comercial` | secciones `contenido-comercial`, `contenido-patrocinado`, `publicidad-politica-pagada`, `apuestas-deportivas`, `corporativo` | `El amor por el deporte es el secreto de Decathlon` |
| `indicador` | "precio(s)/cotización del dólar/oro/petróleo/euro…" + "hoy"; titular que empieza por "dólar hoy"/"oro hoy" | `Precios del dólar y del petróleo hoy … de abril` |
| `caricatura` | titular que empieza por "caricatura de" | `Caricatura de Vladdo` |
| `multimedia` | podcast; "video titulares/entretenimiento de" | `Video titulares de septiembre` |
| `obituario` | sección `condolencias` (avisos pagados) | — |

Las reglas exigen dos condiciones cuando una sola es ambigua: "así será el
sorteo de la Libertadores" no se marca (no nombra un juego de azar) y "cambios y
multas en el pico y placa de Medellín" tampoco (no empieza por "pico y placa").

**Reglas descartadas tras revisar muestras:** las secciones `videos-eltiempo` y
`eltiempoplay` (traen notas de video que sí son noticias: "Corte Suprema de EE.
UU. rechaza intento de Trump…") y `obituarios` de La República (notas sobre la
muerte de figuras públicas: "Falleció el papa Francisco").

Resultado:

| Medio | URLs | No informativas | % | Analizables* |
|---|---|---|---|---|
| El Tiempo | 683.173 | 16.130 | 2,4 | 666.406 |
| Blu Radio | 382.333 | 38.848 | 10,2 | 342.538 |
| Noticias RCN | 211.309 | 12.300 | 5,8 | 199.001 |
| Noticias Caracol | 210.606 | 9.475 | 4,5 | 200.709 |
| La República | 200.589 | 1.774 | 0,9 | 198.536 |
| Cambio | 44.575 | 321 | 0,7 | 44.152 |
| El Espectador | 835 | 11 | 1,3 | 803 |
| Semana | 1 | 0 | — | 0 |
| **Total** | **1.733.421** | **78.859** | **4,5** | **1.652.145** |

\* Con titular y `non_news_reason IS NULL`.

Por motivo: servicio 41.112 · emisión 26.322 · comercial 5.394 · indicador
3.744 · caricatura 2.281 · multimedia 3 · obituario 3. Blu Radio concentra la
mitad (23.493 de servicio, sobre todo chance, y 15.161 programas completos).

## 4. Validación

**Tests.** `tests/test_enrich_and_tagging.py` fija cada regla con URLs reales del
corpus, incluidos los casos que **no** deben cambiar (colas `da14`/`mh17`,
noticias sobre el dólar o sobre loterías, notas de video).

**Precisión de las marcas.** Muestra aleatoria de 20 URLs por motivo (los 5 con
volumen), revisada a mano:

```sql
select setseed(0.42);
select non_news_reason, title from (
  select non_news_reason, title,
         row_number() over (partition by non_news_reason order by random()) r
  from article where non_news_reason in
    ('servicio','emision','comercial','indicador','caricatura')) x
where r <= 20 order by 1;
```

| Motivo | Correctas | Errores |
|---|---|---|
| caricatura | 20/20 | — |
| emision | 20/20 | — |
| comercial | 20/20 | la marca sigue la sección del medio, no el contenido |
| servicio | 19/20 | "Pico y placa Bogotá: habrá nueva medida en la calle" (noticia) |
| indicador | 17/20 | 3 notas diarias de mercado con algo de contenido ("Dólar hoy: caída del crudo por temor del coronavirus…") |
| **Total** | **96/100** | |

No se estimó la cobertura (recall): quedan formatos de servicio sin regla
(clima, programación de TV, "en vivo" deportivos).

## 5. Efecto en el corpus

| | Antes | Después |
|---|---|---|
| URLs con titular | 138.629 | 1.731.003 (2.418 sin titular derivable, p. ej. `/archivo/documento/MAM-2880084`) |
| URLs con sección | 94.086 | 1.732.807 |
| URLs con código CMS en el titular | 322.705 (derivación anterior) | 2 |
| Artículos con al menos un tema | 43.816 (54.935 etiquetas) | 519.547 (645.730 etiquetas); 503.491 son noticias |
| Esquema (alembic) | `29e030435542` | `7b3f9c1d2e40` |

El salto del etiquetado se debe a que ahora el titular existe para todo el
corpus; las reglas de `config/topics.yaml` no cambiaron (versión `140be257414e`).

Antes del proceso se guardó la base en
`dumps/respaldo_pre_restore_2026-11-04.dump` (idéntica al dump del 2026-10-04).

## 6. Distribución del corpus analizable

Noticias con titular y `non_news_reason IS NULL`: **1.652.145**. Todas tienen
fecha; 42.418 (2,6 %) sólo con precisión de mes. Consulta en
[`02-consultas.md`](02-consultas.md#corpus-analizable-por-año-y-medio).

### Por año y medio

| Año | El Tiempo | Blu Radio | RCN | Caracol | La República | Cambio | El Espectador | **Total** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2013 | 167 | 7.213 | — | 4.938 | — | — | — | **12.318** |
| 2016 | 4.879 | — | — | — | — | — | — | **4.879** |
| 2018 | 21.992 | 14.643 | 4.665 | 10.809 | 9.340 | — | — | **61.449** |
| 2019 | 57.175 | 34.187 | 11.500 | 23.979 | 21.967 | — | — | **148.808** |
| 2020 | 58.522 | 40.186 | 14.803 | 34.435 | 22.483 | — | — | **170.429** |
| 2021 | 75.983 | 42.139 | 23.584 | 23.435 | 23.601 | — | — | **188.742** |
| 2022 | 79.481 | 41.595 | 29.487 | 22.075 | 24.079 | 3.436 | — | **200.153** |
| 2023 | 102.798 | 43.907 | 28.303 | 25.047 | 25.247 | 12.355 | — | **237.657** |
| 2024 | 104.063 | 48.068 | 38.849 | 28.570 | 26.661 | 12.684 | — | **258.895** |
| 2025 | 101.723 | 44.285 | 29.891 | 17.802 | 25.883 | 10.531 | — | **230.115** |
| 2026* | 59.623 | 26.315 | 17.919 | 9.619 | 19.275 | 5.146 | 803 | **138.700** |
| **Total** | **666.406** | **342.538** | **199.001** | **200.709** | **198.536** | **44.152** | **803** | **1.652.145** |

\* Enero–agosto de 2026. 2014, 2015 y 2017 no tienen ninguna URL. Semana: 0.

### Por gobierno

| Gobierno | Período en el corpus | El Tiempo | Blu Radio | RCN | Caracol | La República | Cambio | El Espectador | **Total** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Santos 1 | ene–may 2013 | 167 | 7.213 | — | 4.938 | — | — | — | **12.318** |
| Santos 2 | 2016 → 2018-08-06 | 5.925 | 535 | — | 393 | 267 | — | — | **7.120** |
| Duque | 2018-08-07 → 2022-08-06 | 258.413 | 155.303 | 72.646 | 105.861 | 91.010 | 98 | — | **683.331** |
| Petro | 2022-08-07 → 2026-08-06 | 396.207 | 176.661 | 123.615 | 88.404 | 105.301 | 44.054 | 803 | **935.045** |
| Sin gobierno | — | 5.694 | 2.826 | 2.740 | 1.113 | 1.958 | — | — | **14.331** |

Sin gobierno: 13.066 son del 7 al 31 de agosto de 2026, posteriores al gobierno
Petro (el siguiente no está en la tabla `government`), y 1.265 tienen precisión
de mes en agosto de 2018 o 2022, meses de posesión en los que asignar un
gobierno sería inventar el dato.

Estas cifras incluyen las fechas de precisión `month`. Con
`date_precision = 'day'`, Duque baja de 683.331 a 649.889 (−4,9 %) y Petro de
935.045 a 927.334 (−0,8 %); Santos no cambia. La pérdida se concentra en RCN:
sus 4.665 noticias de 2018 y 9.592 de las 11.500 de 2019 sólo tienen mes. Un
corte fino por fecha (semanas, eventos) en RCN 2018–2020 no es sólido.

### Lectura

1. **Sólo Duque y Petro son comparables.** Cinco medios (El Tiempo, Blu Radio,
   RCN, Caracol, La República) tienen cobertura continua de 2018-08 a 2026-08.
   Santos no lo es: 2013 es el piloto (enero–mayo), 2016 sólo trae El Tiempo y
   2014, 2015 y 2017 no existen en el corpus.
2. **Cambio sólo cubre a Petro** (44.054 de 44.152): sirve para comparar medios
   dentro de ese gobierno, no entre gobiernos. El Espectador (una semana de
   julio de 2026) y Semana no tienen volumen analizable.
3. **El volumen no es cobertura.** El Tiempo pasa de ~58k noticias/año
   (2019–2020) a más de 100k desde 2023, y Caracol cae a 17.802 en 2025. Antes de
   leerlo como cambio editorial hay que contrastarlo con `archive_density`: puede
   reflejar lo que el medio expone en sus sitemaps.
4. **Petro tiene un 37 % más de noticias que Duque** (935k frente a 683k). Las
   comparaciones entre gobiernos deben hacerse en proporciones (p. ej. la
   participación de un tema dentro de cada medio), no en conteos absolutos.

## 7. Limitaciones

- **El titular es una reconstrucción.** Pierde tildes, mayúsculas, comillas y
  puntuación, y puede diferir del publicado si el medio cambió el titular o
  escribió el slug para buscadores.
- **Se pierden los números.** La limpieza descarta todos los tokens numéricos
  para quitar IDs, y con ellos cifras y fechas del titular ("Bogotá registró
  casos nuevos de covid, ya van"). Afecta poco al análisis léxico y mucho a
  cualquier extracción de cantidades.
- **Las reglas de no-noticia son patrones de superficie**, construidos sobre los
  titulares más repetidos. Precisión ~96 % en la muestra; cobertura no medida.
- **Las secciones no están armonizadas** entre medios.
- **El Espectador (835) y Semana (1)** no tienen volumen para comparar.

## 8. Borrador para el artículo

> Dado que la descarga del cuerpo de los artículos sólo fue posible para cerca
> del 1 % de las URLs, se adoptó como unidad de análisis el titular reconstruido
> a partir del *slug* de la URL, disponible para el 99,9 % del corpus
> (1.731.003 de 1.733.421 URLs). La reconstrucción elimina la extensión, los
> prefijos de plantilla, los identificadores numéricos y, en Blu Radio y Noticias
> Caracol, un código de dos letras y dos dígitos que el gestor de contenidos
> añade al final del *slug* (presente en el 58 % y el 49 % de sus URLs, y que sin
> tratamiento era el término más frecuente de ambos medios). La sección se tomó
> del primer segmento de la ruta, lo que elevó su cobertura del 32–95 % al
> 99,6–100 % según el medio.
>
> Las URLs que no corresponden a piezas informativas —emisiones y programas
> completos, resultados de juegos de azar, pico y placa, cotizaciones diarias,
> caricaturas y contenido patrocinado— se identificaron mediante reglas sobre la
> sección y el titular y se marcaron sin eliminarse: 78.859 URLs (4,5 %), con
> máxima incidencia en Blu Radio (10,2 %). Una revisión manual de 100 URLs
> marcadas (20 por categoría) arrojó una precisión del 96 %. El corpus analizable
> queda en 1.652.145 titulares de seis medios. Los titulares reconstruidos
> carecen de tildes, puntuación y cifras, y pueden diferir del titular publicado;
> cada registro conserva su procedencia (`title_source`) y el motivo de exclusión
> (`non_news_reason`).
