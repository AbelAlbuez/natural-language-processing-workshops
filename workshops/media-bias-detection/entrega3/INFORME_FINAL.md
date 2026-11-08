# Informe final — ¿Cambió la cobertura de cinco medios colombianos entre los gobiernos Duque y Petro?

*8 de noviembre de 2026 · corpus `news_corpus` (dump 2026-10-04, slug procesado 2026-11-04)*

Este informe reúne todo el trabajo de la entrega 3: los tópicos, los eventos
(titulares del mismo hecho), la omisión, la elección léxica, el lenguaje cargado,
la banda 0,65–0,80 y el silver standard de titulares sesgados. Los detalles
técnicos y cómo reproducir cada paso están en el [`README.md`](README.md), y el
resumen corto en el [`RESUMEN_EJECUTIVO.md`](RESUMEN_EJECUTIVO.md). Todas las
cifras salen de los CSV que se citan y todas las rutas son relativas a `entrega3/`.

---

## 1. Pregunta de investigación

**¿Cambió la forma en que El Tiempo, Blu Radio, Noticias RCN, Noticias Caracol y
La República cubren la actualidad entre el gobierno de Iván Duque (2018-08 →
2022-08) y el de Gustavo Petro (2022-08 → 2026-08)?** ¿Algún medio cambió más
que los otros, y en particular trata con más dureza a uno de los dos gobiernos?

La pregunta se responde en tres niveles, de lo más fácil de medir a lo más
difícil:

| Nivel | Pregunta | Método |
|---|---|---|
| **Agenda** | ¿De qué habla cada medio? | Modelos de tópicos (LDA, LDA de consenso, BERTopic) y Δ relativo |
| **Selección** | Ante el mismo hecho, ¿quién lo cubre y quién no? | Eventos entre medios y omisión por tema × gobierno |
| **Encuadre** | Ante el mismo hecho, ¿con qué palabras lo cuenta? | Log-odds léxico, personalización, léxico de carga, silver standard |

Todo es **descriptivo**. Ninguna medida de este informe dice *por qué* un medio
cambió, y una palabra cargada o un tema distinto **no son, por sí solos, sesgo**.
El silver standard (§ 5.7) se armó justamente para medir cuánto se parecen esos
indicadores al juicio humano de sesgo.

## 2. Datos y corpus

- **Fuente:** el corpus `news_corpus`, con las URLs de los sitemaps de cada medio.
  El titular se **reconstruye a partir del slug** de la URL, por lo que no tiene
  tildes, cifras ni puntuación. El proceso está en
  [`news-retrieval/docs/07-tratamiento-del-slug.md`](../news-retrieval/docs/07-tratamiento-del-slug.md).
- **Limpieza:** se marcaron 78.859 piezas que no son noticias, como emisiones,
  loterías, pico y placa, dólar del día, caricaturas o publirreportajes. Se
  asignó un gobierno a cada URL y se guardó con qué precisión se conoce su
  fecha.

| Paso | Titulares |
|---|---:|
| Export 2018-08 → 2026-08 (todos los medios) | 1.716.219 |
| Gobierno Duque o Petro | 1.698.581 |
| 5 medios presentes en los dos gobiernos | 1.653.170 |
| Con titular | 1.650.907 |
| **Noticias** (`non_news_reason IS NULL`) | **1.573.421** |
| Subcorpus de asuntos públicos (política, economía, seguridad, justicia, internacional *en el titular*) | 313.170 |
| Población elegible del silver standard | 290.464 |

Figuras `resultados_publico/figuras/01_embudo_corpus.png`, `02_volumen_mensual.png`
y `15_subcorpus_publico.png`.

**Cuidados que valen para todo el informe:**

- **El volumen no es cobertura.** El número de URLs depende de cómo cada medio
  arma sus sitemaps. Por eso se comparan siempre **proporciones** dentro de cada
  medio, nunca conteos.
- **RCN tiene fecha exacta sólo desde 2020-09.** En las comparaciones por
  eventos, que piden la fecha exacta, el periodo de Duque empieza en 2020-09 y
  hay pruebas de robustez sin RCN.
