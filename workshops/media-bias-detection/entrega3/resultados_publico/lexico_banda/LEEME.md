# Elección léxica en la banda 0,65–0,80: ¿el mismo hecho contado distinto?

Código: `lexico_banda.py` (reutiliza las funciones de `lexico.py`, `eventos.py` y
`calibracion.py` sin modificarlas). Tests: `tests/test_lexico_banda.py`.

```bash
SCRIPT=lexico_banda.py ./run.sh - --output resultados_publico     # ~1,5 min; figuras 33 a 35 en figuras/
```

**Resultado exploratorio.** El filtro que separa «el mismo hecho» acierta en
el 81 % de las parejas anotadas que pasan (13 de 16; IC 95 % de Wilson 57–93 %).
Ponderada por población la precisión es del 72 %, y la validación cruzada
anidada da 72 % (61–81 %). La cota inferior queda por debajo del 70 %, así que
estos resultados no tienen la misma solidez que los de ≥ 0,80
(`../lexico/LEEME.md`, 81 %, IC 72–90 %).

## Por qué

`lexico.py` mide las diferencias de redacción dentro de eventos con similitud
≥ 0,80. Ese umbral selecciona titulares redactados de forma parecida, así que el
encuadre muy distinto de un mismo hecho queda fuera y lo medido es una **cota
inferior**. En la banda 0,65–0,80 debería estar «el mismo hecho contado
distinto». Pero sin filtrar, sólo el **36 %** de sus parejas son el mismo hecho
(31 de 85 anotadas; IC 27–47 %). Es decir, la mayoría son **hechos distintos del
mismo tema**. Si se analizan tal cual, las diferencias de agenda se leen como
diferencias de encuadre. El diseño apunta a evitar ese error.

## Método

### 1. Unidad

- **Parejas recíprocas entre medios** con 0,65 ≤ sim < 0,80: cada titular es el
  más parecido del otro en el medio del otro, a ± 2 días y con fecha al día. Es
  el criterio de `eventos.reciprocal_pairs`, con las mismas exclusiones de
  plantilla.
- Quedan fuera las 2.673 parejas cuyos dos titulares ya están en **el mismo
  evento ≥ 0,80**. También salen 13 que cruzan el cambio de gobierno.
- Población: **55.384 parejas** (de 58.057 en la banda).
- Cada pareja es un «evento» de dos medios. Se usan sin cambios las funciones
  emparejadas de `lexico.py`: el medio se compara con **el otro medio de la
  pareja**.

### 2. Filtro de precisión

**Rasgos de cada pareja:**

- similitud;
- días de diferencia;
- mismo tópico de BERTopic;
- términos compartidos. Se calculan su IDF, su Jaccard ponderado y el número
  de **términos raros** compartidos. Un término es raro si aparece en ≤ 300,
  ≤ 1.000 o ≤ 3.000 de los 304 mil titulares. Casi siempre es un nombre propio,
  un lugar o una institución: «otoniel», «tuchín», «endeudamiento». Los slugs no
  conservan mayúsculas, así que no hay reconocimiento de entidades.

**Qué separa en las 85 parejas anotadas de la banda** (AUC, `lexico_banda.json`):

| Rasgo | AUC |
|---|---:|
| similitud | 0,67 |
| suma de IDF compartido | 0,79 |
| Jaccard ponderado | 0,79 |
| términos raros compartidos | 0,75 |
| misma fecha (0 días) | 61 % de «mismo hecho», frente a 24–32 % con 1–2 días |
| **mismo tópico** | **0,51: no sirve** (el 83 % de las parejas de la banda ya lo comparte) |

**Elección de la regla.** Se probó una rejilla de 42 reglas (`filtro_rejilla.csv`):
días de diferencia ≤ 0/1/2, ≥ 0/1/2 términos raros con tres cortes de rareza, y
con o sin el mismo tópico. Se eligió la de **mayor cota inferior de Wilson**, un
criterio que equilibra precisión y número de parejas, sin mirar ningún
resultado léxico. La regla elegida:

> **misma fecha + al menos un término compartido que aparece en ≤ 1.000
> titulares del corpus.**

Elegir la regla sobre las mismas 85 parejas con las que se mide infla la
precisión. Por eso se mide también la del **procedimiento completo** con
validación cruzada anidada: se elige en 4/5 de las parejas y se mide en el 1/5
restante, con 200 repeticiones. La misma regla gana en el 68 % de las
particiones.

