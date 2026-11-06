# Resumen ejecutivo — Agenda de cinco medios bajo Duque y Petro

*6 de noviembre de 2026 · corpus `news_corpus` (dump 2026-10-04, slug procesado 2026-11-04)*

## Qué se hizo

1. **Se limpió el corpus** con el enfoque de slug: 1,73 M de URLs con titular
   reconstruido y sección, y 78.859 piezas que no son noticias marcadas
   (emisiones, loterías, pico y placa, dólar del día, caricaturas, publirreportajes).
   Detalle en `news-retrieval/docs/07-tratamiento-del-slug.md`.
2. **LDA sobre el corpus completo**: un único modelo para los dos gobiernos
   (K = 15), entrenado con 400.000 titulares balanceados y aplicado a las
   **1.573.421 noticias** de El Tiempo, Blu Radio, Noticias RCN, Noticias Caracol
   y La República.
3. **Mejoras**: un **subcorpus de asuntos públicos** (313.170 titulares con una
   etiqueta del tesauro de política, economía, seguridad, justicia o relaciones
   internacionales *en el titular*), un **control por sección** (cada medio se
   repondera para tener la misma mezcla de sus propias secciones en los dos
   gobiernos) y dos modelos alternativos sobre el subcorpus: **LDA de consenso**
   (EnsembleLda) y **BERTopic** (embeddings multilingües + UMAP + k-means).
4. **Se comparó la agenda** con el Δ relativo: cambio de Duque a Petro de un
   medio menos el cambio promedio de los otros cuatro, con IC por bootstrap de
   bloques mensuales y corrección de Holm.

## Resultados principales

**1. BERTopic es el único modelo estable; el LDA no lo es ni con consenso.**

| Modelo | K | c_v | Jaccard entre semillas | Tópicos robustos | Δ fiables sin / con control* |
|---|---:|---:|---:|---:|---:|
| LDA · corpus completo | 15 | 0,417 | 0,25 | 3 (20 %) | 13 / 5 de 75 |
| LDA · asuntos públicos | 25 | 0,360 | 0,19 | 1 (4 %) | 7 / 2 de 125 |
| LDA de consenso · asuntos públicos | 12 | 0,319 | 0,22 | 0 | 2 / 1 de 60 |
| **BERTopic · asuntos públicos** | 20 | 0,398 | **0,79** | **19 (95 %)** | **22 / 10 de 100** |

\* Holm < 0,05, tópico no inestable y mismo signo con las otras dos semillas
(`resultados_publico/comparacion_metodos.csv`, figura `17_comparacion_metodos.png`).

Con ~6 palabras útiles por titular, el LDA no reproduce sus tópicos al cambiar
la semilla; el consenso de 16 modelos tampoco, porque cada ensamble converge a
otro consenso. BERTopic repite 19 de sus 20 tópicos con otras semillas y su Δ
relativo se correlaciona 0,95 entre semillas: **es el modelo a usar en adelante.**

**2. El control por sección se lleva la mayoría de los cambios.** En el LDA del
corpus completo, de 13 cambios fiables quedan 5 al controlar por sección. Los más
llamativos desaparecen: Fútbol en RCN (+11,5 → +5,5 pp, no significativo),
Conflicto armado en Blu Radio (+2,5 → +1,0) y Gobierno en RCN (−2,9 → −1,0).
Eran sobre todo cambios en cuánto pesa cada sección en el archivo del medio, no
en qué cubre dentro de cada sección.

**3. Lo que sobrevive con BERTopic y control por sección** (asuntos públicos):

| Medio | Tópico | Duque → Petro | Δ relativo | Con control |
|---|---|---|---:|---:|
| Noticias Caracol | Venezuela, Cuba y Maduro | 6,6 % → 10,0 % | +4,8 pp | **+3,8 pp** |
| El Tiempo | Mixto: medidas de gobierno, energía y Estados Unidos† | 4,7 % → 6,8 % | +2,8 pp | +2,9 pp |
| Noticias Caracol | Policía y delitos | 17,1 % → 10,5 % | −5,8 pp | **−2,8 pp** |
| La República | Mixto: medidas de gobierno, energía y Estados Unidos† | 11,0 % → 9,0 % | −2,5 pp | −2,3 pp |
| El Tiempo | Policía y delitos | 7,7 % → 7,2 % | +2,2 pp | +1,7 pp |
| El Tiempo | Conflicto, víctimas y justicia transicional | 12,8 % → 9,3 % | −1,3 pp | −1,6 pp |
| La República | Guerras: Israel, Rusia y Ucrania | 1,8 % → 3,7 % | +1,7 pp | +1,6 pp |
| Noticias Caracol | Narcotráfico | 2,7 % → 1,7 % | −1,1 pp | −0,9 pp |
| El Tiempo | Narcotráfico | 2,6 % → 2,9 % | +0,6 pp | +0,5 pp |
| Noticias Caracol | Vacunación contra el COVID | 0,7 % → 0,1 % | +0,3 pp | +0,4 pp |

