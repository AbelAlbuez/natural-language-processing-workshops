# Entrega 3 — LDA conjunto Duque + Petro

Modelo de tópicos (LDA) entrenado una sola vez sobre los dos gobiernos, para que
los tópicos sean los mismos al comparar **medios dentro de un gobierno** y **cada
medio entre gobiernos**. El LDA no identifica temas en sentido estricto: muestra
qué palabras tienden a aparecer juntas en los titulares. Las etiquetas son una
interpretación humana (`topic_labels.csv`).

Resumen de resultados para el equipo: [`RESUMEN_EJECUTIVO.md`](RESUMEN_EJECUTIVO.md).

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
> y corrección de Holm. De los 75 pares medio–tópico, 14 muestran un Δ relativo
> significativo en tópicos robustos o parciales que conserva el signo con las
> tres semillas.