**Precisión medida** (`precision_filtro.csv`, figura 33):

| Filtro | Pasan / anotadas | Precisión (Wilson IC 95 %) | Ponderada por población | Parejas en el corpus |
|---|---:|---:|---:|---:|
| sin filtro (toda la banda) | 85 / 85 | 36 % (27–47) | 36 % (26–45) | 55.384 |
| **regla (principal)** | 16 / 85 | **81 % (57–93)** | 72 % (47–98) | **13.741** |
| regla, validación cruzada anidada | — | **72 %** (percentiles 2,5–97,5: 61–81) | — | — |
| logístico p ≥ 0,5 (sensibilidad) | 29 / 85 | 66 % (47–80) | 61 % (42–81) | 20.045 |
| regla propuesta a priori: mismo tópico + ≤ 1 día + término raro | 22 / 85 | 68 % (47–84) | 65 % (44–86) | 17.462 |

- **Logístico.** Usa similitud, días, Jaccard ponderado, suma de IDF y términos
  raros. Se entrena con las 207 anotaciones de todos los tramos, con validación
  cruzada repetida: 5 partes × 20. Su AUC fuera de la muestra en la banda es
  0,77, y no supera a la regla.
- **Cobertura.** La regla recupera el 42 % de los «mismo hecho» de la banda y
  deja el 25 % de las parejas: 19 % en 0,65–0,70, 25 % en 0,70–0,75 y 32 % en
  0,75–0,80.
- **Errores que deja pasar** (sección 1 de `ejemplos_banda.md`): la misma persona
  en otra declaración, como «Embajador Plata pide perdón…» frente a otro
  perdón; «Canciller Marta Lucía Ramírez lista para empalme…» frente a «El
  mensaje de Marta Lucía Ramírez al nuevo canciller»; y la misma cumbre con otro
  presidente (Uruguay frente a México). **El error típico es el mismo actor en
  otro hecho del mismo día**, justo lo que no se puede excluir con rasgos léxicos.

**¿El filtro vuelve a seleccionar redacciones parecidas?** En parte sí
(`solapamiento_lexico.csv`). Jaccard de las palabras **no raras**:

| Conjunto | Jaccard de las palabras no raras |
|---|---:|
| ≥ 0,80 | 0,65 |
| banda filtrada | 0,52 |
| banda sin filtro | 0,44 |
| banda rechazada | 0,41 |

Las parejas filtradas comparten la entidad, pero el resto del titular se parece
bastante menos que en ≥ 0,80. Así que sí amplía hacia «contado distinto», aunque
no llega a los encuadres sin ninguna palabra rara en común.

### 3. Análisis léxico

- **Log-odds y criterios.** Log-odds de presencia con prior de Dirichlet
  informativo, α₀ = 100, con la tasa de fondo de los titulares únicos de la
  banda. Vocabulario: términos en ≥ 10 parejas (13.682). Los criterios son los
  de `lexico.py`: bootstrap por parejas (2.000), FDR q < 0,05, ≥ 10 parejas del
  medio y ≥ 5 discordantes, con clases formato / atribución / contenido.
- **Robusta**: además z ≥ 1,96 con bootstrap por meses y sin RCN como
  contraparte.
- **Comparación con ≥ 0,80** (`logodds_medio_gobierno.csv` de `lexico/`):
  - *nueva*: distintiva en la banda y no en ≥ 0,80;
  - *nueva estricta*: además, con ≥ 0,80 ni siquiera era nominalmente
    significativa (z < 1,96).
- **Diagnóstico de agenda.** Se repite el análisis en las **41.643 parejas que
  el filtro rechaza**, que en su mayoría son hechos distintos (~27 % de
  precisión). Un término que también separa al medio ahí (`tambien_en_rechazadas`,
  z ≥ 1,96) es un rasgo de la casa o de su agenda, no una forma de contar el
  mismo hecho.
- **Formas de nombrar al gobierno.** Se usan `formas_nombrar` y
  `proporciones_emparejadas` en parejas domésticas: sin los tópicos de otros
  países T2, T5, T13 y T16, en cualquiera de los dos titulares.
- **RCN en Duque**: sólo desde **2020-09**, por la misma decisión que en
  `lexico.py`.

## Resultados

### Palabras distintivas: casi nada nuevo, y lo nuevo es sobre todo estilo de la casa