- **Cambio de archivo en RCN.** La sección deportes pasa de ~1 % a 43–45 % de
  sus URLs, y algo parecido, en sentido contrario, ocurre en El Tiempo y Blu
  Radio. Para que ese cambio no se lea como decisión editorial se agregó un
  **control por sección** (§ 4.1).

## 3. Métodos

### 3.1 Tópicos (agenda)

- **LDA conjunto:** un solo modelo para los dos gobiernos (K = 15), entrenado
  con 400.000 titulares, 40.000 por medio × gobierno, y aplicado a los 1,57 M.
- Sobre el subcorpus de asuntos públicos se ajustaron además un **LDA**, un
  **LDA de consenso** (EnsembleLda) y **BERTopic** (embeddings multilingües,
  UMAP y k-means, K = 20).
- **Δ relativo:** el cambio de Duque a Petro de un medio, menos el cambio
  promedio de los otros cuatro. Así se separa lo propio de cada medio de lo que
  cambió la agenda de todos. Los IC salen de un bootstrap por bloques mensuales,
  con corrección de Holm.
- **Control por sección:** cada medio se repondera para que tenga la misma
  mezcla de sus propias secciones en los dos gobiernos.
- **Robustez:** se repitió cada modelo con otras semillas y se emparejaron los
  tópicos (Jaccard). Sólo se interpretan los tópicos estables.

### 3.2 Eventos: titulares del mismo hecho y calibración

- Dos titulares de medios distintos forman pareja si cada uno es el más parecido
  del otro en ±2 días. El parecido es la similitud coseno de embeddings
  `paraphrase-multilingual-MiniLM-L12-v2`.
- Las parejas se agrupan en **eventos**, y los componentes encadenados se
  parten.
- **Calibración manual del umbral:**
  - dos personas anotaron 210 parejas, estratificadas en 7 tramos de similitud
    (60 dobles);
  - el acuerdo fue κ = 0,77;
  - la precisión se pondera por la población de cada tramo.
- **Umbral elegido: 0,80**, con precisión del 81 % (IC 95 % 72–90 %). El 0,75
  da 75 % y el 0,90 da 93 %.
- **Resultado:** 20.905 eventos, 5.867 con ≥3 medios (1.916 de Duque desde
  2020-09 y 3.951 de Petro) y 342 con los cinco medios.

Archivos: `resultados_publico/eventos/` (figuras 18–22) y
`resultados_publico/calibracion/precision_por_umbral.csv`.

### 3.3 Omisión por tema × gobierno

- **Qué se mide:** para cada evento que cubren al menos 3 de los otros 4 medios,
  si el medio también lo cubre.
- **Por qué con ese denominador:** así ningún medio define qué es noticia.
- La omisión se compara entre temas y gobiernos con el Δ relativo, un bootstrap
  por bloques y las correcciones de Holm y BH.
- **Cota de recall:** entre el 27 % y el 54 % de las «ausencias» podrían ser
  titulares que el emparejamiento no reconoció.

Archivos: `resultados_publico/omision/` (figuras 23–25).

### 3.4 Elección léxica dentro del mismo hecho

- **Palabras distintivas:** log-odds con prior de Dirichlet informativo (Monroe
  et al., 2008), calculado sobre la presencia de cada palabra por titular y
  **emparejado por evento**. Así se compara cómo cuentan los medios el mismo
  hecho.
- **Índice de personalización:** cuántos titulares dicen «Gobierno Petro» o
  «Gobierno Duque» en vez de «el Gobierno».

Archivos: `resultados_publico/lexico/` (figuras 26–29).

### 3.5 Lenguaje cargado

- Se usa el léxico evaluativo curado `lexico_carga.csv`, con polaridad, tipo y
  exclusiones de contexto, validado con concordancias (KWIC) en
  `resultados_publico/carga/validacion_lexico.md`. **No es análisis de
  sentimiento.**
- Se comparan los medios ante el mismo hecho y entre gobiernos, incluida la
  carga en los titulares que mencionan al gobierno.