Los porcentajes son la participación del tópico dentro del subcorpus de cada
medio y gobierno. El Δ relativo puede tener otro signo que el cambio absoluto:
la policía baja en El Tiempo (7,7 → 7,2 %), pero baja mucho más en los demás.

† **No citar como tema.** Revisado con los titulares más cercanos a su centroide,
es una mezcla: el 27 % de sus titulares menciona Estados Unidos (incluidas notas
de estilo de vida) y el resto son anuncios de gobiernos, energía e impuestos.
«Policía y delitos» trata a la Policía como actor: delitos (~28 % de sus
titulares), uniformados asesinados o heridos y abusos de agentes; ~8 % son
ataques de grupos armados.

**4. Tres hallazgos se repiten en varios modelos** (Δ con control por sección,
significativo y del mismo signo; `resultados_publico/hallazgos_coincidentes.csv`):

- **El Tiempo cubre más inseguridad urbana y sucesos** que los demás con Petro:
  3 modelos (LDA del corpus completo, consenso y BERTopic), +1,1 a +1,7 pp.
- **El Tiempo cubre menos justicia y tribunales**: 2 modelos (los dos LDA),
  −0,7 a −1,1 pp; BERTopic da el mismo signo (−1,0 pp) sin llegar a ser significativo.
- **La República cubre más guerras y geopolítica**: 2 modelos (LDA del subcorpus y
  BERTopic), +1,2 a +1,6 pp.

**5. Con Petro hay más asuntos públicos en cuatro de los cinco medios.** Su peso
en las noticias sube en El Tiempo (15,8 → 21,8 %), Blu Radio (19,7 → 24,4 %),
Caracol (16,6 → 20,2 %) y La República (17,9 → 20,8 %); en RCN baja levemente
(20,2 → 19,3 %) (figura `resultados_publico/figuras/15_subcorpus_publico.png`).

**6. Las agendas se separan un poco con Petro** (LDA del corpus completo): la
distancia media entre los cinco medios pasa de 0,180 a 0,204 (Jensen-Shannon) y
RCN es el que más cambia respecto a sí mismo (0,139).

## Cautelas antes de citar estos resultados

- **Agenda no es framing.** Los tópicos dicen *de qué* se habla, no *cómo*.
  Ningún resultado de este análisis mide sesgo por sí solo.
- **El control por sección también descuenta cambios reales**: si un medio
  decidió dar más espacio a una sección, ese cambio editorial desaparece del Δ
  controlado. Las dos cifras se reportan juntas por eso.
- **BERTopic asigna un tópico por titular** (k-means): las participaciones son
  conteos de titulares, no promedios de distribuciones como en el LDA.
- **Los titulares son reconstruidos** desde la URL (sin tildes, cifras ni
  puntuación) y en RCN 2018–2020 sólo se conoce el mes de publicación.

## Siguientes pasos recomendados

1. **Emparejar titulares del mismo hecho entre medios**, reutilizando los
   embeddings de BERTopic (`resultados_publico/bertopic/embeddings.npy`) con una
   ventana de ±2 días. Es la base para pasar de agenda a encuadre.
2. Sobre esos eventos: **cobertura u omisión** de cada medio y **elección
   léxica** (*log-odds* con prior informativo) dentro del mismo hecho.
3. **Validar los tópicos de BERTopic con el equipo** (prueba de intrusión de
   palabras) y revisar los dos tópicos mixtos antes de citarlos.
4. Extender BERTopic al **corpus completo** para comparar con el LDA K = 15.

## Dónde está todo

- Código y cómo reproducir: [`README.md`](README.md)
- Comparación de métodos: `resultados_publico/comparacion_metodos.csv`,
  `hallazgos_coincidentes.csv` y `figuras/17_comparacion_metodos.png`
- Por modelo (`resultados/`, `resultados_publico/`, `…/ensemble/`, `…/bertopic/`):
  `deltas.csv` (con columnas `secc_*` del control por sección), `topic_robustness.csv`,
  `participacion_medio_gobierno.csv` y `figuras/` (la central es `12_delta_relativo.png`;
  el efecto del control, `16_control_seccion.png`)