Términos de contenido distintivos por celda (`resumen_celdas.csv`, figura 34):

| Medio | Duque: banda / ≥ 0,80 | Petro: banda / ≥ 0,80 | Nuevos estrictos y robustos (banda) |
|---|---:|---:|---|
| El Tiempo | 4 / 4 | 33 / 31 | Duque: «Iván Duque». Petro: «audiencia», «imputación», «Cepeda», «Iván Cepeda», «Álvaro», «Colombia», «sexual», «pensional», «norte» |
| Blu Radio | 0 / 3 | 1 / 6 | — |
| Noticias RCN | 0 / 0 | 0 / 3 | — |
| Noticias Caracol | 0 / 1 | 1 / 3 | — |
| La República | 3 / 6 | 0 / 4 | — («Gobierno nacional» en Duque, ya cerca de significativa con ≥ 0,80: z 2,6) |

- **Hay menos parejas por celda** (763 a 5.673) que eventos en ≥ 0,80. Eso da
  menos poder estadístico y menos términos distintivos, no más.
- **Lo que ya se veía se repite.** En El Tiempo · Petro, 17 de sus 33
  distintivas de contenido ya lo eran con ≥ 0,80. Son los nombres completos:
  «Gustavo Petro» (5,7 % frente a 2,0 %), «presidente Gustavo», «Donald Trump»,
  «Nicolás Maduro», «Abelardo de la Espriella» y «Gobierno Gustavo». Blu Radio
  repite «eeuu» y **evita** «Gustavo Petro» (1,5 % frente a 4,4 %, z −8,8) y
  «Donald Trump».
- **Lo nuevo es poco y casi todo aparece también en las parejas rechazadas.** De
  los 9 términos nuevos estrictos de El Tiempo · Petro, 7 también separan al
  medio en las parejas que son hechos distintos: «audiencia» 0,8 % frente a
  0,4 %, «imputación» 1,0 % frente a 0,6 %, «Cepeda» 0,8 % frente a 0,4 %. Es un
  léxico judicial y de actores más propio de la casa, o de su agenda, que de
  cómo cuenta un hecho concreto.
- Sólo «pensional» (0,5 % frente a 0,3 %; z 3,3) y «norte» (de Santander) no
  aparecen en las rechazadas. Son pocos casos y de contenido temático, sin
  lectura de encuadre clara.
- **Ningún verbo de atribución ni adjetivo valorativo** aparece como distintivo
  nuevo.
- «viene» (El Tiempo · Petro, «qué viene / lo que viene») es un formato
  explicativo de la casa, como «claves». No está en la lista de formato de
  `lexico.py` y no se tocó.

**Concordancia de los δ** (Spearman sobre los términos comunes):

| Comparación | Spearman |
|---|---:|
| banda filtrada frente a ≥ 0,80 | 0,18–0,39 (con conteos chicos, mucho ruido) |
| frente a la banda sin filtro | 0,60–0,68 |
| frente al filtro logístico | 0,76–0,83 |
| Duque, ventana común | 0,69–0,78 |

**Robustez de las distintivas** (porcentaje que mantiene z ≥ 1,96):

| Prueba | % que se mantiene |
|---|---:|
| bootstrap por meses | 100 % |
| sin RCN como contraparte | 97–100 % |
| ventana común en Duque | 100 % |
| sin filtro | 67–100 % |

### Personalización del gobierno: se mantiene, y en El Tiempo se acentúa

Índice de personalización del gobierno: entre los titulares que dicen
«Gobierno Petro/Duque», «Gobierno nacional» o «Gobierno» sin más, % con el
apellido. La tabla da el del medio **menos el del otro medio de la pareja**, en
pp, con IC 95 % por bootstrap de parejas (`personalizacion_comparada.csv`,
figura 35).