Archivos: `resultados_publico/carga/` (figuras 30–32).

### 3.6 Banda de similitud 0,65–0,80

- Se repitió el análisis léxico con las parejas de menor similitud.
- Esas parejas se filtraron: misma fecha y un término raro compartido. El filtro
  tiene ≈ 72 % de precisión con validación cruzada anidada.
- Sirve para comprobar que los resultados con ≥ 0,80 no son un artefacto del
  umbral.

Archivos: `resultados_publico/lexico_banda/` (figuras 33–35).

### 3.7 Silver standard de titulares sesgados

- **Muestra:** 300 titulares de asuntos públicos, 30 por medio × gobierno.
- **Estratos:** cada celda mezcla titulares al azar (en evento o sueltos) con
  titulares candidatos:
  - con léxico cargado;
  - con «Gobierno Petro/Duque»;
  - o que más se apartan de los otros medios del evento.
- **Pesos:** para estimar las tasas reales, cada titular pesa N_h / n_h.
- **Anotación a ciegas del medio,** mostrando hasta 4 titulares de otros medios
  sobre el mismo hecho.
- **Esquema de etiquetas:**
  - ¿sesgado? (Sí / No / No se puede saber);
  - si es Sí: tipo, dirección respecto al gobierno de turno e intensidad.
- **Reparto:** dos planillas de 180 titulares con 60 dobles.

**Quién anotó.** La planilla 1 la anotó una persona del equipo. **La planilla 2
la anotó un modelo de lenguaje («Claude (IA)»), no una segunda persona.** Por
eso el silver standard se reporta **por anotador**, más dos combinaciones:

- **laxo:** un desacuerdo cuenta como sesgado;
- **estricto:** un desacuerdo cuenta como no sesgado.

Las tasas se ponderan por estrato, con IC de Wilson y n efectivo de Kish. Las
diferencias usan un bootstrap estratificado.

Código: `silver.py` (muestra, planillas, evaluación) y `silver_analisis.py`
(análisis). Salidas: `resultados_publico/silver/` y
`resultados_publico/silver/analisis/` (figuras 36–38).

## 4. Hallazgos

### 4.1 Agenda (tópicos)

1. **BERTopic es el único modelo estable.**
   - Repite 19 de sus 20 tópicos con otras semillas (Jaccard 0,79).
   - El LDA no lo logra ni con consenso: 0–3 tópicos robustos y Jaccard
     0,19–0,25.
   - Con ~6 palabras útiles por titular, el LDA es demasiado sensible a la
     semilla (`comparacion_metodos.csv`, figura `17_comparacion_metodos.png`).
2. **El control por sección se lleva la mayoría de los cambios.** En el LDA del
   corpus completo, de 13 Δ fiables quedan 5. Fútbol en RCN, por ejemplo, pasa
   de +11,5 a +5,5 pp y deja de ser significativo (figura `16_control_seccion.png`).
3. **Lo que sobrevive con BERTopic y control por sección** (Δ relativo,
   asuntos públicos):
   - Noticias Caracol: **Venezuela, Cuba y Maduro +3,8 pp** (6,6 → 10,0 %) y
     **Policía y delitos −2,8 pp** (17,1 → 10,5 %).
   - El Tiempo: Conflicto y justicia transicional −1,6 pp.
   - La República: Guerras (Israel, Rusia y Ucrania) +1,6 pp.
4. **Tres hallazgos se repiten en varios modelos** (`hallazgos_coincidentes.csv`):
   - El Tiempo cubre más inseguridad urbana y sucesos (3 modelos, +1,1 a
     +1,7 pp).
   - El Tiempo cubre menos justicia y tribunales (2 modelos).
   - La República cubre más guerras y geopolítica (2 modelos).
5. **Con Petro hay más asuntos públicos** en cuatro de los cinco medios: por
   ejemplo, El Tiempo pasa de 15,8 a 21,8 % y Blu Radio de 19,7 a 24,4 %. RCN
   baja levemente.
