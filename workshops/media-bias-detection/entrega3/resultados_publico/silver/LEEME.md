# Silver standard de titulares sesgados

Responde a la sugerencia del profesor en la entrega anterior: un conjunto de
titulares etiquetados a mano como «sesgado / no sesgado», con el tipo de sesgo y
su dirección respecto al gobierno de turno. Sigue el mismo proceso que la
calibración del emparejamiento (`../calibracion/`): una muestra, dos planillas
para anotar en paralelo con titulares dobles para medir el acuerdo, y una etapa
de evaluación. Código: `silver.py`; tests: `tests/test_silver.py`.

## Para el equipo: cómo anotar

Hay una planilla por persona:

- `planilla_silver_persona_1.xlsx`: 180 titulares.
- `planilla_silver_persona_2.xlsx`: 180 titulares.

1. Cada persona abre **su** planilla. La hoja **Instrucciones** trae las
   definiciones, una guía de decisión y un ejemplo anotado. Léanla entera
   antes de empezar (5–10 min) y, si pueden, anoten juntos 5 titulares inventados
   o del ejemplo para alinear el criterio. **No** usen titulares de la muestra.
2. En la hoja **Anotación**, para cada titular (celdas amarillas):
   - **¿sesgado?**: «Sí» / «No» / «No se puede saber».
   - Si es «Sí»: **tipo principal**, **dirección** respecto al gobierno de turno
     e **intensidad** (1 leve, 2 moderada, 3 fuerte). Si no, se dejan vacías.
   - **comentario** libre (opcional; útil en los casos dudosos).
   - La columna **control** avisa si falta o sobra algo.
3. La columna **otros medios sobre el mismo hecho** muestra cómo titularon
   el mismo hecho otros medios (cuando el titular está en un evento). No es la
   verdad: sirve para ver qué otras formas había de contarlo. Dos de cada cinco
   titulares no tienen otros medios; se juzgan solos. **Ojo:** el emparejamiento
   acierta en ~4 de cada 5 casos, así que a veces el contexto es otro hecho
   (p. ej. «Lula arremete contra Trump» con «Petro contra Trump» como contexto).
   En ese caso, ignoren el contexto y juzguen el titular solo.
4. **No comparen respuestas mientras anotan.** Los **60 titulares dobles**
   (filas azules, `doble = Sí`) están en las dos planillas a propósito.
5. **No abran `clave_no_abrir.csv` ni `poblacion_estratos.csv`**: dicen el medio,
   la URL y por qué se eligió cada titular. Tampoco busquen el titular en
   internet: la anotación es a ciegas del medio.
6. La hoja **Progreso** muestra cuánto falta y cuántas filas tienen avisos.

**Tiempo estimado**: ~40 s por titular (hay que leer también el contexto), unas
**2 horas por persona**. Mejor en dos sesiones de una hora: el criterio se
degrada con el cansancio.

### Opciones (resumen; la definición completa está en la planilla)

| Tipo | Qué es |
|---|---|
| Lenguaje cargado | Palabras valorativas o estigmatizantes sobre un actor o un hecho cuando hay una forma neutra («se despachó contra» frente a «criticó») |
| Opinión como hecho | Valoración o predicción afirmada sin fuente («La reforma acabará con…») |
| Atribución selectiva | Voz a una sola parte en un asunto disputado; verbos que juzgan la credibilidad («admitió», «confesó» frente a «dijo») |
| Sensacionalismo | Exagera la gravedad, la novedad o la emoción («caos total», «terremoto político») |
| Encuadre parcial / omisión de contexto | Destaca un aspecto y omite un dato central que los otros medios sí ponen |
| Otro | Ironía, sarcasmo u otro; explicar en el comentario |

Dirección: **Favorable** (deja mejor parado al gobierno de turno o peor a quien
se le opone en ese asunto), **Desfavorable** o **Neutra / no aplica** (el sesgo
no toca al gobierno: p. ej. sensacionalismo sobre un crimen). Reglas clave:
se juzga **cómo se cuenta**, no si el hecho es bueno o malo para el gobierno; el
estilo o formato (preguntas, «en vivo», «Gobierno Petro» frente a «el Gobierno»)
no es sesgo por sí solo.