| Medio | Petro, ≥ 0,80 | Petro, banda filtrada | Petro, filtrada sin RCN | Petro, sin filtro | Duque, banda filtrada |
|---|---:|---:|---:|---:|---:|
| El Tiempo | +11,2 (7,5 a 15,0) | **+15,2 (10,6 a 19,8)** | +14,1 (9,0 a 19,6) | +13,5 (11,2 a 15,8) | +0,2 (−3,6 a 3,9) |
| Blu Radio | −5,1 (−9,2 a −1,4) | **−8,3 (−12,8 a −4,0)** | −10,9 (−16,1 a −5,9) | −6,8 (−9,3 a −4,3) | −2,7 (−6,9 a 1,2) |
| Noticias RCN | −12,7 (−16,9 a −8,4) | **−8,4 (−13,5 a −3,3)** | — | −8,0 (−10,9 a −5,2) | −3,4 (−9,0 a 0,1) |
| Noticias Caracol | +7,3 (1,8 a 12,7) | +2,4 (−4,0 a 9,7) | −1,8 (−8,9 a 5,6) | +5,3 (1,8 a 8,7) | +4,9 (−0,9 a 10,8) |
| La República | −7,9 (−12,8 a −2,9) | **−6,7 (−11,8 a −1,6)** | −6,6 (−13,1 a −0,4) | −11,1 (−14,2 a −7,8) | +0,7 (−3,0 a 4,8) |

- **El patrón de ≥ 0,80 se replica en la banda filtrada.** En Petro, El Tiempo
  personaliza más que el otro medio ante el mismo hecho, y Blu Radio, RCN y La
  República menos. En Duque ningún IC excluye el 0.
- El signo y la significación se mantienen sin RCN como contraparte y con el
  filtro logístico: El Tiempo +15,0, Blu −6,7, RCN −10,2, La República −10,5.
- **Caracol (Petro) sigue sin ser robusto**: +2,4, con un IC que cruza el 0, como
  ya pasaba sin RCN con ≥ 0,80.
- **Cambio Duque → Petro** en los titulares de las parejas filtradas
  (`formas_nombrar.csv` y `formas_nombrar_cambio.csv`; IC de Newcombe):

  | Medio | Duque | Petro | Cambio |
  |---|---:|---:|---:|
  | El Tiempo | 3,7 % | 25,9 % | +22,2 pp (16,1 a 27,0) |
  | Blu Radio | 5,4 % | 11,0 % | +5,5 (0,3 a 9,7) |
  | Noticias Caracol | 10,8 % | 20,0 % | +9,2 (0,4 a 17,1) |
  | Noticias RCN | 2,3 % | 9,3 % | +7,0 (−3,0 a 11,6; n = 44 en Duque) |
  | La República | 2,9 % | 8,1 % | +5,3 (−0,8 a 10,7) |

  Sube en los cinco medios, como con ≥ 0,80.
- Hay 110 parejas de Petro en las que un medio escribe «Gobierno Petro» y el
  otro «el Gobierno» (frente a 9 de Duque). Por ejemplo: «Gobierno Petro y
  disidencias de Iván Mordisco logran acuerdo…» (El Tiempo) frente a «Gobierno y
  disidencias de las FARC de Iván Mordisco logran acuerdo…» (Caracol). Hay más
  en la sección 3 de `ejemplos_banda.md`.
- **Advertencia sobre la banda sin filtro.** En Duque aparecen diferencias
  pequeñas pero «significativas»: El Tiempo +3,0, Blu −3,3 y RCN −3,6 pp. No se
  ven ni con ≥ 0,80 ni con el filtro. Es justo el riesgo señalado: con dos
  tercios de hechos distintos, la agenda se cuela como si fuera redacción.

## Qué cambia respecto a ≥ 0,80

1. **No aparecen palabras de encuadre nuevas que sean robustas.** Ampliar a
   «misma entidad, otra redacción» no destapa diferencias léxicas sistemáticas
   de contenido entre medios. Las pocas nuevas son de El Tiempo y separan al
   medio también en hechos distintos: son estilo o agenda de la casa.
2. **La personalización se mantiene** con el mismo signo en El Tiempo, Blu Radio,
   RCN y La República, y en Duque sigue sin diferencias. La magnitud de El Tiempo
   sube (+15 frente a +11 pp, con IC solapados) y la de RCN baja (−8 frente a
   −13 pp).
3. La conclusión de `lexico.py` (diferencias pequeñas y de estilo, salvo la
   personalización del gobierno) **no parece un artefacto del umbral 0,80**, al
   menos hasta donde llega un filtro con un 70–80 % de precisión.

## Limitaciones

- **Precisión del filtro**: 81 % en la muestra (IC 57–93 %), 72 % fuera de la
  muestra. Entre una de cada cuatro y una de cada cinco parejas filtradas no es
  el mismo hecho. La medida se apoya en sólo 16 parejas anotadas que pasan el
  filtro: 2, 5 y 9 por tramo. **La ponderación por tramo es muy inestable** (IC
  47–98 %).