6. **Las agendas se separan un poco con Petro:** la distancia Jensen-Shannon
   media entre medios sube de 0,180 a 0,204 (figura `13_distancias_js.png`).

### 4.2 Omisión (selección)

- **Los perfiles de cada medio son estables entre gobiernos.**
  - El más marcado es La República, con unos −20 pp en policía, justicia y
    conflicto y más economía.
  - Es un perfil de medio especializado, no una omisión ligada al gobierno.
- **Casi nada cambia de Duque a Petro.**
  - El único cambio robusto es **RCN en Justicia: +7,5 pp** (IC 2,9–12,7)
    frente a los otros medios.
  - Caracol en Venezuela (+14,4 pp) sólo conserva el signo en las pruebas de
    robustez.
- **Participación de RCN:** con fecha exacta (Duque desde 2020-09) está en
  eventos el 47 % de las veces, frente al 48 % con Petro.
- La cota de recall (27–54 %) obliga a leer la omisión como **cota superior**.

Archivos: `omision/LEEME.md`, figuras 23–25.

### 4.3 Elección léxica (encuadre)

- **Las palabras distintivas de cada medio son sobre todo de estilo de casa:**
  El Tiempo usa nombres completos y Blu Radio formas cortas.
- **El hallazgo más claro es de periodo, no de medio: todos personalizan más al
  gobierno con Petro.**

  | Medio | «Gobierno Petro/Duque» con Duque | Con Petro |
  |---|---:|---:|
  | El Tiempo | 5,1 % | 26,9 % |
  | Noticias Caracol | 7,6 % | 28,4 % |
  | Blu Radio | 5,4 % | 17,0 % |
  | Noticias RCN | 3,9 % | 12,1 % |
  | La República | 6,6 % | 10,7 % (no significativo) |

- **Comparación emparejada dentro de Petro, en los mismos hechos:**
  - El Tiempo +11,2 pp sobre los otros medios;
  - RCN −12,7, La República −7,9 y Blu Radio −5,1.
- **Con Duque ningún medio se distingue.**

Archivos: `lexico/LEEME.md`, `lexico/ejemplos_lexico.md`, figuras 26–29.

### 4.4 Lenguaje cargado

- **Ante el mismo hecho, las diferencias entre medios son de 3 pp como mucho:**
  - Caracol usa más carga negativa con Duque (+2,4 pp);
  - La República usa menos con Petro (−3,1 pp);
  - Blu Radio usa unos +12 pp más de verbos de atribución cargados
    («arremete», «denuncia»), en los dos gobiernos.
- **En los titulares sobre el gobierno ningún medio usa más carga que los
  otros en el mismo hecho.**
- **La carga negativa en esos titulares sube en conjunto de 5,2 % a 9,7 % con
  Petro,** igual en todos los medios.

Archivos: `carga/LEEME.md`, figuras 30–32.

### 4.5 Banda 0,65–0,80

- **No aparece encuadre nuevo,** y la personalización se mantiene (El Tiempo
  +15,2 pp).
- Los resultados con ≥ 0,80 **no son un artefacto del umbral**.

Archivos: `lexico_banda/LEEME.md`, figuras 33–35.

### 4.6 Silver standard: cuánto sesgo ve un anotador y qué tan de acuerdo están

Archivos: `silver/evaluacion.json` y `silver/analisis/`, figuras 36–38.

**a) El acuerdo es bajo y tiene una estructura clara.**

- El κ entre la persona y la IA es **0,30** en sesgado sí/no.
- En tipo de sesgo es −0,04 y en dirección −0,01: **ninguno de los dos se
  puede usar como etiqueta**.
- En los 60 dobles, la persona marcó sesgo en 32 y la IA en 10. **Los 10 de la
  IA están entre los 32 de la persona:** la IA nunca dijo «Sí» donde la persona
  dijo «No».
- **Es un umbral distinto, no ruido.** La IA aplica la guía al pie de la letra
  (una opinión atribuida a su fuente no es sesgo; «polémica» o «histórico» solos
  tampoco). La persona marca además titulares con citas fuertes o con
  sustantivos como «escándalo» o «polémica».