## Después de anotar

Guarden las dos planillas llenas en esta carpeta (mismo nombre) y corran, desde
`entrega3/`:

```bash
SCRIPT=silver.py ./run.sh - evaluar      # lee planilla_silver_persona_{1,2}.xlsx de esta carpeta
SCRIPT=silver.py ./run.sh - adjudicar    # adjudicacion.xlsx con los desacuerdos de las dobles
# llenen adjudicacion.xlsx juntos (o una tercera persona) y vuelvan a evaluar:
SCRIPT=silver.py ./run.sh - evaluar --adjudicacion resultados_publico/silver/adjudicacion.xlsx
```

`evaluar` genera:

- `evaluacion.json`: kappa de Cohen en las dobles: sesgado en 3 clases, binario
  («Sí» frente al resto) y «Sí/No» sin «No se puede saber»; tipo y dirección
  (sobre las dobles en que las dos dijeron «Sí»); intensidad con kappa ponderada
  cuadrática. También los conteos de cada etiqueta y los pendientes.
- `acuerdo_por_categoria.csv`: acuerdo específico por categoría,
  2·n(ambas) / (n(persona 1) + n(persona 2)). Muestra qué categorías se
  confunden (p. ej. «Lenguaje cargado» frente a «Sensacionalismo»).
- `tasa_sesgo_medio_gobierno.csv`: proporción de «Sí» por medio × gobierno, por
  medio y por gobierno, **sin ponderar y ponderada por estrato**, con IC 95 % de
  Wilson calculado con el n efectivo de Kish.
- `tasa_por_estrato.csv`: proporción de «Sí» en cada estrato y entre los
  titulares que cumplen cada criterio de candidato (léxico, «Gobierno
  Petro/Duque», divergente). Dice cuánto sirvió el enriquecimiento.
- `silver_standard.csv`: la etiqueta consolidada de cada titular, con medio, URL,
  estrato, peso y la fuente de la etiqueta.

Un kappa binario por debajo de ~0,6 querría decir que las definiciones no son lo
bastante claras: conviene revisarlas (con los comentarios y
`acuerdo_por_categoria.csv`) antes de usar las etiquetas.

### Regla de consolidación

| Caso | Etiqueta | `fuente` |
|---|---|---|
| Titular simple (una persona) | La de esa persona | `una persona` |
| Doble, coinciden en ¿sesgado? (y, si es «Sí», en tipo y dirección) | La común; intensidad = media de las dos | `acuerdo de dos` |
| Doble, no coinciden en ¿sesgado? | «Pendiente» (fuera de las tasas) hasta adjudicar | `desacuerdo` |
| Doble, las dos «Sí» pero distinto tipo o dirección | «Sí» se mantiene; tipo o dirección «Pendiente» | `desacuerdo` |
| Después de adjudicar | La decisión de la hoja «Adjudicación» | `adjudicado` |

En la adjudicación se discute cada desacuerdo con las mismas definiciones;
las respuestas aparecen como «A» y «B», en orden aleatorio, sin decir de quién
son, y siguen sin medio ni URL. Si tras discutir no hay acuerdo, se elige «No se
puede saber». «No se puede saber» queda fuera del denominador de las tasas y se
cuenta aparte.

## Diseño (para el artículo)

### Unidad y contexto

La unidad es el **titular**. Cuando el titular pertenece a un evento de
`eventos.py` (umbral calibrado 0,80, precisión 81 %), se muestran los titulares
núcleo de los otros medios sobre el mismo hecho (hasta 4, en orden aleatorio).
Juzgar el sesgo por comparación con otras formas de contar el mismo hecho es más
fiable que juzgar un titular aislado, y es coherente con el resto del proyecto
(léxico y omisión emparejados por evento). Sin embargo, sólo el 20 % de los
titulares está en algún evento, y esos titulares no son representativos: el
emparejamiento favorece titulares redactados de forma parecida. Por eso la
muestra incluye también **titulares sin evento** (120 de 300), que se juzgan
solos: sin ellos no se podría hablar de la tasa de sesgo de un medio.

