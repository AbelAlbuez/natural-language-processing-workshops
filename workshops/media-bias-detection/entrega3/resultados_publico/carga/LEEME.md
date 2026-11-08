# Lenguaje evaluativo o cargado dentro del mismo hecho

Código: `carga.py`. Léxico: `lexico_carga.csv`. Datos: los eventos de `eventos.py`
(titulares de medios distintos sobre el mismo hecho, umbral calibrado 0,80,
precisión 81 %, IC 95 % 72–90 %), con el diseño emparejado de `lexico.py`.

```bash
SCRIPT=carga.py ./run.sh - --output resultados_publico                    # ~1,5 min; figuras 30 a 32
SCRIPT=carga.py ./run.sh - --output resultados_publico --etapa validar    # sólo el KWIC del léxico
```

**Esto no es análisis de sentimiento.** El proyecto no usa el sentimiento como
medida de sesgo. Aquí se cuentan palabras que **añaden un juicio al hecho**:
«polémica», «escándalo», «fracaso», «caos», «arremete», «revés», «logro»,
«histórico», «contundente»… Que un titular las lleve no dice nada de su
veracidad ni de la postura del medio. Lo que sí puede decir algo es que, **ante
el mismo hecho**, un medio las use más que los otros.

## Método

### Léxico curado (`lexico_carga.csv`)

No hay red en el contenedor, así que no se usó ningún léxico externo. Se
construyó uno a mano: 77 entradas, 74 activas. Cada fila es una entrada (un lema
o una familia de palabras) con:

| Columna | Contenido |
|---|---|
| `id` | nombre de la entrada |
| `polaridad` | `negativa`, `positiva` o `neutra` (intensificador o sensacionalismo sin dirección) |
| `tipo` | `juicio`, `intensificador`, `sensacionalismo`, `conflicto`, `atribucion_cargada`, `atribucion_neutra` |
| `formas` | variantes como expresión regular, **sin tildes** (los titulares no las tienen): `polemic(?:a\|as\|o\|os)` |
| `excluir` | contextos que anulan una coincidencia que caiga dentro de ellos: `golpe de (?:estado\|calor)`, `pacto historico` |
| `activa` | `si` / `no` (las desactivadas se quedan documentadas) |
| `origen` | `a_priori` o `tras_datos` (cambiada después de ver los contextos) |
| `nota` | criterio y, si cambió, qué se vio en los datos |

Composición de las 74 activas:

| Tipo | Negativa | Positiva | Sin polaridad |
|---|---:|---:|---:|
| juicio («polémica», «fracaso», «logro») | 18 | 8 | — |
| sensacionalismo («escándalo», «caos», «insólito») | 9 | — | 2 |
| conflicto («rifirrafe», «choque», «tensión») | 7 | — | 1 |
| intensificador («histórico», «contundente», «duro») | — | — | 6 |
| atribución cargada («arremete», «admite que», «celebra») | 11 | 2 | 4 |
| atribución neutra («dijo», «afirmó», «aseguró») | — | — | 6 (referencia) |

**Criterio.** Entra una palabra si añade una valoración que el hecho no exige:
«polémica por el decreto» frente a «decreto»; «arremetió contra» frente a
«dijo»; «escándalo de la UNGRD» frente a «caso de la UNGRD». No entran palabras
que **describen** el hecho, aunque sea negativo («muerto», «ataque»,
«corrupción», «secuestro»): eso es agenda, no encuadre. «Histórico», «récord»,
«golpe» y «advierte» van **sin polaridad**: el dato real decide la dirección
(«histórico acuerdo» frente a «máximo histórico del dólar»; «duro golpe al Clan
del Golfo» es lenguaje de éxito policial).

**Indicadores por titular** (unidad: titular núcleo, uno por medio y evento):