- **Consecuencia:** a nivel de titular, la frontera entre sesgo y no sesgo
  depende mucho de quién anota.

**b) Prevalencia ponderada a la población** (`tasas_por_definicion.csv`):

| Anotador | Duque | Petro | Ambos |
|---|---:|---:|---:|
| Persona | 39 % (24–56) | 21 % (11–38) | ≈ 30 % |
| IA | 14 % (6–29) | 12 % (5–26) | ≈ 12 % |
| Combinado laxo | 28 % (18–41) | 17 % (10–29) | — |

**Con ninguna de las dos etiquetas hay más sesgo con Petro.** La persona ve
menos con Petro, pero la diferencia de −16 pp no es significativa (IC −40 a
+11). La IA ve lo mismo en los dos gobiernos (+3 pp, IC −11 a +22).

**c) Por medio:**

- **Ninguna diferencia Petro − Duque por medio es significativa** con la
  etiqueta de la persona, con la de la IA ni con la combinada
  (`diferencias_petro_duque.csv`). Hay unos 18 titulares por celda y
  anotador, así que los IC son de ±30–50 pp.
- **Caracol es el medio con más titulares sesgados según la IA:** 41 % (21–64),
  frente al 1–13 % de los demás; con Blu Radio sus IC no se solapan, y con RCN
  y La República apenas se tocan. En la etiqueta combinada laxa también es el primero, con 38 %
  (22–57). Según la persona, en cambio, queda en el medio (29 %), detrás de
  El Tiempo (42 %).
- **Hay una señal débil en La República:** el sesgo *desfavorable al gobierno*
  baja con Petro.
  - Persona: −25 pp (IC −69 a 0; p bootstrap = 0,05).
  - Combinado laxo: −14,5 pp (IC −40 a 0; p = 0,05).
  - Queda en el límite de la significación y no resiste la corrección por más
    de 20 comparaciones, así que se lee como **indicio**.

**d) Dirección y tipo:**

- **Dirección, según la persona:** entre los titulares sesgados, el ~77–79 % es
  desfavorable al gobierno de turno **en los dos gobiernos**, sin asimetría.
- **Dirección, según la IA:** con Duque casi todo su sesgo es «neutro»
  (sensacionalismo sobre crímenes), y con Petro el 81 % es desfavorable. Son
  sólo 15 titulares por gobierno y el κ de dirección es ≈ 0, así que **no se
  interpreta**.
- **Tipo:** los dos anotadores ven que con Petro el sesgo es más
  **sensacionalismo** y menos **lenguaje cargado**.
  - Persona: de 4 % a 36 % de los sesgados.
  - IA: de 29 % a 84 %.
  - Con un κ de tipo ≈ 0, es una coincidencia sugerente, no un resultado.

**e) ¿Sirven los indicadores automáticos?** (`validacion_indicadores.csv`,
`entradas_lexico_vs_etiqueta.csv`, figura 38)

| Indicador | Precisión (persona) | Precisión (IA) | Cobertura | Lectura |
|---|---:|---:|---:|---|
| Léxico de `carga.py`, cualquier entrada | 40 % (prev. 30 %) | 23 % (prev. 12 %) | 12–14 % | Enriquece ×1,3–1,9, pero deja fuera a ~85 % de los sesgados |
| Léxico negativo | 35 % | 34 % | 9–14 % | Similar |
| Verbos de atribución cargados | 11 % | 10 % | ≤ 2 % | **Peor que el azar** |
| «Gobierno Petro/Duque» | 7 de 14 | **1 de 13** | ≤ 3 % | **No es indicador de sesgo** |
| Titular divergente del evento | 42 % | 11 % | 3–4 % | Débil |

- **Los estratos candidatos sí sirven para muestrear:**
  - según la persona, el 65–69 % de los titulares con léxico están sesgados,
    frente al 28 % de los demás;
  - según la IA, 25–29 % frente a 6–14 %.