### Población

Subcorpus de asuntos públicos (`prepared.parquet`, 313.170 titulares), con
estas exclusiones, en orden (`muestra.json`):

| Motivo | Titulares |
|---|---:|
| Noticias RCN en el gobierno Duque antes de 2020-09 (sin fecha al día; misma decisión que `../lexico/LEEME.md`) | 6.095 |
| Tópico 14 de BERTopic (fútbol residual) | 8.351 |
| Opinión, columnas, editoriales y humor (sección o marca en el titular): la opinión declarada no es sesgo informativo | 5.136 |
| El titular menciona un medio (ver «Ceguera») | 915 |
| Menos de 5 palabras | 1.244 |
| Duplicado exacto dentro del mismo medio | 965 |
| **Población elegible** | **290.464** |

### Muestreo estratificado y enriquecido

Un muestreo al azar daría pocos positivos y poco útiles para entrenar. La
muestra se estratifica en dos niveles:

1. **Celda medio × gobierno** (10 celdas), con el mismo tamaño en todas: 30
   titulares. Así cada medio y gobierno tiene casos suficientes para compararse,
   aunque El Tiempo–Petro tenga 10 veces más titulares que RCN–Duque.
2. **Estrato** dentro de la celda, excluyentes, con esta prioridad:

| Estrato | Criterio | Por celda | Población total |
|---|---|---:|---:|
| `E_lexico` | en evento y con léxico candidato | 7 | 2.299 (0,8 %) |
| `E_divergente` | en evento, sin léxico, y es de los titulares que más se apartan de los otros medios del evento (15 % con menor similitud coseno al centroide de los titulares de los otros medios, por celda) | 5 | 8.646 (3,0 %) |
| `E_resto` | en evento, el resto (al azar) | 6 | 49.068 (16,9 %) |
| `S_lexico` | sin evento y con léxico candidato | 5 | 10.593 (3,6 %) |
| `S_resto` | sin evento, el resto (al azar) | 7 | 219.858 (75,7 %) |

**Léxico candidato** = el titular contiene un término de la lista `CARGA` de
`silver.py` (111 formas en cuatro grupos: descalificación, estigmatización,
dramatización y exaltación; p. ej. «fracaso», «papelón», «castrochavismo»,
«escándalo», «se despachó», «arremete», «histórico», «espaldarazo») **o** la
personalización «Gobierno Petro/Duque», detectada con la misma expresión regular
que `lexico.formas_nombrar`. Se descartan usos neutros conocidos («Pacto
Histórico», «ataque terrorista», «máximo histórico»). La lista es deliberadamente
breve y se armó sin mirar etiquetas; sólo sirve para enriquecer el muestreo, no
como clasificador. Se puede armonizar después con `lexico_carga.yaml` (lo
construye otro módulo en paralelo); la clave guarda los términos encontrados en
cada titular (`terminos_carga`) para poder recalcular.

Si un estrato tiene menos titulares que los pedidos, se toman todos y lo que
falta pasa al estrato «resto» del mismo bloque (no ocurrió con la semilla 42).
Total: **300 titulares**; 13 de 30 por celda son de los estratos al azar.

**Pesos.** Cada titular lleva en la clave `N_h`, `n_h` y `peso = N_h / n_h`
(entre 6 y 9.189). La tasa de sesgo de una celda se estima como
Σ_h (N_h / N) · p_h. El IC es de Wilson con el n efectivo de Kish,
(Σ w)² / Σ w². Como el 76 % de la población está en `S_resto` y sólo hay 7
titulares por celda de ese estrato, **los IC por celda serán anchos** (n efectivo
≈ 8–12). Las comparaciones se sostienen mejor agregadas por medio (n efectivo
≈ 15–20) o por gobierno (≈ 40–45). La tasa sin ponderar se reporta, pero
**no estima nada poblacional**: está inflada por el enriquecimiento.

### Dobles y reparto