- **El filtro exige una palabra rara compartida y la misma fecha.** Deja fuera
  los encuadres que no comparten ninguna entidad y las notas del día siguiente.
  La cota sigue siendo inferior, aunque menos estrecha que con ≥ 0,80.
- **El error típico (mismo actor, otro hecho del mismo día) no se puede
  filtrar con rasgos léxicos.** Haría falta anotar más parejas de la banda o
  leer el cuerpo de la nota.
- **Las anotaciones son de un anotador por pareja** (Anotador 1, como
  `calibracion.py`). El kappa de la calibración es 0,77.
- **Diseño en parejas.** Cada comparación es medio frente a medio, no frente al
  resto. Un titular puede estar en hasta cuatro parejas. El bootstrap por meses
  cubre esa dependencia.
- Son titulares reconstruidos desde la URL, como en `lexico.py`. La lista de
  formato es la de `lexico.py`, sin cambios («viene» queda como contenido).
- Nada de esto mide veracidad ni sesgo ideológico.

## Archivos

| Archivo | Contenido |
|---|---|
| `precision_filtro.csv` | precisión de cada filtro: Wilson, ponderada por población, por tramo y recall |
| `filtro_rejilla.csv` | las 42 reglas probadas con su precisión y la elegida |
| `anotadas_banda.csv` | las 85 parejas anotadas de la banda con rasgos, etiqueta, si pasan cada filtro y p del logístico |
| `solapamiento_lexico.csv` | Jaccard (todas las palabras y no raras) en ≥ 0,80, banda, filtrada y rechazada |
| `logodds_banda.csv` | δ, z, IC, q, z por meses, sin RCN y ventana; δ y z en ≥ 0,80, sin filtro, rechazadas y logístico; `nueva`, `nueva_estricta`, `tambien_en_rechazadas` |
| `palabras_nuevas.csv` | términos de contenido distintivos en la banda y no en ≥ 0,80 |
| `resumen_celdas.csv` | recuentos por celda, Spearman frente a ≥ 0,80 y variantes, % robustas |
| `formas_nombrar_emparejado.csv` | formas de nombrar, medio frente al otro medio: filtrada, sin filtro y logístico; todos, sin RCN y ventana común |
| `formas_nombrar.csv`, `formas_nombrar_cambio.csv` | proporciones (Wilson) y cambio Duque → Petro (Newcombe) en la banda filtrada |
| `personalizacion_comparada.csv` | índice de personalización: ≥ 0,80 frente a las variantes de la banda |
| `tamanos.csv` | parejas por variante, gobierno y medio |
| `lexico_banda.json` | parámetros, filtro (regla, precisión, validación anidada, AUC, coeficientes), resumen y cifras clave |
| `ejemplos_banda.md` | anotadas que pasan el filtro, palabras nuevas, «Gobierno Petro» frente a «el Gobierno», misma entidad con otra redacción |
| `figuras/33`–`35` | precisión del filtro, palabras distintivas en la banda, personalización comparada |

## Borrador para el artículo

> Como el emparejamiento con similitud ≥ 0,80 favorece titulares redactados de
> forma parecida, repetimos el análisis con las parejas recíprocas de similitud
> 0,65–0,80, donde debería estar el mismo hecho contado de otra manera. Sin
> filtrar, sólo el 36 % de esas parejas son el mismo hecho según la anotación
> manual. Por eso nos quedamos con las publicadas el mismo día que comparten al
> menos un término raro (un nombre propio, un lugar o una institución), una
> regla elegida sobre las anotaciones. Su precisión es del 81 % (IC 95 % 57–93 %)
> y del 72 % en validación cruzada anidada, por lo que tratamos el resultado como
> exploratorio. En esas 13.741 parejas no aparecen palabras de encuadre nuevas
> que sean robustas: las pocas distintivas que no salían con ≥ 0,80 separan al
> medio también en parejas de hechos distintos, así que son rasgos de estilo o de
> agenda de la casa. La personalización del gobierno, en cambio, se mantiene. En
> el gobierno Petro, El Tiempo escribe «Gobierno Petro» 15 puntos más que el
> otro medio ante el mismo hecho (IC 95 % 11–20), mientras que Blu Radio (−8),
> Noticias RCN (−8) y La República (−7) prefieren «el Gobierno». En el gobierno
> Duque no hay diferencias. Esto sugiere que la conclusión principal no es un
> artefacto del umbral de similitud.