- *negativa*: alguna entrada negativa (sin contar la atribución neutra);
- *positiva*: alguna entrada positiva;
- *carga*: cualquier entrada que no sea atribución neutra (incluye los intensificadores);
- *neto*: negativa − positiva (−1, 0, 1);
- *atribución cargada entre las atribuciones*: entre los titulares con un verbo
  de atribución, % con uno cargado (cociente de sumas sobre los eventos).

### Validación (`validacion_lexico.md`, `frecuencias_lexico.csv`)

Para cada entrada, sobre los 49.759 titulares núcleo: formas más frecuentes,
palabra a la izquierda y a la derecha, coincidencias anuladas por las
exclusiones y 8 titulares al azar con la palabra marcada. Con eso se revisó todo
el léxico. **28 entradas se cambiaron después de ver los contextos** (`origen =
tras_datos`):

- **Desactivadas (3)**: «guerra» (casi siempre guerras literales —Ucrania,
  Gaza—, «guerra comercial» y el apellido Guerra); «ataca» (ataques armados
  literales: «atacan estación de policía»); «positivo» («falsos positivos», el
  74 %, y «dio positivo» por COVID).
- **Falsos amigos de la normalización sin tildes**: «choco» era «Chocó» (68 % de
  «choque»), «ira» era «irá» (futuro de *ir*). Se quitaron esas formas.
- **Nombres propios**: «Pacto Histórico» (272 coincidencias anuladas de
  «histórico»), «Centro Esperanza» y Esperanza Gómez, Aida Victoria Merlano.
- **Trámites que no son juicio**: «Consejo de Estado admite demanda», «Corte
  rechaza tutela», «Fiscalía acusa a…», «archiva denuncia», «declara estado de
  desastre», «estado de alarma». «Admite» y «reconoce» quedan sólo como
  concesión («admite que», «reconoce error»); «la UE reconoce a Guaidó» no
  cuenta. «Amenaza» queda sólo como «amenaza con» (las amenazas literales de
  muerte son un hecho).
- **Literal frente a figurado**: «golpe de calor», «de golpe», «golpeado por un
  rayo»; «grave accidente», «herido de gravedad»; «objetos contundentes»;
  «explosivos improvisados»; «no duró un día» (verbo durar); «plan de choque»;
  «alta tensión»; accidentes de tránsito («choque entre dos buses»);
  hundimientos de embarcaciones.
- **Polaridad revisada**: «golpe», «advierte» y «exige» pasan a sin polaridad.
- **Negación**: «no logró» no cuenta como «logro».
- **Añadidas al ver ejemplos**: «críticas a/al» y los plurales «hundidos/as».

Las entradas más frecuentes (titulares núcleo): «denuncia» 1,2 %, «crisis»
1,0 %, «escándalo» 0,85 %, «revela» 0,74 %, «rechaza» 0,73 %, «polémica»
0,69 %, «advierte» 0,63 %, «tensión» 0,41 %, «triunfo/victoria» 0,39 % y «acusa»
0,37 %. Son las 10 que se quitan en la prueba de robustez. Quedan dudas
conocidas: «crisis» y «escándalo» son a veces el nombre corriente de un caso;
«hundimiento de la reforma» es jerga legislativa; «rechazó» es a la vez verbo y
sustantivo. Se dejaron porque elegirlas frente a «caso» o «archivo» sigue siendo
una elección de redacción, y la robustez sin las 10 más frecuentes muestra si
pesan.

### Diseño emparejado

Igual que `lexico.py` (se importan `matrices_emparejadas`, `pesos_bootstrap`,
`formas_nombrar`, `recorte_rcn`, `precision_fecha_rcn`). Para cada medio y
gobierno se toman los eventos en los que está el medio y al menos otro medio. Se
compara el % de titulares del medio con un indicador frente al % de **los otros
medios en esos mismos eventos**. Los otros se promedian dentro del evento, así
que cada evento pesa uno en cada lado. IC 95 % por **bootstrap de eventos**
(2.000 réplicas). Se reportan la diferencia en puntos porcentuales (pp) y la
diferencia relativa ((medio − otros) / otros). El cambio Petro − Duque resta las
réplicas de los dos gobiernos, que tienen eventos disjuntos.

