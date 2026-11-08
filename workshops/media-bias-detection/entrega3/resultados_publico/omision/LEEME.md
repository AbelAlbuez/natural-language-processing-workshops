# Cobertura u omisión por tema × gobierno (paso 4)

**Pregunta.** En los hechos que cubren al menos tres medios, ¿qué medio falta en
qué temas, y cambia eso entre Duque y Petro más allá del cambio general del
medio?

Código: `entrega3/omision.py`. Tests: `entrega3/tests/test_omision.py`.
Entrada: los eventos de `eventos.py` (umbral 0,80, precisión 81 %, IC 95 %
72–90 %) y el tópico de BERTopic de cada titular.

**Es descriptivo.** Mide en qué eventos aparece cada medio dentro del archivo
recuperado. No controla la agenda propia de cada medio (La República es un
diario económico), el tamaño de su redacción ni lo que el archivo no conserva, y
el emparejamiento no tiene el recall medido. Ningún número de este documento
mide sesgo.

## Método

- **Unidad:** el evento (titulares de medios distintos sobre el mismo hecho).
  Sólo cuenta el núcleo (un titular por medio), no el seguimiento. **Tema** del
  evento = el tópico de BERTopic más frecuente en su núcleo. **Mes** = mes de
  inicio. **Gobierno** = el de la mayoría de sus titulares.
- **Denominador sin sesgo de selección.** En un evento de exactamente 3 medios,
  cada uno de los 3 forma parte de su definición: ninguno puede «faltar». Si el
  denominador es «eventos con ≥3 medios», la participación de cada medio se
  infla, y más la de los medios que suelen ser el tercero. Por eso el
  denominador del medio *m* son los eventos con **al menos 3 de los OTROS 4
  medios presentes**: la entrada no depende de *m*. Con el denominador
  ingenuo, El Tiempo saldría en el 86 % de los eventos de Duque. Con el
  corregido sale en el 66 %. La Republica pasa del 27 % al 14 %. El test
  `test_condicionar_a_los_otros_corrige_el_sesgo_de_seleccion` lo comprueba con
  presencias independientes simuladas: el denominador corregido recupera la
  probabilidad real (0,40) y el ingenuo da más de 0,50.
- **Participación** = % de los eventos del denominador en los que el medio
  está, por tema y en general (todos los temas).
- **Omisión específica** = participación en el tema − participación general del
  medio en ese gobierno, en puntos porcentuales (pp). Descuenta que un medio
  publique menos en general o que su archivo tenga huecos. Negativa: el medio
  falta en ese tema más que en el resto.
- **Δ específico** = omisión específica con Petro − con Duque.
  **Δ relativo** = Δ específico del medio − la media del de los otros cuatro,
  como `topics.relative_series`. Por construcción suma 0 entre medios: lo que
  cambió para todos se cancela.
- **Inferencia.** IC 95 % y p-valor por bootstrap de bloques móviles circulares
  de 3 meses (20.000 réplicas, el mismo esquema que
  `topics.block_bootstrap_diff`). Cada gobierno se remuestrea por separado.
  **Diferencia con `block_bootstrap_diff`:** ese bootstrap promedia una
  proporción por mes, pero aquí un tema tiene de 0 a 5 eventos al mes y la
  proporción de cada mes sería muy ruidosa o no existiría. En su lugar se
  remuestrean los meses (con todos sus eventos) y en cada réplica se recalculan
  los cocientes con los conteos sumados. Se respeta igual la dependencia entre
  meses vecinos. Corrección de Holm sobre todas las parejas medio × tema de cada
  análisis.
- **Temas con inferencia:** sólo los que tienen ≥ 30 eventos en el denominador
  de **cada** medio y **cada** gobierno (`--min-eventos`). Los demás se
  reportan sin prueba en `participacion.csv`. COVID y vacunación existen sólo
  con Duque, y la reforma a la salud sólo con Petro, así que no se comparan.
- **T8 («Mixto: medidas de gobierno, energía y Estados Unidos») no es un tema**
  y no se cita como hallazgo. Va en gris en las figuras, con
  `citable = False` en los CSV. Sí entra en la familia de Holm, lo que es
  conservador. T2 también es en parte mixto (países vecinos y relaciones
  exteriores): conviene leerlo con cautela.

## Decisión sobre Noticias RCN