- **Cada entrada del léxico se juzga distinto según el anotador:**
  - «polémica»: 8 de 9 sesgados para la persona y 0 de 7 para la IA;
  - «histórico»: 2 de 3 y 0 de 8;
  - «escándalo»: 9 de 17 y 4 de 17.

**f) Clasificador de prueba de concepto** (TF-IDF de palabras y caracteres más
regresión logística; validación cruzada 5 × 10; `silver_analisis.json`):

- AUC 0,62 ± 0,09 con la etiqueta de la persona, 0,56 ± 0,09 con la de la IA y
  0,60 ± 0,06 con la combinada.
- Con **180–300 titulares no supera a una sola marca del léxico** (AUC
  0,62–0,66).
- No hay señal que aprender más allá de las palabras cargadas: **no se
  recomienda usarlo**.

### 4.7 ¿El silver standard confirma o contradice los análisis anteriores?

| Análisis anterior | Qué dice el silver standard | Veredicto |
|---|---|---|
| Carga negativa sube de 5 % a 10 % con Petro, en todos los medios | El sesgo juzgado **no sube**: baja según la persona (39 → 21 %) y queda igual según la IA | **Contradice la lectura como sesgo:** hay más palabras cargadas, pero no más titulares juzgados sesgados. Carga ≠ sesgo |
| Personalización «Gobierno Petro» sube en todos los medios | La IA casi nunca la juzga sesgo (1 de 13) y la persona la mitad de las veces | **Confirma que es estilo o periodo,** no un indicador de sesgo |
| Blu Radio usa más verbos de atribución cargados | Esos verbos tienen precisión ≈ 10 %, por debajo de la prevalencia | **Confirma que es estilo de casa** |
| Caracol usa más carga negativa con Duque (+2,4 pp) | Caracol tiene la tasa más alta según la IA y la combinada, sobre todo con Duque (44–48 %) | **Consistente,** débil y dependiente del anotador |
| La República usa menos carga con Petro (−3,1 pp) | El sesgo desfavorable de La República baja con Petro (indicio en el límite, p = 0,05, sin corrección múltiple) | **Consistente,** débil |
| Tópicos (BERTopic) y omisión | El silver standard mide encuadre del titular, no agenda ni selección | No aplica |
| Banda 0,65–0,80 sin encuadre nuevo | Ninguna diferencia de sesgo por medio es significativa | **Consistente:** no aparece un medio que cambie de encuadre |

## 5. Qué NO se encontró

- **Ningún medio trata de forma robusta más desfavorablemente a un gobierno que
  al otro** cuando se compara con los otros medios ante los mismos hechos. No
  aparece ni en la carga dirigida al gobierno (§ 4.4) ni en el sesgo juzgado
  (§ 4.6).
- **No hay un aumento general del sesgo juzgado con Petro,** aunque sí aumentan
  la carga negativa y la personalización en todos los medios.
- **No hay omisiones selectivas que cambien con el gobierno,** salvo RCN en
  Justicia.
- **No hay encuadre nuevo** en las parejas de menor similitud.
- El LDA **no da tópicos estables**, ni con consenso.

## 6. Limitaciones

1. **El segundo anotador del silver standard es un modelo de lenguaje.** El κ
   entre persona e IA (0,30) mide el acuerdo humano–modelo, no el acuerdo entre
   personas.
   - Las tasas por anotador vienen de **una sola persona** y de **un solo
     modelo**.
   - Los 32 desacuerdos en dobles siguen **sin adjudicar** (`silver/adjudicacion.xlsx`).
   - Los análisis usan las etiquetas por anotador y las dos combinaciones
     extremas, que sirven de cota.
2. **Muestras chicas por celda.** Son ~18 titulares por medio × gobierno y
   anotador, con un n efectivo de Kish de ~10 por los pesos de estrato: los IC
   por medio son muy anchos.
3. **Tipo y dirección del sesgo no son fiables** (κ ≈ 0). Además, la persona
   parece haber usado «desfavorable» respecto al actor del titular y no siempre
   respecto al gobierno de turno.