**Por qué el emparejamiento es esencial.** Un hecho negativo (una masacre, un
escándalo) produce palabras negativas en todos los medios. Comparar niveles
brutos mezclaría agenda con redacción. Dentro del evento, la agenda es la
misma; un test lo comprueba (si todos los medios llevan carga en los mismos
eventos, la diferencia es 0 exacto aunque el nivel sea del 60 %).

### Carga dirigida al gobierno

Un titular **nombra al gobierno** si tiene alguna forma de `ref_ejecutivo` de
`lexico.formas_nombrar`: «Gobierno Petro/Duque», «presidente Petro/Duque»,
«Gustavo Petro/Iván Duque», el apellido, «Gobierno nacional», «Gobierno» sin
más, «mandatario», «Casa de Nariño»… Es **simétrico**: el apellido es siempre el
del presidente de ese gobierno. Sólo en eventos domésticos (sin los tópicos de
otros países T2, T5, T13 y T16).

Dos medidas:

- **Ambos nombran (principal)**: sólo los titulares que nombran al gobierno, en
  eventos donde el medio y al menos otro medio lo nombran. Pregunta: ante el
  mismo hecho y la misma mención del gobierno, ¿el medio añade carga?
- **Todos los titulares**: % de todos los titulares que nombran al gobierno y
  llevan carga. Mezcla cuánto se nombra al gobierno con cómo; va en el CSV.

La carga puede referirse al gobierno o al hecho («Petro ordenó liquidar las EPS…
en plena crisis de salud»), o venir de una fuente que el medio cita («Alcaldes
rechazan día cívico»). No se separan: es una medida de cómo se redacta el
titular que nombra al gobierno, no de lo que el medio piensa de él.

### RCN

Como en `lexico.py`: RCN sólo tiene fecha al día de forma sostenida desde
2020-09, así que en Duque se analiza desde esa fecha (1.935 eventos). Controles:
sin RCN entre los otros y ventana común (Duque desde 2020-09 para todos).

### Robustez (`robustez_carga.csv`, figura 32)

Seis variantes además de la principal: bootstrap **por meses**; **con
seguimiento**; **sin RCN** entre los otros; **ventana común**; **titulares de
largo similar** (eventos donde el titular del medio y el promedio de los otros
difieren en ≤2 palabras: un titular más largo tiene más ocasiones de llevar una
palabra del léxico); y **sin las 10 entradas más frecuentes**.

## Resultados

Niveles: entre el 6 % y el 10 % de los titulares núcleo lleva alguna palabra
negativa del léxico; alrededor del 1 %, alguna positiva. El lenguaje cargado
positivo es raro en todos los medios.

### 1. Por medio y gobierno (figura 30, `carga_medio_gobierno.csv`)

Carga **negativa**, medio − otros medios en los mismos eventos (pp; IC 95 %):

| Medio | Duque | Petro | Cambio Petro − Duque |
|---|---:|---:|---:|
| El Tiempo | **−2,1 (−2,8 a −1,3)** | +0,9 (0,3 a 1,5) | +3,0 (2,0 a 3,9) |
| Blu Radio | +0,7 (−0,1 a 1,4) | 0,0 (−0,7 a 0,6) | −0,7 (−1,7 a 0,3) |
| Noticias RCN* | −0,3 (−1,4 a 0,9) | −0,5 (−1,3 a 0,2) | −0,3 (−1,6 a 1,0) |
| Noticias Caracol | **+2,4 (1,3 a 3,4)** | +0,6 (−0,1 a 1,4) | **−1,8 (−3,1 a −0,5)** |
| La República | −0,5 (−1,8 a 0,8) | **−3,1 (−4,1 a −2,1)** | **−2,6 (−4,2 a −0,9)** |