Los eventos exigen fecha al día. Los titulares de RCN del subcorpus tienen esta
precisión de fecha (`prepared.parquet`, % con fecha al día por mes):

| Periodo | RCN con fecha al día | Participación de RCN en los eventos |
|---|---:|---:|
| 2018-09 → 2019-09 | 0 % | 0 % (no puede aparecer) |
| 2019-10 | 90 % | 20 % |
| 2019-11 → 2020-08 | 38–55 % | 17–41 % |
| **2020-09 → 2026-08** | **≥ 80 % todos los meses** (≥ 93 % salvo feb.–mar. 2021) | 25–68 % (sin agosto de 2026) |

Los otros cuatro medios tienen fecha al día en casi todo, con meses bajos aislados: Blu Radio 55 % en mayo de 2025 y Caracol 77 % en febrero de 2022. No son huecos de años como el de RCN.

**Análisis principal: Duque restringido a 2020-09-01 → 2022-08-06, para los
cinco medios; Petro completo.** Es la ventana en que los cinco medios tienen
fecha al día. Se aplica a todos, y no sólo a RCN, para que los cinco se midan
sobre los mismos eventos. Así el Δ relativo compara lo mismo. El costo es la
potencia: con Duque quedan 24 meses y 1.117 eventos con ≥3 medios, frente a
3.951 con Petro.

Sin la restricción, la participación general de RCN con Duque cae al 26 %, un
artefacto (figura 25, izquierda). La cifra del README (50 % frente a 69 %) usa
el denominador ingenuo en el periodo completo. Con la ventana, RCN queda en
47 % con Duque y 48 % con Petro: la «subida» de RCN desaparece.

**Queda un efecto residual.** Entre 2020-09 y 2021-04 RCN tiene fecha al día,
pero publica en el subcorpus entre el 43 % y el 59 % de su mediana mensual.
Desde mayo de 2021 publica ≥ 65 %. Su participación en esos meses (25–47 %)
está por debajo de la de después. La omisión específica descuenta ese nivel
siempre que el hueco afecte a todos los temas por igual. Además se agrega la
variante «Duque desde 2021-05».

**Robustez** (`robustez_rcn.csv`, figura 25):

- (a) **sin RCN:** periodo completo con 4 medios. El denominador pasa a «≥2
  de los otros 3»: con 4 medios, «≥3 de los otros 3» exige que estén todos y
  deja muy pocos eventos. También se calcula en la ventana (`sin_rcn_ventana`).
- (b) **sin restricción:** periodo completo con 5 medios.
- (c) **Duque desde 2021-05.**
- (d) **«≥2 de los otros 4»** en vez de «≥3 de los otros 4». Sigue sin sesgo
  de selección (con *m* el evento tendría ≥3 medios), triplica los
  denominadores y permite probar 15 temas en vez de 4. Tiene su propia familia
  de Holm (75 pruebas). Las variantes (b), (c) y la cota de recall se calculan
  con los dos denominadores.

## Resultados

### Participación general (denominador: ≥3 de los otros 4)

| Medio | Duque 2020-09→ | Petro | Δ Petro − Duque (IC 95 %) | Duque, periodo completo | Ingenuo Duque / Petro |
|---|---:|---:|---|---:|---:|
| El Tiempo | 66 % | 75 % | **+8,8 pp (2,5 a 15,5)** | 66 % | 86 % / 89 % |
| Blu Radio | 62 % | 60 % | −2,5 pp (−7,9 a 3,6) | 61 % | 84 % / 80 % |
| Noticias RCN | 47 % | 48 % | +1,2 pp (−6,1 a 9,1) | **26 %** | 72 % / 69 % |
| Noticias Caracol | 40 % | 45 % | **+5,3 pp (0,5 a 10,7)** | 42 % | 64 % / 66 % |
| La República | 14 % | 21 % | **+7,1 pp (1,7 a 12,2)** | 18 % | 27 % / 35 % |

Denominadores: entre 446 (El Tiempo) y 958 (La República) eventos con Duque, y
entre 1.660 y 3.275 con Petro. El Δ general se da sin Holm: sólo sirve de
contexto.

### Qué medio falta en qué tema (omisión específica, figura 23)

