# Entrega 3 — LDA conjunto Duque + Petro

Modelo de tópicos (LDA) entrenado una sola vez sobre los dos gobiernos, para que
los tópicos sean los mismos al comparar **medios dentro de un gobierno** y **cada
medio entre gobiernos**. El LDA no identifica temas en sentido estricto: muestra
qué palabras tienden a aparecer juntas en los titulares. Las etiquetas son una
interpretación humana (`topic_labels.csv`).

Resumen de resultados para el equipo: [`RESUMEN_EJECUTIVO.md`](RESUMEN_EJECUTIVO.md).
Las mejoras posteriores (subcorpus de asuntos públicos, control por sección, LDA
de consenso y BERTopic) están en la [sección final](#mejoras-subcorpus-de-asuntos-públicos-control-por-sección-lda-de-consenso-y-bertopic).

## Datos

Corpus `news_corpus` restaurado del dump del 2026-10-04 y procesado el
2026-11-04 (titulares del slug, secciones y marca `non_news_reason`; ver
[`news-retrieval/docs/07-tratamiento-del-slug.md`](../news-retrieval/docs/07-tratamiento-del-slug.md)).

| Paso | Titulares |
|---|---:|
| Export 2018-08 → 2026-08 (todos los medios) | 1.716.219 |
| Gobierno Duque o Petro (`government_id`) | 1.698.581 |
| 5 medios con los dos gobiernos | 1.653.170 |
| Con titular | 1.650.907 |
| Noticias (`non_news_reason IS NULL`) | **1.573.421** |
| Muestra de entrenamiento (40.000 × medio × gobierno) | 400.000 |

Medios: El Tiempo, Blu Radio, Noticias RCN, Noticias Caracol y La República.
Cambio (sólo Petro), El Espectador y Semana quedan fuera.

## Reproducir

```bash
# 1. Export (desde news-retrieval/, con la base levantada)
docker exec -w /workspace news-corpus-jupyter \
  news-corpus export -o exports/duque-petro.parquet --from 2018-08-01 --to 2026-08-31 --no-content

# 2. Imagen y pipeline (desde entrega3/)
docker build -t duque-petro-lda:local .
./run.sh all            # o una etapa: prepare | train | stability | infer | examples | robustness | compare
```

En 12 núcleos tarda ≈25 min en total: `train` ≈9 min, `robustness` ≈6 min y el
resto menos de 3 min cada una. `config.json` guarda el SHA-256 del input y de las
stopwords; una etapa se niega a correr sobre resultados de otra configuración.
`prepared.parquet`, `theta.npy` y los modelos de la grilla y de las semillas
alternativas no se versionan (se regeneran).

Tests: `docker run --rm -v "$PWD/..:/workspace" -w /workspace/entrega3 -e PYTHONPATH=/workspace/entrega3:/workspace/entrega2 duque-petro-lda:local python -m pytest tests ../entrega2/tests`.

## Decisiones

| Decisión | Por qué |
|---|---|
| **Un solo modelo para los dos gobiernos** | Con dos modelos, los tópicos no se pueden alinear entre sí y la comparación no tendría unidad común. |
| **Muestra balanceada**: 40.000 por medio × gobierno | El Tiempo es el 42 % de las noticias y Petro tiene un 37 % más de titulares que Duque: sin balancear, definirían los tópicos por volumen. La celda más chica (RCN–Duque) tiene 72.646. |
| **Stopwords de dominio** (`stopwords_dominio.txt`) | Días, meses, numerales escritos y marcadores de formato («video», «asi», «tras») dominaban la frecuencia. Se conservan actores, lugares e instituciones. Se quitan «estado(s)» de la lista de NLTK para que se forme `estados_unidos`. |
| **Bigramas con `Phrases`** | 1.313 de los 15.276 términos del vocabulario son bigramas: `gustavo_petro`, `reforma_pensional`, `clan_golfo`, `corte_suprema`. |
| **K = 15** | Máximo c_v (0,417) en la grilla K = 10, 15, 20, 25, 30, 40. La perplejidad en held-out crece con K y no ayuda a elegir. |
| **Distribución completa θ** | Con ~6 tokens por titular, la confianza media del tópico mayor es 0,51. Las participaciones promedian θ en vez de contar el tópico dominante. |
| **Δ relativo** | (Petro − Duque) del medio menos el promedio de los otros cuatro. Descuenta los cambios de agenda que afectan a todos (p. ej. COVID). |
| **Bootstrap de bloques** de 3 meses + Holm | Las participaciones mensuales están autocorrelacionadas; Holm corrige las 75 comparaciones medio × tópico. |

## Estabilidad y robustez

Con otras dos semillas (7 y 123), los tópicos se emparejaron con el algoritmo
húngaro y se compararon por sus 10 palabras principales (Jaccard):

- **Robustos (≥ 0,5): 3.** Fútbol, Conflicto armado y orden público, Gobierno–Petro–política internacional.
- **Parciales (0,3–0,5): 2.** Sucesos (accidentes y muertes), Justicia y tribunales.
- **Inestables (< 0,3): 10.**

Priors dispersos (α = 0,05, η = 0,01) y 20 pasadas no mejoraron la estabilidad
(`experimento_priors.csv`). Es una limitación conocida del LDA en textos muy
cortos.

Aun así, el **Δ relativo** se sostiene bastante: entre el modelo base y los de las otras semillas tiene
correlación 0,89 y 0,87, y conserva el signo en el 93 % de los pares medio ×
tópico robustos (80 % parciales, 40 % inestables). Por eso sólo se interpretan
los Δ de tópicos robustos o parciales que además conservan el signo
(`deltas.csv`: `robustez`, `mismo_signo_otras_semillas`).

## Figuras (`resultados/figuras/`)

| # | Figura | Qué muestra |
|---|---|---|
| 01 | `01_embudo_corpus.png` | De 1,72 M de URLs del export a 1,57 M de noticias y 400 k de entrenamiento |
| 02 | `02_volumen_mensual.png` | Noticias por mes y medio; El Tiempo pasa de ~5 k a ~9 k/mes desde 2023 |
| 03 | `03_muestra_balanceada.png` | Disponibles por celda frente a los 40 k que se usan |
| 04 | `04_tokens_antes_despues.png` | Top 20 de palabras antes y después de limpiar; aparece `estados_unidos` |
| 05 | `05_ejemplo_titular.png` | Un titular de URL a θ, paso a paso |
| 06 | `06_seleccion_k.png` | c_v y perplejidad por K |
| 07 | `07_estabilidad_semillas.png` | Similitud de tópicos entre semillas: pocos estables |
| 08 | `08_topicos_palabras.png` | 10 palabras por tópico; en gris los inestables |
| 09 | `09_mapa_topicos.png` | Distancia entre tópicos (MDS); interactivo en `lda_visualization.html` |
| 10 | `10_confianza.png` | Confianza del tópico mayor por medio |
| 11 | `11_heatmap_medio_gobierno.png` | Agenda de cada medio en cada gobierno |
| 12 | `12_delta_relativo.png` | **Figura central**: Δ relativo con IC 95 %, por medio |
| 13 | `13_distancias_js.png` | Distancia de agendas entre medios y de cada medio consigo mismo |
| 14 | `14_series_topicos.png` | Series mensuales de los tópicos que más cambiaron |

## Limitaciones

- Titulares reconstruidos: sin tildes, cifras ni puntuación; pueden diferir del publicado.
- 10 de 15 tópicos son inestables entre semillas; sus resultados no se interpretan.
- RCN 2018–2020 sólo tiene fecha mensual; su serie temprana es menos fiable.
- El volumen depende de los sitemaps (`archive_density`). El salto de Fútbol en
  RCN (9,3 % → 18,5 %) coincide con un cambio en su archivo: la sección
  `deportes` pasa de ~1 % de sus URLs en 2019–2020 a 43–45 % en 2023–2024
  (14,8 % en Duque, 33,5 % en Petro). Lo mismo, en sentido contrario, en El
  Tiempo (15,7 % → 9,6 %) y Blu Radio (12,5 % → 9,1 %). Los Δ de Fútbol siguen
  la composición de cada archivo y no deben leerse como decisión editorial sin
  controlar por sección.
- Un tópico es co-ocurrencia de palabras, no un tema ni un encuadre: el LDA
  mide **agenda** (qué se cubre), no **framing** (cómo se cubre).

## Borrador para el artículo

> Para comparar la agenda de los medios entre gobiernos se entrenó un único
> modelo LDA (K = 15, elegido por coherencia c_v = 0,417) sobre una muestra
> balanceada de 400.000 titulares —40.000 por medio y gobierno— y se infirió la
> distribución de tópicos de las 1.573.421 noticias de cinco medios bajo los
> gobiernos de Duque y Petro. Los titulares se preprocesaron con stopwords de
> dominio y detección de bigramas. Dado que los titulares tienen en promedio seis
> tokens útiles, la estabilidad del modelo se evaluó reentrenándolo con dos
> semillas adicionales: tres tópicos resultaron robustos (fútbol, conflicto
> armado y gobierno–política internacional) y dos parcialmente robustos (sucesos
> y justicia). Para separar los cambios propios de cada medio de los cambios de
> la agenda informativa general, se calculó un Δ relativo: la diferencia entre
> gobiernos en la participación de un tópico en un medio, menos la diferencia
> promedio en los otros cuatro, con intervalos por bootstrap de bloques mensuales
> y corrección de Holm. De los 75 pares medio–tópico, 13 muestran un Δ relativo
> significativo en tópicos robustos o parciales que conserva el signo con las
> tres semillas; 5 siguen siéndolo al controlar por la mezcla de secciones de
> cada medio.


## Mejoras: subcorpus de asuntos públicos, control por sección, LDA de consenso y BERTopic

Tres debilidades del LDA anterior motivaron esta segunda ronda: 10 de 15 tópicos
inestables entre semillas, una agenda dominada por fútbol, farándula y sucesos, y
cambios entre gobiernos que seguían la composición de los archivos (la sección
de deportes de RCN pasa del ~1 % al 43–45 % de sus URLs).

### Subcorpus de asuntos públicos

`subcorpus_publico.sh` lista las noticias con al menos una etiqueta del tesauro
(`config/topics.yaml`) de política, economía, seguridad, justicia o relaciones
internacionales **encontrada en el titular**. No se usan las coincidencias en la
URL ni en la sección porque las taxonomías no son comparables entre medios (RCN
no tiene sección de política ni de justicia). Resultado: **313.170 titulares**;
la celda más chica es RCN–Duque (14.689), así que la muestra balanceada es de
14.000 por medio × gobierno (140.000). Vocabulario: 6.678 términos, 454 bigramas.

### Control por sección

`topics.section_weights` repondera, dentro de cada medio, para que los dos
gobiernos tengan la misma mezcla de las secciones *de ese medio*
(peso = p(sección | medio) / p(sección | medio, gobierno); secciones con menos
del 0,5 % se agrupan). No hace falta armonizar taxonomías porque la comparación
es siempre dentro del mismo medio. Lo que queda es el cambio *dentro* de las
secciones; un cambio editorial real de cuánto espacio da el medio a una sección
también se descuenta, por eso `deltas.csv` trae las dos versiones (`delta_rel_*`
y `secc_delta_rel_*`). Figura: `16_control_seccion.png`.

### Corrección de potencia del bootstrap

Con 2.000 réplicas, el p-valor bootstrap no baja de 1/2.000 y Holm lo multiplica
por el número de pruebas: con 125 pruebas (LDA K = 25 × 5 medios) el mínimo
ajustado era 0,0625 y **ningún cambio podía ser significativo**; con 75 pruebas
el mínimo era 0,0375, apenas bajo el umbral. Se pasó a **20.000 réplicas**
(`BOOTSTRAP_REPS`; piso ajustado 0,005 con 100 pruebas). Con eso el LDA del corpus
completo queda en 13 cambios fiables en vez de 14 (Fútbol en Caracol pasa a
p = 0,17).

### Modelos sobre el subcorpus

| Modelo | K | c_v | Jaccard top-10 entre semillas | Robustos / parciales | Corr. Δ entre semillas | Δ fiables sin / con control |
|---|---:|---:|---:|---|---:|---|
| LDA · corpus completo (referencia) | 15 | 0,417 | 0,25 | 3 / 2 | 0,88 | 13 / 5 de 75 |
| LDA · asuntos públicos | 25 | 0,360 | 0,19 | 1 / 3 | 0,67 | 7 / 2 de 125 |
| LDA de consenso · asuntos públicos | 12 | 0,319 | 0,22 | 0 / 2 | 0,76 | 2 / 1 de 60 |
| BERTopic · asuntos públicos | 20 | 0,398 | **0,79** | **19 / 0** | **0,95** | **22 / 10 de 100** |

Fuente: `resultados_publico/comparacion_metodos.csv` (`comparar_metodos.py`). La
c_v se calcula con los textos de la muestra de cada corpus, así que la del
corpus completo no es directamente comparable con las del subcorpus.

- **LDA · asuntos públicos**: grilla K = 10–30; máximo c_v en K = 25.
- **LDA de consenso** (`gensim.models.EnsembleLda`): 16 LDA de K = 25 por
  semilla, tres semillas. Con el radio por defecto (eps = 0,1) sólo sobrevivían
  3–4 tópicos de 400; `ensemble_eps.csv` muestra que desde eps = 0,3 las tres
  semillas dejan 12, y se usó ese valor. Aun así los tópicos de consenso no se
  repiten entre ensambles (Jaccard 0,22) y en su mayoría son mezclas.
- **BERTopic** (`bertopic_topics.py`, imagen `Dockerfile.bertopic`): embeddings
  `paraphrase-multilingual-MiniLM-L12-v2` del titular, UMAP a 5 dimensiones y
  k-means (k = 20) en vez de HDBSCAN, para que todo titular tenga tópico y las
  participaciones sean comparables (θ es one-hot). El c-TF-IDF se calcula con el
  vocabulario del diccionario del LDA: el `CountVectorizer` interno de BERTopic
  aplica `min_df` sobre un documento por tópico y dejaba sólo 164 palabras.

### Hallazgos que se repiten entre modelos

Con control por sección, significativos y del mismo signo en al menos dos
modelos (`resultados_publico/hallazgos_coincidentes.csv`):

| Medio | Tema | Dirección | Modelos | Δ con control |
|---|---|---|---|---|
| El Tiempo | Inseguridad urbana y sucesos | más | LDA completo, consenso, BERTopic | +1,1 a +1,7 pp |
| El Tiempo | Justicia y tribunales | menos | LDA completo, LDA público | −0,7 a −1,1 pp |
| La República | Geopolítica y guerras | más | LDA público, BERTopic | +1,2 a +1,6 pp |

En justicia, BERTopic da el mismo signo para El Tiempo (−0,95 pp) sin ser
significativo.

Los titulares de ejemplo de BERTopic (`resultados_publico/bertopic/topic_examples.csv`)
son los más cercanos al centroide de embeddings de cada tópico; la columna
`similitud_centroide` es el coseno con el centroide (con θ one-hot el criterio
del LDA, mayor θ, empataba y elegía casi al azar). Con esos ejemplos se
revisaron las etiquetas: cambiaron T3 («Elecciones y campañas»), T4 («Policía y
delitos»: la Policía como actor, ~28 % delitos y ~8 % ataques de grupos
armados), T8 («Mixto: medidas de gobierno, energía y Estados Unidos», una mezcla
que no debe citarse como tema aunque tenga Δ significativos en El Tiempo y La
República) y T10 («Economía colombiana: dólar, salario y renta»). Las cifras no
cambian.

### Reproducir

```bash
./subcorpus_publico.sh                                   # → news-retrieval/exports/subcorpus_publico_ids.csv
bash -c 'P="--output resultados_publico --ids /workspace/news-retrieval/exports/subcorpus_publico_ids.csv --per-cell 14000 --cv-docs 50000"
  ./run.sh prepare $P --heldout-per-cell 500 --ids-label "Asuntos públicos (tesauro en el titular)"
  ./run.sh train $P --topics 10 15 20 25 30
  for e in stability infer examples robustness; do ./run.sh $e $P; done
  ./run.sh compare $P --labels /workspace/entrega3/labels/publico_lda.csv
  for e in ensemble stability infer examples robustness; do ./run.sh $e $P --model ensemble --ensemble-topics 25 --ensemble-eps 0.3; done
  ./run.sh compare $P --model ensemble --ensemble-topics 25 --ensemble-eps 0.3 --labels /workspace/entrega3/labels/publico_ensemble.csv'
docker build -t duque-petro-bertopic:local -f Dockerfile.bertopic .
SCRIPT=bertopic_topics.py IMAGEN=duque-petro-bertopic:local ./run.sh - --output resultados_publico --k 20
bash -c './run.sh compare --output resultados_publico --ids /workspace/news-retrieval/exports/subcorpus_publico_ids.csv --per-cell 14000 --model bertopic --labels /workspace/entrega3/labels/publico_bertopic.csv'
SCRIPT=comparar_metodos.py ./run.sh -
```

Tiempos en 12 núcleos: grilla LDA ≈3 min; cada ensamble ≈4 min; BERTopic ≈1,5 h
la primera vez (embeddings de 313 mil titulares y tres ajustes de UMAP, que se
guardan en caché). En zsh, las listas de argumentos en variables necesitan
`bash -c` (zsh no separa palabras).

## Emparejamiento de titulares entre medios (pasos 1 y 3)

Objetivo: encontrar titulares de **medios distintos sobre el mismo hecho**, para
pasar de comparar agendas (de qué se habla) a comparar encuadres (cómo se
cuenta). Código: `eventos.py`; resultados en `resultados_publico/eventos/`.
**Umbral 0,80, calibrado a mano** (paso 2, sección siguiente): el 81 % de las
parejas que acepta son el mismo hecho (IC 95 % 72–90 %).

### Método

1. **Datos.** Subcorpus de asuntos públicos con fecha al día: 305.295 titulares.
   Se excluyen **1.256 titulares de plantilla masiva**: del mismo medio y el
   mismo día, con 9 o más casi idénticos (similitud ≥ 0,9). 1.236 son de El
   Tiempo, sobre todo las páginas «En vivo elecciones… siga la jornada de
   votación en <municipio>» de las elecciones de 2026, una por municipio. Quedan
   304.039.
2. **Candidatos (paso 1).** Cada titular se compara con todos los titulares de
   **otros** medios publicados en ±2 días, por similitud coseno de los
   embeddings de BERTopic (paraphrase-multilingual-MiniLM-L12-v2). Se calcula un
   producto matricial por día contra la ventana, así que todo el subcorpus tarda
   ~3 s. Se guardan las 898.961 aristas con similitud ≥ 0,60 (`aristas.parquet`,
   no versionado) y, para cada titular, su más parecido en cada medio.
3. **Eventos (paso 3).**
   - **Parejas recíprocas:** A y B se emparejan solo si B es el más parecido a A
     en el medio de B y A es el más parecido a B en el medio de A, con similitud
     ≥ umbral (0,80). Así cada titular tiene como mucho una pareja por medio.
   - **Componentes conexas** de esas parejas.
   - **Contra el encadenamiento** (A~B, B~C… que unen hechos distintos): una
     componente con dos titulares del mismo medio o que dura más de 5 días se
     parte con enlace completo sobre la distancia coseno, de modo que dentro de
     cada parte todos los pares tengan similitud ≥ umbral − 0,10. Se partieron
     1.311 de las 20.408 componentes.
   - **Núcleo:** un titular por medio, el más cercano al centroide del evento.
   - **Seguimiento:** titulares libres de un medio que ya está en el evento, a
     ±2 días y con similitud ≥ umbral con el centroide. Cada uno va a su evento
     más parecido (12.536 titulares).

### Cifras (umbral 0,80)

| | Valor |
|---|---:|
| Precisión medida a mano (paso 2) | 81 % (IC 95 % 72–90 %) |
| Titulares con pareja en otro medio, similitud ≥ 0,70 / 0,75 / 0,80 | 41 % / 30 % / 20 % |
| Con pareja en ≥2 medios (similitud ≥ 0,80) | 7 % |
| Parejas recíprocas ≥ 0,80 | 35.843 |
| Eventos | 20.905 |
| … con 2 / 3 / 4 / 5 medios | 15.038 / 4.127 / 1.398 / 342 |
| Eventos con ≥3 medios (Duque / Petro) | 1.916 / 3.951 |
| Titulares en el núcleo de algún evento / incluido seguimiento | 16,4 % / 20,5 % |
| Evento más grande (núcleo + seguimiento) | 57 titulares |
| Eventos que siguen durando > 5 días tras partir | 12 |

**Sensibilidad al umbral** (`sensibilidad_umbral.csv`, figura 20):

| Umbral | Precisión (paso 2) | Eventos | ≥3 medios | ≥4 medios | 5 medios | % titulares en eventos | Componentes partidas |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,70 | 62 % | 36.836 | 12.895 | 4.108 | 798 | 42,7 % | 4.068 |
| 0,75 | 75 % | 29.068 | 9.169 | 2.871 | 561 | 31,0 % | 2.514 |
| **0,80** | **81 %** | **20.905** | **5.867** | **1.740** | **342** | **20,5 %** | **1.311** |
| 0,85 | 84 % | 13.384 | 3.101 | 843 | 168 | 11,9 % | 504 |
| 0,90 | 93 % | 6.767 | 1.186 | 251 | 36 | 5,4 % | 97 |

La componente conexa más grande, antes de partir, mide 49 titulares entre 0,70
y 0,80. Son las elecciones de Venezuela de julio de 2024: 12 días de notas
parecidas de los cinco medios que se encadenan entre sí. La partición la
divide en sub-eventos.

**Cobertura descriptiva** en eventos con ≥3 medios (`cobertura_eventos.csv`, figura 22):

| Medio | Participa, Duque | Participa, Petro | Publica primero*, Duque | Publica primero*, Petro |
|---|---:|---:|---:|---:|
| El Tiempo | 88 % | 89 % | 24 % | 24 % |
| Blu Radio | 85 % | 80 % | 31 % | 27 % |
| Noticias RCN | 50 % | 69 % | 14 % | 21 % |
| Noticias Caracol | 70 % | 66 % | 21 % | 19 % |
| La República | 35 % | 35 % | 10 % | 10 % |

\* Solo hay fecha al día, así que en un empate el crédito se reparte. En el
68–71 % de los eventos más de un medio publica el primer día. La subida de RCN
se explica, al menos en parte, porque sus titulares de 2018–2020 solo tienen
fecha mensual y quedan fuera del emparejamiento. Ninguna de estas cifras mide
sesgo.

### Ejemplos

| Fecha | Medios | Titulares |
|---|---|---|
| 2020-02-07 | Blu Radio, El Tiempo, La República, RCN | «Fernando Ruiz, **cercano a Vargas Lleras**, es el nuevo ministro de Salud» frente a «Fernando Ruiz Gómez es el nuevo ministro de Salud» |
| 2025-03-05 | Blu Radio, El Tiempo, Caracol, RCN | Mensaje de urgencia de la reforma a la salud: «**Gobierno Petro** radicó…» (Blu Radio) y «…**Gobierno Petro insiste**…» (El Tiempo) frente a «**Armando Benedetti** radicó…» (Caracol) y «**Gobierno** radicó…» (RCN) |
| 2025-09-24/25 | El Tiempo, Caracol, RCN | Sismos en Venezuela: «Así se vivió el fuerte temblor… en varias ciudades» (El Tiempo) frente a «Impactantes videos: los momentos de **pánico**… la gente gritaba» (Caracol) |

Son el mismo hecho con encuadres distintos, que es lo que el análisis siguiente
va a medir. Más ejemplos en `ejemplos_eventos.md`.

### Limitaciones

- **Precisión del 81 %, no del 100 %.** Con el umbral 0,80, cerca de una de
  cada cinco parejas es «mismo tema, otro hecho» o distinta. Para análisis que
  necesiten más pureza se puede filtrar a parejas ≥ 0,90 (93 %), a costa de
  quedarse con un quinto de los eventos.
- **El seguimiento usa el mismo umbral que el núcleo** y a veces pega notas solo
  relacionadas (con 0,75 una nota sobre un video militar de EE. UU. quedó en el
  evento de los sismos en Venezuela, con similitud 0,77). La calibración del
  paso 2 mide las parejas del núcleo, no el seguimiento.
- **Titulares reconstruidos** desde la URL: sin tildes, cifras ni comillas.
- **Solo fecha al día**, sin hora: «quién publica primero» es aproximado. Unos
  8.000 titulares con fecha solo mensual quedan fuera, sobre todo de RCN en
  2018–2020.
- La marca `non_news_reason` no detecta las páginas de plantilla masiva; aquí se
  excluyen, pero convendría marcarlas en el pipeline del corpus.

### Reproducir

```bash
SCRIPT=eventos.py ./run.sh - --output resultados_publico --stage all   # ~1 min; umbral 0,80 por defecto
SCRIPT=eventos.py ./run.sh - --output resultados_publico --stage eventos --umbral 0.90   # otro umbral
```

Requiere `resultados_publico/prepared.parquet` y
`resultados_publico/bertopic/embeddings.npy` (ver la sección de BERTopic).
Figuras 18 a 22 en `resultados_publico/eventos/figuras/`.

## Calibración manual del emparejamiento (paso 2)

Se mide qué tan seguido acierta el emparejamiento y se elige el umbral con datos.
`calibracion.py` toma una muestra de las mismas parejas recíprocas que usa
`eventos.py`, con las mismas plantillas masivas excluidas, y genera las
planillas para el equipo:

- **210 parejas, 30 por tramo de similitud** (0,60–0,65 … 0,90–1,00), salidas de
  20.891 parejas recíprocas de 30.000 titulares al azar. Semilla 42.
- **Dos planillas para trabajar en paralelo:** `planilla_persona_1.xlsx` y
  `planilla_persona_2.xlsx`, de 135 parejas cada una.
  - **60 parejas dobles** están en las dos planillas, para medir el acuerdo entre
    anotadores (kappa de Cohen).
  - Las otras 150 se reparten 75 y 75, equilibradas por tramo.
- **Sin la similitud:** la planilla no la muestra, para no sesgar. Está en
  `clave_no_abrir.csv`, que el equipo no debe abrir.
- **Cuatro respuestas:** «Mismo hecho», «Mismo tema / otro hecho», «Distinto» y
  «No se puede saber». Cada pareja trae enlaces a la nota original.

Instrucciones para el equipo en
[`resultados_publico/calibracion/LEEME.md`](resultados_publico/calibracion/LEEME.md).

```bash
python calibracion.py muestra && python calibracion.py dividir        # regenerar
python calibracion.py evaluar --personas resultados_publico/calibracion/planilla_persona_{1,2}.xlsx
```

`evaluar` devuelve:

- la precisión por tramo, con intervalo de Wilson;
- la precisión de quedarse con las parejas ≥ cada umbral, **ponderada por la
  población**: la muestra tiene 30 parejas por tramo, pero en el corpus los
  tramos bajos tienen más parejas (`poblacion_tramos.csv`). Sin ponderar, la
  precisión se sobrestima (77 % en vez de 75 % para ≥ 0,75). Estimador
  estratificado Σ W_t·p_t, con IC 95 % normal;
- el umbral que alcanza la precisión objetivo (90 % por defecto,
  `--precision-objetivo`);
- la kappa de Cohen en 4 clases y en binario.

### Resultados

Se anotaron las 270 filas de las dos planillas: 207 parejas distintas con
respuesta válida, quitando «No se puede saber».

**Acuerdo entre anotadores (60 parejas dobles):** kappa 0,70 en 4 clases y
**0,77 en «mismo hecho sí/no»**. Es un acuerdo bueno, por encima del mínimo de
0,6, así que el criterio es claro.

| Tramo de similitud | n | «Mismo hecho» | IC 95 % (Wilson) |
|---|---:|---:|---|
| 0,60–0,75 | 88 | 25–27 % | 13–44 % |
| 0,75–0,80 | 30 | 63 % | 46–78 % |
| 0,80–0,85 | 30 | 77 % | 59–88 % |
| 0,85–0,90 | 30 | 77 % | 59–88 % |
| 0,90–1,00 | 29 | 93 % | 78–98 % |

| Umbral | Parejas en el corpus | Precisión ponderada | IC 95 % |
|---|---:|---:|---|
| 0,70 | 73.498 | 62 % | 54–69 % |
| 0,75 | 53.945 | 75 % | 67–83 % |
| **0,80** | **35.843** | **81 %** | **72–90 %** |
| 0,85 | 20.654 | 84 % | 74–94 % |
| 0,90 | 9.198 | 93 % | 82–100 % |

**Decisión: umbral 0,80.** El salto está en 0,75: por debajo, tres de cada
cuatro parejas no son el mismo hecho, casi siempre «mismo tema, otro hecho».
El 0,90 es el único que llega al 90 % de precisión, pero conserva una cuarta
parte de las parejas del 0,80 y pierde justo los titulares del mismo hecho
redactados de forma distinta, que son los que interesan para comparar
encuadres. El 0,80 equilibra las dos cosas y su precisión se reporta.

Texto para el artículo: *«Dos parejas de titulares se consideran el mismo hecho
si son recíprocamente las más parecidas entre sus medios en ±2 días y su
similitud coseno es ≥ 0,80. En una muestra estratificada de 210 parejas anotada
por dos personas (κ = 0,77 sobre 60 parejas dobles), la precisión ponderada a
ese umbral es del 81 % (IC 95 % 72–90 %).»*