60 dobles = 6 por celda, elegidos para que haya al menos uno de cada estrato
(así el acuerdo se mide también sobre candidatos y no sólo sobre casos fáciles).
Los otros 240 se reparten 120 y 120, alternados dentro de cada celda × estrato.
Cada persona anota 60 + 120 = **180**. Con 60 dobles, el error estándar de un
kappa en torno a 0,6 es ≈ 0,1: suficiente para saber si las definiciones
funcionan, que es el objetivo. Se mantuvo el tamaño sugerido (300 / 60) aunque
cada titular lleve contexto: ~2 h por persona es el máximo razonable en dos
sesiones. Para afinar las tasas por celda, la manera más barata es una segunda
ronda sólo de `S_resto`.

### Ceguera del medio

- La planilla no tiene medio, URL, enlace ni sección (la URL y secciones como
  «blu360» o «globoeconomia» delatan el medio). El `id` (`T001`…) es aleatorio
  y no codifica medio ni estrato. Tampoco se muestran los medios del contexto.
- **No se ofrece enlace.** El titular publicado tiene tildes y cifras, pero
  abrirlo revela el medio, su diseño y el cuerpo de la nota, y el objetivo es
  etiquetar el titular. Si hace falta el enlace para adjudicar un caso, está en
  `clave_no_abrir.csv`; al usarlo hay que anotarlo en «nota».
- **Autorreferencias.** 915 titulares de la población nombran a un medio:
  programas («Mañanas Blu con Camila Zuluaga»), entrevistas «en Noticias
  Caracol», «editorial de El Tiempo», transmisiones «por el Canal RCN». Casi
  todos son autopromoción o formato, y enmascarar sólo el nombre dejaría pistas
  («[medio] con Camila Zuluaga»). **Decisión: se excluyen de la población.** En
  los titulares de contexto, cualquier mención se reemplaza por «[medio]» (en
  esta muestra no hubo ninguna). «El tiempo» y «la república» sólo cuentan como
  marca en construcciones que nombran al periódico («de el tiempo», «diario la
  república»), no en «Banco de la República» ni «el tiempo se agota».
- Hay un test que recorre todas las celdas (y vínculos) de las dos planillas y
  falla si aparece un nombre de medio, una marca, un dominio o «http».
- **Límite:** quien conozca bien los medios puede reconocer el estilo (p. ej.
  «eeuu» en Blu Radio, nombres completos en El Tiempo, los temas económicos de
  La República). La ceguera reduce el sesgo del anotador; no lo elimina.

### Por qué es «silver» y no «gold»

- Lo anotan dos estudiantes del proyecto, no expertos en análisis de medios ni
  un panel diverso. El sesgo percibido depende de la posición política de quien
  lee; con dos personas no se puede controlar.
- El 80 % de los titulares tiene una sola anotación. El acuerdo medido en las
  dobles indica la calidad esperada, pero cada etiqueta individual tiene ruido.
- Los titulares están reconstruidos desde la URL (sin tildes, cifras, comillas ni
  signos de interrogación; a veces truncados). Las comillas, que marcan la
  atribución, se pierden: eso afecta sobre todo a «Opinión como hecho» y a
  «Atribución selectiva».
- No se lee la nota completa, y el contexto de otros medios sólo existe para el
  60 % de la muestra (y está emparejado con precisión del 81 %).
- El muestreo está enriquecido: la distribución de la muestra no es la de la
  población (hay que ponderar).

Un *gold standard* requeriría al menos tres anotadores con formación,
adjudicación de todos los casos, el titular original y la nota, y pautas
validadas en una ronda piloto.

## Cómo usar el silver standard después

1. **Validar el léxico de carga** (`lexico_carga.yaml` o la lista `CARGA`).
   Precisión: proporción de «Sí» entre los titulares que el léxico marca
   (estratos `*_lexico`, ya en `tasa_por_estrato.csv`). Cobertura (recall): con
   pesos, Σ peso · [marcado ∧ Sí] / Σ peso · [Sí]. Los estratos al azar dicen
   cuántos sesgados se le escapan al léxico. El acuerdo entre léxico y anotación
   por tipo indica qué tipos detecta (es de esperar: lenguaje cargado y
   sensacionalismo, no omisión).