El patrón más claro es el de **La República**. Con Petro casi no aparece en los
eventos de Policía y delitos (participa en el 1 %, −20,1 pp, IC −23,1 a −16,7),
de Justicia (−19,9 pp), de Conflicto y víctimas (−19,4 pp) ni de Combates
(−19,0 pp). En cambio está por encima de su media en Impuestos (+16,1 pp, IC
4,2 a 30,1), en Economía (+14,2 pp) y en Venezuela (+10,7 pp). Con Duque el
patrón es el mismo, con menos eventos. Es el perfil de un diario económico, no
una omisión en sentido editorial.

Con Petro, El Tiempo (Policía −13,4, Justicia −12,7, Conflicto −10,6,
Elecciones −9,9 pp) y RCN (Policía −18,2 pp, IC −26,7 a −8,0) faltan más en los
eventos de orden público y justicia que en el resto. También Caracol en Justicia
(−9,7 pp). Los IC de El Tiempo rozan el 0. Con Duque, RCN falta en Justicia
(−20,0 pp, IC −27,1 a −13,3, n = 33 eventos). Venezuela es el tema en que más
medios están por encima de su media.

**Ojo con el techo y el piso.** La omisión específica es una resta de
porcentajes. Un medio que ya está en el 80 % de los eventos de un tema no puede
subir mucho, y uno que está en el 1 % no puede bajar. Cuando la participación
general de un medio sube (El Tiempo, +8,8 pp), su omisión específica en los
temas donde ya estaba casi siempre baja de forma mecánica.

### Cambio Duque → Petro más allá del cambio general (Δ relativo, figura 24)

Con el denominador principal sólo 4 temas tienen ≥ 30 eventos en todas las
celdas: T2, Elecciones, Venezuela e Impuestos. Eso da 20 pruebas, y **una** es
significativa tras Holm. Con «≥2 de los otros 4» hay 15 temas y 75 pruebas, y
**dos** son significativas.

| Medio · tema | Denominador | Participación Duque → Petro | Δ relativo (IC 95 %) | p Holm |
|---|---|---|---|---:|
| **Caracol · Venezuela, Cuba y Maduro** | ≥3 de los otros 4 | 38 % → 57 % (general 40 % → 45 %) | **+14,4 pp (6,2 a 21,3)** | 0,008 |
| | ≥2 de los otros 4 | 26 % → 38 % (general 23 % → 24 %) | +11,1 pp (5,5 a 16,1) | 0,030 |
| **RCN · Justicia: cortes, Fiscalía y corrupción** | ≥2 de los otros 4 | 22 % → 30 % (general 27 % → 27 %) | **+7,5 pp (2,9 a 12,7)** | 0,037 |

Lectura: con Petro, Caracol aparece más en los eventos sobre Venezuela, en
relación con su propia media y con lo que cambiaron los otros medios. RCN deja
de faltar en los eventos de justicia: con Duque estaba por debajo de su media
(−4,6 pp; −20 pp con el denominador estricto) y con Petro está algo por encima
(+3,8 pp).

Hay otros cruces con un IC sin el 0 pero sin Holm: El Tiempo · Venezuela,
−15,3 pp (IC −26,4 a −3,3, p Holm 0,24), y La República · Venezuela, +8,3 pp
(0,1 a 16,8, p Holm 0,86). No se reportan como hallazgos.

### Qué es robusto (figura 25, `robustez_rcn.csv`)

| Cruce | ≥2 de 4 | Sin restricción (≥2) | Duque desde 2021-05 (≥2) | Sin RCN | Casi presente ≥ 0,75 (≥3 / ≥2) |
|---|---|---|---|---|---|
| Caracol · Venezuela | +11,1 (5,5 a 16,1)* | +5,2 (0,1 a 10,9) | +10,2 (3,4 a 16,7) | +9,2 (4,2 a 13,7)* | +10,1 (−1,5 a 20,7) / +5,0 (−1,2 a 10,8) |
| RCN · Justicia | +7,5 (2,9 a 12,7)* | +9,4 (4,7 a 13,4)* | +9,3 (4,0 a 16,0)* | — | +35,1 (18,3 a 50,4)* / +10,1 (4,1 a 16,6) |
| El Tiempo · Venezuela | −11,7 (−19,3 a −3,9) | −9,0 (−13,7 a −4,2)* | −12,0 (−21,1 a −3,2) | −8,8 (−15,5 a −3,0) | −9,5 (−21,1 a 2,0) / −13,8 (−21,0 a −5,3) |
| La República · Venezuela | +8,3 (1,1 a 15,4) | −3,1 (−8,3 a 4,2) | +8,6 (−0,3 a 17,1) | −1,3 (−6,8 a 5,2) | +20,1 (9,2 a 31,4)* / +14,7 (5,7 a 23,1) |