4. **Titulares reconstruidos desde la URL:** sin tildes, cifras ni puntuación,
   lo que quita señales como las comillas o los signos de interrogación.
5. **El emparejamiento acierta en ~81 % de los casos** y su recall no está
   medido. La omisión es una cota superior, y el contexto que se mostró en el
   silver standard es a veces de otro hecho.
6. **RCN con fecha exacta sólo desde 2020-09:** las comparaciones por eventos
   cubren 2020-09 → 2022-08 para Duque.
7. **El volumen depende de los sitemaps:** por eso todo se trabaja en
   proporciones, con control por sección.
8. **Carga ≠ sesgo y tópico ≠ encuadre.** Los indicadores léxicos son
   descriptivos, y el silver standard muestra que se parecen poco al juicio de
   sesgo.

## 7. Conclusión

Con 1,57 millones de titulares y tres niveles de análisis, **las diferencias
entre los cinco medios son pequeñas y sobre todo de perfil y estilo.** La
República se especializa en economía, El Tiempo usa nombres completos y Blu
Radio, verbos de atribución vivos. Esos perfiles se mantienen de un gobierno al
otro.

**Lo que cambia con Petro es común a todos los medios:**

- más asuntos públicos;
- más personalización del gobierno («Gobierno Petro»);
- más carga negativa en los titulares sobre el gobierno.

Al ser un cambio compartido, encaja mejor con un **cambio del periodo** (otro
estilo de gobierno, otra agenda, otra forma de nombrarlo) que con una decisión
editorial de un medio en particular.

**Los cambios propios de cada medio son pocos y modestos:**

- Caracol, más Venezuela y menos policía en la agenda;
- RCN, más justicia en los hechos que cubre;
- El Tiempo, más personalización del gobierno de Petro que los otros en los
  mismos hechos.

Ninguno equivale a un trato sistemáticamente más duro con uno de los dos
gobiernos.

El silver standard deja una lección de método: **la carga léxica no equivale a
sesgo juzgado.** Las palabras cargadas aumentan con Petro y el sesgo juzgado
no, y que un titular se considere sesgado depende mucho del umbral de quien
anota (κ 0,30). Cualquier afirmación sobre «sesgo» de un medio a partir de
indicadores automáticos de titulares debería tomarse con mucha cautela.

## 8. Trabajo futuro

1. **Una segunda persona** anota la planilla 2 (o adjudica los 32 desacuerdos)
   y se recalcula el κ entre humanos. Comando:
   `SCRIPT=silver.py ./run.sh - evaluar --adjudicacion resultados_publico/silver/adjudicacion.xlsx`.
2. **Guía más precisa** para «dirección» y para citas atribuidas, y un silver
   standard **centrado en titulares sobre el gobierno**, donde la pregunta de
   dirección tiene sentido. Con ~100 por celda los IC por medio bajarían a
   ±10–15 pp.
3. **Medir el recall del emparejamiento,** anotando ausencias, para acotar mejor
   la omisión.
4. **Extender BERTopic al corpus completo** y validar sus tópicos con el equipo
   (prueba de intrusión de palabras).
5. **Usar el titular publicado o el texto completo** en una submuestra, con
   tildes, cifras y comillas, para la atribución y el encuadre.

## Anexo: mapa de archivos

| Tema | Carpeta | Figuras |
|---|---|---|
| Corpus, LDA, control por sección, comparación de modelos | `resultados/`, `resultados_publico/` (más `ensemble/` y `bertopic/`) | 01–17 |
| Eventos y calibración | `resultados_publico/eventos/`, `resultados_publico/calibracion/` | 18–22 |
| Omisión | `resultados_publico/omision/` | 23–25 |
| Elección léxica | `resultados_publico/lexico/` | 26–29 |
| Lenguaje cargado | `resultados_publico/carga/` | 30–32 |
| Banda 0,65–0,80 | `resultados_publico/lexico_banda/` | 33–35 |
| Silver standard | `resultados_publico/silver/`, `resultados_publico/silver/analisis/` | 36–38 |