\* RCN en Duque sólo desde 2020-09.

En relativo: Caracol en Duque lleva carga negativa en el 10,1 % de sus titulares
frente al 7,7 % de los otros medios en los mismos eventos (+31 %). La República
en Petro, en el 5,4 % frente al 8,5 % (−36 %).

Carga **positiva**: todas las diferencias están entre −0,5 y +0,6 pp. Sólo El
Tiempo en Duque (−0,5; −0,8 a −0,1) y RCN en Duque (+0,6; 0,0 a 1,2) tienen IC
que no cruzan el 0, y ninguna sobrevive a todas las variantes.

**Verbos de atribución**: entre los titulares con un verbo de atribución, Blu
Radio usa uno cargado («denuncia», «rechaza», «arremete», «revela») frente a uno
neutro («dice», «afirma») más que los otros: +12,5 pp en Duque (6,3 a 18,5) y
+11,4 en Petro (7,5 a 15,3). RCN en Petro, +8,7 (3,7 a 13,8). El Tiempo (−13,6
en Duque, −5,2 en Petro), Caracol en Petro (−6,9) y La República en Petro (−9,7)
usan más los neutros.

Qué palabras empujan cada diferencia (`carga_por_entrada.csv`):

- **Caracol en Duque**: el sensacionalismo de suceso: «terror/pánico/brutal»
  (+0,36 pp), «tragedia/trágico» (+0,30), «advierte», «escándalo». Por tema, se
  concentra en conflicto armado y combates (T0 y T7, ver abajo).
- **La República en Petro**: lo contrario. Evita «polémica» (−0,81 pp),
  «crisis» (−0,65), «revela» (−0,53) y «escándalo» (−0,33). Por tema, en
  relaciones exteriores (T2), Venezuela (T5), trabajo y pensiones (T12) y reforma
  a la salud (T17).
- **El Tiempo en Petro**: «polémica» (+0,36), «golpe» (+0,28), «crisis» (+0,28).

### 2. Carga dirigida al gobierno (figura 31, `carga_gobierno.csv`)

**El nivel sube con Petro en todos los medios juntos.** Entre los titulares
núcleo de eventos domésticos que nombran al gobierno (cinco medios):

| | Duque | Duque desde 2020-09 | Petro |
|---|---:|---:|---:|
| con carga negativa | 5,2 % (4,1–6,5; n = 1.394) | 3,8 % (2,7–5,4; n = 767) | **9,7 % (8,9–10,6; n = 4.538)** |
| con carga positiva | 2,1 % (1,5–3,0) | 2,5 % (1,6–3,8) | 0,9 % (0,7–1,2) |

La carga negativa al nombrar al gobierno casi se duplica y la positiva baja a la
mitad. Ese cambio es **común a los cinco medios** y se mantiene con la ventana
común. Puede ser de agenda (más escándalos, reformas hundidas, choques con otras
ramas en el periodo de Petro), del estilo del presidente o del periodo. Este
diseño no lo atribuye a ningún medio.

**Frente a los otros medios, ante el mismo hecho y la misma mención** (ambos
nombran al gobierno; pp, IC 95 %):

| Medio | Negativa Duque | Negativa Petro | Cambio | Eventos D / P |
|---|---:|---:|---:|---:|
| El Tiempo | −2,1 (−5,0 a 0,5) | +0,6 (−1,0 a 2,3) | +2,7 (−0,2 a 6,1) | 332 / 1.163 |
| Blu Radio | +1,2 (−1,0 a 3,4) | +0,3 (−1,5 a 2,0) | −0,9 (−3,7 a 1,8) | 343 / 1.032 |
| Noticias RCN* | −1,3 (−4,0 a 0,0) | +0,5 (−1,9 a 2,9) | +1,8 (−1,1 a 5,1) | 113 / 671 |
| Noticias Caracol | +3,1 (−0,2 a 6,5) | −1,7 (−3,6 a 0,2) | **−4,8 (−8,7 a −0,9)** | 239 / 670 |
| La República | −0,3 (−2,3 a 1,6) | −0,6 (−3,0 a 1,8) | −0,2 (−3,3 a 2,9) | 153 / 331 |