pp; * = significativo tras Holm en esa variante.

- **RCN · Justicia es lo más robusto.** Tiene el mismo signo y un IC sin el 0
  en todas las variantes, incluso sin restringir el periodo, desde 2021-05 y
  contando los «casi presentes». No tiene prueba con el denominador estricto
  porque con Duque hay sólo 19–33 eventos por celda. Las variantes con ese
  denominador dan Δ mayores (+13 a +35 pp) pero muy imprecisos.
- **Caracol · Venezuela tiene el signo robusto (+5 a +14 pp) y la
  significación frágil.** Pierde la significación sin restringir el periodo y,
  sobre todo, al contar como presentes los titulares casi emparejados (+5,0 pp,
  IC −1,2 a 10,8). Parte del cambio puede ser de redacción, no de cobertura: con
  Petro, más titulares de Caracol sobre Venezuela superan el umbral.
- **El Tiempo · Venezuela** es negativo en todas las variantes, pero sólo es
  significativo en una. Además está expuesto al techo: participa en el 81–83 %
  de esos eventos en los dos gobiernos.
- **La República · Venezuela no es robusto:** cambia de signo sin RCN y sin
  restringir el periodo.
- El cambio general de RCN de la tabla del README era un artefacto de fechas
  (26 % → 48 % sin restringir frente a 47 % → 48 % en la ventana).

## Cota de recall: ¿falta el medio o falta el emparejamiento?

Un medio «ausente» puede haber cubierto el hecho con un titular que no superó
0,80 o que no fue el recíproco. El recall del emparejamiento no está medido. Como
cota, para cada ausencia se buscó en `eventos/aristas.parquet` el titular de ese
medio más parecido a algún titular del núcleo (±2 días, similitud ≥ 0,60)
(`cota_recall.csv`):

| Medio | Ausencias con un titular ≥ 0,75 (Duque / Petro) | ≥ 0,70 | Con pareja ≥ 0,80 no usada | Participación general si ≥ 0,75 cuenta (Duque / Petro) |
|---|---:|---:|---:|---:|
| El Tiempo | 44 % / 54 % | 66 % / 73 % | 11 % / 23 % | 81 % / 88 % |
| Blu Radio | 45 % / 45 % | 63 % / 62 % | 19 % / 19 % | 79 % / 78 % |
| Noticias RCN | 33 % / 37 % | 49 % / 52 % | 12 % / 17 % | 65 % / 67 % |
| Noticias Caracol | 27 % / 32 % | 41 % / 46 % | 10 % / 16 % | 57 % / 63 % |
| La República | 12 % / 19 % | 20 % / 30 % | 4 % / 7 % | 25 % / 37 % |

En la calibración del paso 2, las parejas de 0,75–0,80 son el mismo hecho el
63 % de las veces y las de 0,60–0,75 cerca del 25 %. Así que «≥ 0,75» es una
cota alta y «≥ 0,70» una muy generosa. Conclusión: **una parte grande de la
«omisión» medida, de un cuarto a la mitad de las ausencias en los cuatro medios
generalistas, puede ser falta de recall.** Los **niveles** de participación no
deben leerse como cobertura real. Los Δ relativos resisten mejor, porque el
recall entra en los dos gobiernos y en todos los medios. Aun así, la
proporción de «casi presentes» sube con Petro en casi todos los medios, y por
eso Caracol · Venezuela pierde la significación con la cota.

## Limitaciones

- **Descriptivo, sin control.** No hay modelo de qué debió cubrir cada medio:
  la línea editorial (La República), el tamaño de la redacción, el formato
  (radio, TV, prensa) y la política de URL del archivo explican parte de los
  niveles.
- **Recall no medido** (sección anterior). La omisión es la cota superior de la
  ausencia real.
- **Precisión del 81 %:** cerca de una de cada cinco parejas del núcleo no es
  el mismo hecho. Eso añade ruido a la presencia, en principio parejo entre
  medios.