2. **Entrenar o evaluar un clasificador** de titular sesgado (p. ej. regresión
   logística sobre los embeddings de `bertopic/embeddings.npy`). Con 300
   ejemplos, validación cruzada estratificada por celda. Para **evaluar**, usar
   sólo las dobles con acuerdo y las adjudicadas (las de mejor calidad), y
   reportar métricas ponderadas con `peso` si se quiere hablar de la población.
   Para **entrenar**, las simples sirven como etiquetas ruidosas.
3. **Comparar medios y gobiernos** con `tasa_sesgo_medio_gobierno.csv`, con la
   cautela de los IC anchos y de que se mide sesgo **percibido por dos
   anotadores**, no la intención del medio. La dirección (favorable/
   desfavorable al gobierno de turno) se puede comparar entre Duque y Petro
   dentro de un mismo medio.
4. **Ampliar**: más titulares `S_resto` para afinar las tasas; o una ronda
   activa con los titulares en que el clasificador duda.

## Archivos

| Archivo | Contenido | ¿Lo abren quienes anotan? |
|---|---|---|
| `planilla_silver_persona_{1,2}.xlsx` | Planillas (Instrucciones, Anotación, Progreso) | Sí, cada quien la suya |
| `muestra.csv` | Lo que se ve en la planilla: id, doble, fecha, gobierno, titular, contexto | Puede, pero no hace falta |
| `clave_no_abrir.csv` | id → article_id, medio, URL, sección, tópico, estrato, N_h, n_h, peso, evento, similitud con los otros medios, términos de carga, personalización | **No** |
| `poblacion_estratos.csv` | N_h y n_h por medio × gobierno × estrato | **No** (revela la proporción de candidatos) |
| `muestra.json` | Parámetros, exclusiones, tamaños por celda y estrato, lista de términos | No |
| `adjudicacion.xlsx` | (tras `adjudicar`) desacuerdos para decidir | Sí, en la adjudicación |
| `evaluacion.json`, `acuerdo_por_categoria.csv`, `tasa_*.csv`, `silver_standard.csv` | (tras `evaluar`) resultados | Después de anotar |

Semilla 42. Se regenera con `SCRIPT=silver.py ./run.sh - muestra` y
`SCRIPT=silver.py ./run.sh - dividir` (~2 min). Las fórmulas de las planillas se
recalcularon con LibreOffice (`recalc.py` del skill xlsx: 200 fórmulas por
planilla, 0 errores).

## Resultado (8 de noviembre de 2026)

> **La planilla 2 la anotó un modelo de lenguaje («Claude (IA)»), no una segunda
> persona.** El acuerdo que sigue es entre persona e IA.

- **Acuerdo en los 60 dobles:**
  - κ = 0,30 en sesgado sí/no; en tipo y dirección es ≈ 0.
  - La IA marca sesgo en 10, la persona en 32, y los 10 de la IA están entre
    los 32 de la persona: es un umbral más exigente, no ruido.
  - Quedan **32 desacuerdos sin adjudicar** en `adjudicacion.xlsx`.
- **Tasa ponderada:**
  - Persona: 39 % con Duque y 21 % con Petro.
  - IA: 14 % y 12 %.
  - Ninguna diferencia por medio entre gobiernos es significativa.
- **Léxico de carga:** enriquece la muestra (65–69 % de sesgados en los estratos
  con léxico según la persona, frente a 28 % en el resto), pero cubre menos del
  15 % de los titulares sesgados de la población.
- **«Gobierno Petro/Duque» no es un indicador de sesgo:** la IA juzga sesgado 1
  de 13 de esos titulares.
- **El clasificador TF-IDF no supera al léxico:** AUC 0,56–0,62.

El análisis completo está en `analisis/` (lo genera `silver_analisis.py`;
figuras 36–38) y en [`../../INFORME_FINAL.md`](../../INFORME_FINAL.md).