- **Ningún medio añade carga negativa al gobierno de forma distinguible de los
  otros, en ninguno de los dos gobiernos.** Los diez IC cruzan el 0 o lo tocan.
- La carga **positiva** dirigida al gobierno es tan rara (≈1 %) que no permite
  comparar: todas las diferencias están entre −1,6 y +1,1 pp y cruzan el 0.
- El único contraste con IC que excluye el 0 es el **cambio de Caracol**:
  ligeramente más carga negativa que los otros con Duque (+3,1) y algo menos con
  Petro (−1,7). Es una sola celda entre diez y ninguna de sus dos diferencias es
  significativa por sí sola en la principal; la de Duque sólo excluye el 0 sin
  RCN entre los otros (figura 32). Hay que leerlo como indicio, no como hallazgo.
- RCN en Duque: ninguno de sus 113 titulares que nombran al gobierno en eventos
  compartidos lleva una palabra negativa del léxico (los otros, el 1,3 %). Con
  ese tamaño, el IC llega al 0.

### 3. Por tema (`carga_tema.csv`)

94 celdas medio × gobierno × tema con ≥150 eventos del medio (sin T8, mixto, ni
T14, fútbol residual), con FDR dentro de cada indicador (94 pruebas). 12
diferencias con q < 0,05, todas en *cualquier carga*; en *negativa* las mejores
quedan en q ≈ 0,06. Repiten los patrones generales:

- El Tiempo en Duque, menos carga en conflicto (T0), exterior (T2), justicia
  (T6) y combates (T7: −8,9 pp, −12,7 a −5,3); en parte, slugs cortos.
- Caracol en Duque, más en combates (T7: +8,3 pp, 3,8 a 13,2) y conflicto (T0:
  +5,1, q = 0,051).
- La República en Petro, menos en exterior (T2: −6,8), Venezuela (T5: −5,1) y
  trabajo y pensiones (T12: −4,6, q = 0,06).
- El Tiempo en Petro, más en Venezuela (T5: +3,1), economía (T10: +5,2) y
  narcotráfico (T15: +5,4); Blu Radio en Petro, menos en economía (T10: −4,9).

No aparece un tema donde un medio cargue contra el gobierno. En el tópico
«Gobierno y presidente» (T1), sólo Caracol en Duque tiene un IC de negativa que
excluye el 0 (+4,9 pp, 1,3 a 8,5), con q = 0,09.

### 4. Ejemplos (`ejemplos_carga.md`)

Eventos reales donde un medio usa carga y ningún otro la usa, elegidos al azar
entre los candidatos (semilla 42): carga negativa al nombrar al gobierno, carga
positiva al nombrar al gobierno y carga negativa en general. Dos de Petro:

| Medio | Titular (evento 8558, 2024-05-28) |
|---|---|
| **El Tiempo** | No me interesa para nada la reeleccion presidente petro responde a la **polemica** desatada por senadora zuleta |
| Blu Radio | Presidente petro a mi no me interesa para nada la reeleccion |
| Noticias RCN | Presidente gustavo petro asegura que no le interesa para nada la reeleccion |
| Noticias Caracol | Presidente gustavo petro aseguro que no le interesa para nada la reeleccion |

| Medio | Titular (evento 6351, 2023-06-02) |
|---|---|
| El Tiempo | Laura sarabia sofia petro reacciona a su salida de gobierno petro y la defiende |
| Blu Radio | Laura sarabia y armando benedetti se van del gobierno |
| Noticias RCN | Laura sarabia y armando benedetti salen del gobierno por decision del presidente gustavo petro |
| **Noticias Caracol** | Laura sarabia y armando benedetti salen del gobierno tras **escandalo** con ninera marelbys meza |