- **Titulares reconstruidos desde la URL** (sin tildes ni cifras): los
  titulares cortos o genéricos se emparejan peor, y esto afecta más a unos
  medios que a otros.
- **Ventana corta con Duque** (24 meses): poca potencia. Sólo 4 temas tienen
  prueba con el denominador estricto.
- **El tema del evento** es la moda de los tópicos de su núcleo. BERTopic
  asigna un tópico por titular, y los eventos mezclados caen en uno solo.
- **El techo y el piso** de la resta de porcentajes (sección de resultados).
- **El volumen de RCN** entre 2020-09 y 2021-04 es bajo (ver la decisión).
- El p-valor bootstrap no baja de 1/20.000. Con 20 o 75 pruebas, el mínimo
  ajustado por Holm es 0,001 o 0,004.

## Borrador para el artículo

> Para estudiar la omisión usamos los eventos cubiertos por al menos tres
> medios. El denominador de cada medio son los eventos en los que al menos tres
> de los otros cuatro estaban presentes, porque en un evento de tres medios
> ninguno de ellos puede «faltar». Como los titulares de Noticias RCN anteriores
> a septiembre de 2020 sólo tienen fecha mensual, el periodo de Duque se
> restringe a septiembre de 2020–agosto de 2022 (1.117 eventos, frente a 3.951
> con Petro). Los perfiles de cobertura son estables: La República casi no
> aparece en los hechos de orden público, justicia y conflicto (1–3 % de los
> eventos con Petro, unos 20 puntos por debajo de su media) y sí en los de
> impuestos y economía. Más allá del cambio general de cada medio y de lo que
> cambiaron los demás, sólo dos cambios entre gobiernos superan la corrección
> de Holm. Noticias Caracol aparece más en los hechos sobre Venezuela
> (+14 pp, IC 95 % 6–21). Noticias RCN aparece más en los de justicia
> (+7,5 pp, IC 3–13, con un denominador menos estricto). El segundo resiste
> todas las variantes de robustez. El primero pierde la significación si se
> cuentan como presentes los titulares que casi superaron el umbral de
> emparejamiento. Entre un cuarto y la mitad de las ausencias de los medios
> generalistas tienen un titular con similitud ≥ 0,75 con el evento, así que
> estas cifras describen la cobertura emparejable, no la cobertura total. No
> miden sesgo.

## Archivos

| Archivo | Contenido |
|---|---|
| `participacion.csv` | Por variante × gobierno × tema × medio: denominador, % que participa, % general, omisión específica con IC; en la principal, también el denominador ingenuo |
| `participacion_general.csv` | Participación general por variante, gobierno y medio, con Δ Petro − Duque e IC |
| `deltas.csv` | Por variante × tema × medio: Δ participación, Δ específico y Δ relativo con IC, p y p Holm; `citable` = False para T8 |
| `robustez_rcn.csv` | Δ relativo de cada medio × tema en todas las variantes (columnas `…__variante`), mismo signo y significación |
| `cota_recall.csv` | Ausencias por medio y gobierno y cuántas son «casi presentes» (≥ 0,75 / ≥ 0,70 / pareja ≥ 0,80 no usada) |
| `rcn_participacion_mensual.csv` | Participación mensual de RCN en el periodo completo (muestra el hueco) |
| `omision.json` | Cifras clave y los hallazgos con su robustez |
| `figuras/23_omision_especifica.png` | Mapa de calor tema × medio × gobierno de la omisión específica (principal, temas con n ≥ 15) |
| `figuras/24_omision_delta_relativo.png` | Δ relativo con IC por medio y tema, con los dos denominadores |
| `figuras/25_omision_robustez.png` | Participación general con y sin la ventana; hallazgos candidatos en cada variante |

Variantes: `principal` (≥3 de los otros 4, Duque desde 2020-09), `principal_k2`
(≥2 de los otros 4), `sin_restriccion[_k2]`, `desde_2021_05[_k2]`, `sin_rcn`,
`sin_rcn_ventana`, `recall_0.75[_k2]` y `recall_0.70[_k2]`.

## Reproducir

```bash
SCRIPT=omision.py ./run.sh - --output resultados_publico   # ~10 s; requiere eventos/ (eventos.py) y aristas.parquet
```

Opciones: `--min-eventos 30` (mínimo por celda para la inferencia),
`--min-heatmap 15` (temas en la figura 23), `--reps 20000` y `--seed 42`.