Los ejemplos muestran el tipo de diferencia que se mide: una palabra que
califica («polémica», «escándalo», «crisis») añadida a un hecho que los otros
cuentan sin ella. También muestran sus límites: a veces la palabra la pone una
fuente («Procuraduría denuncia al presidente»), no el medio.

### 5. Qué es robusto y qué no (figura 32)

| Resultado | Principal | Se mantiene en | No se mantiene en |
|---|---|---|---|
| Caracol en Duque, más carga negativa | +2,4 | las seis variantes (+1,8 a +2,6, todas con IC > 0) | — |
| La República en Petro, menos carga negativa | −3,1 | las seis (−1,1 a −3,3, todas con IC < 0) | se atenúa a −1,1 sin las 10 más frecuentes («polémica», «crisis», «escándalo» pesan) |
| El Tiempo en Duque, menos carga negativa | −2,1 | las seis (−1,4 a −2,2) | se atenúa con largo similar: **parte es artefacto de los slugs cortos** (10,3 palabras frente a 12,1) |
| El Tiempo en Petro, más carga negativa | +0,9 | meses, seguimiento, sin RCN, ventana | **desaparece** con largo similar (−0,5) y sin las 10 más frecuentes (+0,1) |
| Blu Radio, más atribución cargada | +12,5 / +11,4 | todas en Petro; en Duque todas salvo sin las 10 más frecuentes | Duque sin las 10: +5,0 (−3,0 a 12,3) |
| Carga dirigida al gobierno | ningún medio se aparta | en 6 de las 136 combinaciones variante × celda × indicador (negativa y positiva) un IC excluye el 0, sin patrón: El Tiempo en Duque, menos negativa con seguimiento y sin RCN; RCN en Duque, menos con seguimiento; Caracol en Duque, más sin RCN (+3,8; 0,5 a 7,7); Caracol en Petro, menos con largo similar; La República en Duque, menos positiva con largo similar | — |

Entre las diferencias generales con IC que excluye el 0 en la principal, sólo
cambian de signo en alguna variante El Tiempo en Petro (negativa, carga y neto)
y RCN en Petro (carga), las dos con largo similar.

## Limitaciones

- **Léxico hecho a mano.** 74 entradas elegidas por una persona, revisadas con
  KWIC y cambiadas en 28 casos tras ver los datos (documentado en `origen` y
  `nota`). No tiene validación externa ni acuerdo entre anotadores; la
  sensibilidad es baja (sólo lo que está en la lista) y la precisión por
  entrada no se midió con una muestra anotada. Otro léxico podría dar otras
  cifras; la robustez sin las 10 más frecuentes acota cuánto depende de unas
  pocas palabras.
- **Titulares reconstruidos desde la URL**: sin tildes, cifras, comillas ni
  mayúsculas, y a veces truncados. Sin tildes, «choco» es «Chocó» y «ira» es
  «irá»; se corrigió lo que se vio, pero pueden quedar casos. Sin comillas no se
  distingue la carga del medio de la de una cita textual.
- **Largo del titular**: un slug más largo tiene más ocasiones de llevar una
  palabra del léxico. Los de El Tiempo en Duque son 2 palabras más cortos que los
  de los otros medios; su «menos carga» en Duque es en parte eso.
- **Cota inferior por el emparejamiento ≥ 0,80**: los eventos se forman con
  similitud de embeddings ≥ 0,80, así que favorecen titulares redactados de
  forma parecida. Un medio que cuente el mismo hecho con un encuadre muy
  distinto tiende a no emparejarse. Las diferencias medidas aquí son **una cota
  inferior**. Además, el 19 % de los pares no son el mismo hecho, lo que mete algo
  de agenda.
- **Carga ≠ sesgo.** Una palabra cargada puede ser el registro de la casa
  (Caracol, noticiero de televisión, usa más el léxico de suceso), una cita de
  la fuente o una descripción justa de un hecho grave. Este análisis mide
  elecciones de redacción, no intención ni postura política.
- **Carga dirigida al gobierno**: la mención y la carga se miden en el mismo
  titular, pero no se verifica que la palabra se refiera al gobierno. Los
  tamaños por celda son modestos (113 a 1.163 eventos) y la carga positiva es
  casi inexistente.
- **Inferencia**: muchas comparaciones (5 medios × 2 gobiernos × varios
  indicadores). En las tablas principales no se corrige por multiplicidad; por
  tema se usa FDR. Un IC aislado que roza el 0 debe leerse con cautela.
- **RCN en Duque**: sólo 2020-09–2022-08 (pandemia, paro, campaña).

## Archivos

| Archivo | Contenido |
|---|---|
| `carga_medio_gobierno.csv` | indicadores por medio × gobierno × variante: % medio, % otros, diferencia, IC, diferencia relativa |
| `carga_gobierno.csv` | carga dirigida al gobierno, medidas `ambos_nombran` y `todos`, por variante |
| `carga_cambio_duque_petro.csv` | cambio Petro − Duque de la diferencia medio − otros, con IC y cambio relativo |
| `niveles_gobierno.csv` | nivel de carga al nombrar al gobierno, cinco medios juntos, IC de Wilson |
| `robustez_carga.csv` | resumen largo de todas las variantes (signo e IC frente a la principal) |
| `carga_por_entrada.csv` | diferencia medio − otros de cada entrada del léxico |
| `carga_tema.csv` | por tema de BERTopic (≥150 eventos del medio), con q de FDR |
| `frecuencias_lexico.csv` | frecuencia de cada entrada, total y por medio × gobierno |
| `validacion_lexico.md` | KWIC de todas las entradas (también las desactivadas) |
| `ejemplos_carga.md` | eventos reales con los titulares lado a lado y la carga detectada |
| `carga.json` | parámetros y cifras clave |
| `figuras/30`–`32` | carga por medio y gobierno, carga dirigida al gobierno, robustez |

## Borrador para el artículo

> Para medir el lenguaje evaluativo sin recurrir al análisis de sentimiento,
> construimos un léxico de 74 entradas de palabras que añaden un juicio al hecho
> («polémica», «escándalo», «fracaso», «arremete», «logro», «histórico»),
> validado con concordancias y corregido tras ver los datos (se excluyeron, por
> ejemplo, «Pacto Histórico», «golpe de calor» y los trámites judiciales). Dentro
> de cada evento comparamos el titular de un medio con los de los otros medios
> que cubrieron el mismo hecho, de modo que la agenda queda fija. Las
> diferencias son pequeñas: entre el 6 % y el 10 % de los titulares lleva una
> palabra negativa del léxico y los medios se apartan de los demás en, como
> mucho, tres puntos. Noticias Caracol usa más léxico de suceso durante el
> gobierno Duque (+2,4 puntos frente a los otros medios en los mismos eventos;
> IC 95 % 1,3–3,4), y La República menos carga negativa durante el de Petro
> (−3,1; −4,1 a −2,1); Blu Radio prefiere verbos de atribución cargados
> («denuncia», «arremete») a los neutros en los dos gobiernos. Entre los
> titulares que nombran al gobierno, la proporción con carga negativa casi se
> duplica con Petro (del 5,2 % al 9,7 %), pero el aumento es común a los cinco
> medios: ante el mismo hecho y la misma mención del gobierno, ningún medio
> añade carga negativa de forma distinguible de los demás en ninguno de los dos
> gobiernos. Estas cifras describen elecciones de redacción en titulares
> reconstruidos desde la URL, con un léxico hecho a mano y sobre eventos
> emparejados con una precisión del 81 %, que tienden a juntar titulares
> parecidos (una cota inferior de las diferencias); no miden la postura de los
> medios.
