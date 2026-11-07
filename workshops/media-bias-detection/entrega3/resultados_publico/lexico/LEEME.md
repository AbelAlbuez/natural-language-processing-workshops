# Elección léxica dentro del mismo hecho

Código: `lexico.py`. Datos: los eventos de `eventos.py` (titulares de medios
distintos sobre el mismo hecho, umbral calibrado 0,80, precisión 81 %, IC 95 %
72–90 %). Al fijar el hecho, si un medio usa una palabra más que los otros, eso
ya no se explica por la agenda (de qué se habla) sino por cómo se cuenta.

```bash
SCRIPT=lexico.py ./run.sh - --output resultados_publico     # ~1 min; figuras 26 a 29 en figuras/
```

## Método

**Unidad y diseño emparejado.** Para cada medio *m* y gobierno, se toman los
eventos en los que está *m* y al menos otro medio. Se compara el titular de *m*
con los titulares de **los otros medios en esos mismos eventos**, no con todo el
corpus. Cada evento pesa uno en cada lado: si hay tres medios más, sus titulares
se promedian dentro del evento. Principal: titulares núcleo (uno por medio y
evento, `es_seguimiento = False`). Robustez: con las notas de seguimiento, que
también se promedian dentro del evento y del medio.

**Términos.** Unigramas y bigramas (sobre la secuencia ya sin stopwords) del
titular normalizado con `core.tokenize`. Stopwords de NLTK y de dominio
(`stopwords_dominio.txt`, como en `topics.py`). Los actores no se quitan. Los
marcadores de formato que esa lista sí quita («video», «vivo», «así»…) se dejan
**para poder marcarlos**. Vocabulario: términos en ≥10 eventos distintos (6.726).

**Log-odds con prior de Dirichlet informativo** (Monroe, Colaresi y Quinn 2008),
en versión de **presencia por titular**. *y* = eventos en los que el titular
lleva el término (en los otros medios, la fracción de sus titulares). *n* =
número de eventos, igual en los dos lados. Prior: α₀ = 100 titulares ficticios,
con la tasa de fondo del término en todos los titulares núcleo (cinco medios, dos
gobiernos). δ > 0 quiere decir que el medio usa el término más que los otros al
contar el mismo hecho.
*Por qué presencia y no tokens:* con conteos de tokens, δ arrastra el término
log(n_otros / n_medio), que sólo depende de la longitud de los titulares. Una
palabra usada exactamente igual en los mismos eventos recibía un δ pequeño y
constante. El bootstrap lo daba como «significativo» (z de 15 con δ = +0,07)
porque los dos lados se mueven a la vez. Con presencia, el mismo uso da δ = 0
exacto (hay un test que lo comprueba).

**Inferencia robusta a la dependencia.**
- Bootstrap **por eventos** (2.000 réplicas): error estándar e IC 95 % de δ,
  z = δ / EE.
- Robustez con bootstrap **por meses** (se remuestrean los meses de inicio de los
  eventos, por si eventos del mismo mes no son independientes).
- **FDR de Benjamini-Hochberg** dentro de cada celda medio × gobierno (q < 0,05).
  Holm (`p_holm`) se reporta aparte: con 400–3.200 términos por celda casi no deja
  nada.

**Criterios.**
- *Distintiva*: δ > 0, q < 0,05, el medio la usa en ≥10 eventos y en ≥5 eventos
  la usa sólo él (eventos discordantes).
- *Evitada*: lo simétrico.
- *Robusta*: distintiva y además z ≥ 1,96 con bootstrap por meses, con
  seguimiento y sin RCN entre los otros medios (esta última no se aplica a RCN).

**Formato frente a encuadre.** Cada término lleva una `clase`:
- **formato**: programas y autorreferencias («Mañanas Blu», «reviva aquí los
  goles», «cotización divisa TRM»); firmas de columnas; «en vivo», «claves»,
  «atención»; artefactos del slug («por ciento», «elecciones usa»). También
  cualquier término que en ≥50 % de sus usos va junto a una marca de firma o
  programa (así se marca «Ricardo Ospina», de «opinión de Ricardo Ospina»).
- **atribución**: verbos que introducen lo que dice una fuente («afirmó»,
  «confirmó», «denunció»).
- **contenido**: el resto.

La lista de formato se amplió **después de ver los primeros resultados**: la
mayoría de los términos «exclusivos» de un medio eran secciones fijas. Las marcas
de formato a nivel de titular (preguntas, «qué se sabe», videos, «en vivo»,
«última hora», opinión) se comparan aparte, en `formato_titulares.csv`. No se usa
análisis de sentimiento.

**Formas de nombrar al gobierno y al presidente** (`formas_nombrar`, simétrica:
el apellido es el del presidente de *ese* gobierno). Las formas:

- «Gobierno Petro/Duque», incluido «Gobierno de (Gustavo) Petro»;
- «presidente Petro/Duque»;
- «Gustavo Petro» / «Iván Duque»;
- el apellido solo;
- «Gobierno nacional/colombiano»;
- «Gobierno» sin más, excluyendo «gobierno de…», gentilicios, gobiernos locales y
  nombres de otros mandatarios;
- «mandatario» / «jefe de Estado»;
- «Ejecutivo», excluyendo «presidente ejecutivo» y «director ejecutivo»;
- «Casa de Nariño»;
- «Presidencia de la República»;
- ministro(a), incluidas abreviaturas como «MinHacienda».

Se miden en titulares núcleo de **eventos domésticos**: se excluyen los tópicos
de BERTopic sobre otros países (T2, T5, T13 y T16), donde «Gobierno» suele ser
un gobierno extranjero. Dos índices:

- **personalización del gobierno** = «Gobierno + apellido» / (titulares con
  «Gobierno + apellido», «Gobierno nacional» o «Gobierno» sin más);
- **personalización del Ejecutivo** = titulares que nombran al presidente /
  titulares con cualquier referencia al Ejecutivo.

Las proporciones de cada medio llevan IC de Wilson. El cambio Duque → Petro lleva
IC de Newcombe. La diferencia frente a los otros medios en los mismos eventos se
calcula como cociente de sumas sobre los eventos, con bootstrap por eventos.

## Decisión sobre Noticias RCN

En el subcorpus público, RCN **no tiene ningún titular con fecha al día antes de
octubre de 2019** (`rcn_precision_fecha.csv`). Entre 2019-10 y 2020-08 la tiene
sólo para el 38–55 % de sus titulares cada mes (salvo el 90 % de octubre de
2019). **Desde 2020-09 la tiene de forma sostenida: ≥80 % todos los meses**,
casi siempre 94–98 %. El emparejamiento exige fecha al día, así que los
titulares de RCN de 2018–2019 no entran a ningún evento. Los de 2019-10 a
2020-08 que sí entran son una submuestra seleccionada por el formato de la URL.

**Decisión:** en las comparaciones de RCN en el gobierno Duque se usan sólo los
eventos desde **2020-09** (umbral `--rcn-min-dia 0,75`, sostenido hasta el fin
del gobierno). Son 1.935 de sus 2.247 eventos de Duque (802 con ≥3 medios), y
2.246 titulares núcleo de RCN quedan en 1.935.
**Advertencia:** el perfil de RCN en Duque sale sólo de 2020-09 a 2022-08: la
pandemia, el paro nacional de 2021 y la campaña de 2022, con una agenda atípica.
Su cambio Duque → Petro compara ese tramo con todo el gobierno Petro.

Dos controles:

- **Sin RCN entre los otros**: se repite cada comparación de los otros cuatro
  medios quitando a RCN del lado «otros» (columnas `*_sinrcn`,
  `robustez_sin_rcn*.csv`).
- **Ventana común**: Duque recortado a 2020-09–2022-08 para todos los medios
  (`delta_ventana` y la ventana `comun` en `formas_nombrar_cambio.csv`).

### Tamaños (titulares núcleo; `tamanos.csv`)

| Medio | Gobierno | Eventos | con ≥3 medios | Titulares núcleo | Seguimiento | Eventos domésticos | Palabras por titular (medio / otros) |
|---|---|---:|---:|---:|---:|---:|---|
| El Tiempo | Duque | 5.253 | 1.690 | 5.253 | 2.487 | 3.540 | 10,3 / 12,1 |
| Blu Radio | Duque | 4.864 | 1.633 | 4.864 | 868 | 3.394 | 12,2 / 11,4 |
| Noticias RCN | Duque (todo) | 2.247 | 951 | 2.247 | 255 | 1.579 | 11,8 / 11,6 |
| **Noticias RCN** | **Duque desde 2020-09** | **1.935** | **802** | **1.935** | **234** | **1.361** | 11,9 / 11,7 |
| Noticias Caracol | Duque | 3.304 | 1.342 | 3.304 | 513 | 2.333 | 12,6 / 11,4 |
| La República | Duque | 1.561 | 665 | 1.561 | 273 | 918 | 12,2 / 11,0 |
| El Tiempo | Petro | 10.215 | 3.532 | 10.215 | 3.923 | 6.928 | 14,9 / 13,0 |
| Blu Radio | Petro | 8.089 | 3.156 | 8.089 | 1.529 | 5.727 | 13,1 / 13,8 |
| Noticias RCN | Petro | 5.978 | 2.733 | 5.978 | 1.120 | 4.122 | 12,5 / 13,7 |
| Noticias Caracol | Petro | 5.404 | 2.604 | 5.404 | 920 | 3.613 | 13,7 / 13,5 |
| La República | Petro | 2.844 | 1.377 | 2.844 | 648 | 1.751 | 12,3 / 13,4 |

Los slugs de El Tiempo en Duque son más cortos (10,3 palabras frente a 12,1 de
los otros medios en los mismos eventos). Con presencia por titular, eso empuja
sus δ hacia abajo: muchas de sus palabras «evitadas» en Duque («acusó»,
«experto», «abren») son palabras que los otros usan y que no caben en un slug
corto.

## Resultados

### 1. Palabras distintivas: pocas, y casi todas de estilo

Con el diseño emparejado, **las diferencias léxicas entre medios ante el mismo
hecho son pequeñas**. Entre 1 y 41 términos distintivos por celda, sobre 362 a
3.193 evaluados (`robustez_sin_rcn.csv`). En Duque hay 1–8 por medio, y en RCN
Duque y Caracol Duque ninguno de contenido robusto. Casi todos los distintivos
superan las tres pruebas de robustez:

- z ≥ 1,96 con bootstrap por meses: 100 % (salvo Caracol Duque, 1 de 2);
- con seguimiento: 100 %;
- sin RCN entre los otros: 93–100 %.

La correlación de Spearman de δ entre la versión principal y cada robustez es:

- con seguimiento: 0,95–0,97;
- sin RCN: 0,89–0,96;
- ventana común en Duque: 0,68–0,78. Más baja, como cabe esperar con la mitad de
  los eventos.

Términos de **contenido** distintivos (% de titulares del medio / % de los otros
en los mismos eventos):

| Medio | Duque | Petro |
|---|---|---|
| El Tiempo | elecciones 6,1/4,9 · venezuela 13,9/12,8 · colombia 12,1/11,3 | **donald trump 3,2/1,3 · gustavo petro 4,8/2,6 · presidente gustavo 3,2/1,8 · nicolas maduro 2,2/1,2** · estados unidos 10,5/8,5 |
| Blu Radio | eeuu 0,6/0,1 · santander 1,0/0,5 · presunta corrupción 0,6/0,3 | eeuu 1,6/0,1 · precio dólar 0,6/0,1 · gobierno 10,5/9,3 · santander, bucaramanga |
| Noticias RCN | — | panorama 0,4/0,1 · abrió 0,9/0,4 · cuánto 0,9/0,4 |
| Noticias Caracol | general 2,1/1,5 | disidencias farc 1,6/1,0 · trump 5,0/4,5 · eps 0,6/0,4 |
| La República | tasa 3,1/1,5 · tasa desempleo 1,7/0,6 · millones · próximo | debate reforma 1,8/1,0 · radicó 0,8/0,3 · venezolana · próximo |

Lectura prudente:

- **El Tiempo (Petro) escribe nombres completos.** «Donald Trump», «Gustavo
  Petro», «Nicolás Maduro» y «Abelardo de la Espriella» salen distintivos. El
  control `nombre_completo_actores.csv` lo confirma como **convención de la
  casa**, no como algo específico del presidente. Entre los titulares de El
  Tiempo que mencionan el apellido, llevan el nombre de pila el 75 % de los de
  Trump (IC 71–79 %), el 67 % de los de Maduro (62–72 %) y el 39 % de los de
  Petro (37–42 %).
- **Blu Radio es lo contrario: formas cortas.** Escribe «EE. UU.» como «eeuu»
  (1,6 % frente a 0,1 %) y evita «Gustavo Petro» (1,6 % frente a 3,7 %) y
  «Donald Trump». Lleva el nombre de pila el 14 % de sus titulares con «Petro»
  (12–16 %), el 21 % de los de Trump y el 29 % de los de Maduro; en Duque, el
  21 % con «Duque». Es un patrón estable de redacción.
- **La República** tiene un léxico económico y legislativo: «tasa de
  desempleo», «millones», «radicó», «debate de la reforma». Es su perfil de
  medio económico, no un encuadre político.
- **Formato**: muchas palabras distintivas son de formato o de secciones fijas y
  se excluyen de la figura 26. Las marcas de formato a nivel de titular
  (`formato_titulares.csv`) también separan a los medios:
  - La República casi no titula con preguntas: −3,0 pp frente a los otros en los
    mismos eventos, en los dos gobiernos;
  - RCN (+1,7 pp) y Caracol (+1,3 pp) titulan más con preguntas en Petro;
  - El Tiempo usa más «atención/última hora» (+1,4 pp) y «claves» en Petro.

**Cambio Duque → Petro** (`logodds_cambio_duque_petro.csv`, figura 27). Hay
pocos cambios con q < 0,05: 33 en El Tiempo (muchos son el efecto de los slugs
cortos de Duque), 11 en La República, 6 en Blu Radio, 3 en Caracol y 2 en RCN.
Los de contenido repiten lo anterior:

- El Tiempo pasa a usar más que los otros «Gustavo Petro», «presidente» y
  «gobierno»;
- Blu Radio, menos «Gustavo Petro»;
- La República, menos «Donald Trump», «Estados Unidos» y «gobierno».

**Por tema** (`logodds_tema.csv`): 94 celdas medio × gobierno × tema con ≥150
eventos del medio, sin T8 ni fútbol residual. Hay 100 términos distintivos en
total. La mayoría repiten los patrones generales dentro del tema: nombres
completos en El Tiempo, «eeuu» y «precio del dólar» en Blu, «debate reforma» en
La República (reforma a la salud) y «EPS» en Caracol (reforma a la salud). No
aparece ningún encuadre temático nuevo que sea robusto.

### 2. Cómo se nombra al gobierno: la personalización sube con Petro en todos los medios

**Personalización del gobierno**: entre los titulares que nombran al gobierno
nacional, % con el apellido. IC 95 % de Wilson.

| Medio | Duque | Petro | Cambio (IC 95 % Newcombe) | Cambio con ventana común |
|---|---:|---:|---:|---:|
| El Tiempo | 5,1 % (2,9–8,8; n = 217) | 26,9 % (23,6–30,3; n = 670) | +21,8 pp (16,8 a 25,9) | +22,6 pp |
| Blu Radio | 5,4 % (3,2–8,9; n = 259) | 17,0 % (14,2–20,1; n = 624) | +11,6 pp (7,2 a 15,4) | +12,1 pp |
| Noticias RCN* | 3,9 % (1,4–11,0; n = 76) | 12,1 % (9,2–15,7; n = 381) | +8,1 pp (0,5 a 12,6) | (igual) |
| Noticias Caracol | 7,6 % (4,4–12,9; n = 157) | 28,4 % (23,8–33,6; n = 327) | +20,8 pp (13,8 a 26,8) | +19,5 pp |
| La República | 6,6 % (3,4–12,4; n = 122) | 10,7 % (7,3–15,3; n = 234) | +4,1 pp (−2,6 a 9,7) | +5,9 pp (−3,1 a 11,5) |

\* RCN en Duque sólo desde 2020-09.

**Personalización del Ejecutivo** (nombra al presidente entre los titulares que
se refieren al Ejecutivo):

| Medio | Duque | Petro |
|---|---:|---:|
| El Tiempo | 45 % | 67 % |
| Blu Radio | 42 % | 60 % |
| Noticias RCN | 42 % | 56 % |
| Noticias Caracol | 47 % | 71 % |
| La República | 35 % | 48 % |

Sube en los cinco medios; todos los IC del cambio excluyen el 0. «Presidente +
apellido» pasa del 1,7–4,4 % al 6,2–8,6 % de los titulares de eventos domésticos.
Hay 191 eventos de Petro en los que un medio escribe «Gobierno Petro» y otro
«Gobierno» o «Gobierno nacional», frente a 9 de Duque.
**El aumento es común a todos los medios y sobrevive a la ventana común**, así
que es un rasgo del periodo, del presidente y de su comunicación, más que de un
medio.

**Frente a los otros medios en los mismos eventos** (índice del medio menos el
de los otros, pp, IC 95 % por bootstrap de eventos; figura 29):

| Medio | Duque | Petro | Petro, sin RCN entre los otros |
|---|---:|---:|---:|
| El Tiempo | −1,5 (−4,4 a 1,5) | **+11,2 (7,5 a 15,0)** | **+9,0 (4,6 a 13,4)** |
| Blu Radio | −1,2 (−4,4 a 1,9) | **−5,1 (−9,2 a −1,4)** | **−8,0 (−12,6 a −3,4)** |
| Noticias RCN | +0,5 (−3,6 a 4,8) | **−12,7 (−16,9 a −8,4)** | — |
| Noticias Caracol | +1,3 (−2,0 a 4,8) | +7,3 (1,8 a 12,7) | +5,3 (−0,7 a 11,4) |
| La República | +3,0 (−0,4 a 7,1) | **−7,9 (−12,8 a −2,9)** | **−11,7 (−16,9 a −6,3)** |

- **En Duque ningún medio se distingue** de los otros al nombrar al gobierno:
  todos los IC cruzan el 0.
- **En Petro los medios se separan.** Ante el mismo hecho, El Tiempo escribe
  «Gobierno Petro» más que los demás. RCN, La República y Blu Radio escriben más
  «Gobierno» o «Gobierno nacional». Son robustos sin RCN entre los otros.
- Caracol (+7,3 pp) no es robusto: sin RCN, el IC cruza el 0.
- RCN es el que menos personaliza: −12,7 pp. También evita «Gobierno Petro»
  como término (0,8 % de sus titulares frente al 1,4 % de los otros) y «Petro»
  (8,9 % frente a 11,5 %).

Hay dos lecturas posibles de que un medio diga «Gobierno Petro» en vez de «el
Gobierno». Puede atribuir las decisiones al presidente, ya sea para marcarlas
como suyas o para distanciarse. O puede ser un hábito de redacción, como en El
Tiempo, que usa nombres completos con todos. Con titulares reconstruidos no se
distinguen. Lo que sí se sostiene es que la diferencia **aparece en Petro y no
en Duque, con los mismos medios**.

## Limitaciones

- **Titulares reconstruidos desde la URL**: sin tildes, cifras, comillas ni
  mayúsculas, y a veces truncados. Los de El Tiempo en Duque son más cortos, lo
  que sesga sus δ hacia abajo. «Mandatario», «Ejecutivo», «Casa de Nariño» y
  «Presidencia» casi no aparecen (≤0,3 %), quizá porque el slug los recorta.
- **Emparejamiento con precisión del 81 %** (IC 72–90 %): cerca de uno de cada
  cinco pares no es el mismo hecho. Esas parejas añaden diferencias de agenda,
  que el diseño emparejado no controla del todo.
- **Sesgo de selección del emparejamiento**: los eventos se forman con similitud
  de embeddings ≥ 0,80, así que favorecen titulares redactados de forma
  parecida. Los encuadres muy distintos del mismo hecho tienden a no
  emparejarse. Las diferencias léxicas medidas aquí son **una cota inferior**.
- **RCN en Duque**: sólo 2020-09–2022-08 (1.935 eventos); periodo atípico
  (pandemia, paro, campaña). Para personalizar, sólo 76 titulares con «gobierno»:
  IC amplio.
- **Detección por expresiones regulares**: «Gobierno» sin más puede ser a veces
  un gobierno extranjero o local no listado. «Gobierno de Duque» incluye
  construcciones como «primer año de gobierno de Duque». Los ministros se
  detectan por el cargo, no por el nombre: «Armando Benedetti radicó…» no cuenta
  como forma de nombrar al gobierno.
- **La lista de formato se revisó a la vista de los resultados**: es una
  decisión documentada (`FORMATO`, `CONTAGIO`, `UMBRAL_CONTAGIO_FORMATO`), no un
  criterio ciego.
- **Inferencia**: FDR y no error familiar; los z de términos que sólo usa un
  medio (0 eventos de los otros) son grandes y sensibles al prior. Para estos
  términos, lo que importa es el recuento de eventos (`n_solo_medio`).
- Nada de esto mide la veracidad ni el sesgo ideológico de un medio. Mide
  diferencias de redacción ante el mismo hecho.

## Archivos

| Archivo | Contenido |
|---|---|
| `logodds_medio_gobierno.csv` | δ, z, IC, q, robustez (`z_mes`, `z_seg`, `z_sinrcn`, `z_ventana`), clase y eventos por término, medio y gobierno |
| `logodds_cambio_duque_petro.csv` | cambio de δ por medio y término, con IC y q |
| `logodds_tema.csv`, `tamanos_tema.csv` | lo mismo por tema de BERTopic (≥150 eventos del medio) |
| `formas_nombrar.csv` | proporción de cada forma por medio × gobierno, IC de Wilson; `ventana` = principal / común |
| `formas_nombrar_emparejado.csv` | medio frente a los otros en los mismos eventos, con y sin RCN, IC por bootstrap |
| `formas_nombrar_cambio.csv` | cambio Duque → Petro, IC de Newcombe, ventana principal y común |
| `nombre_completo_actores.csv` | % con nombre de pila para Petro, Duque, Trump, Maduro, Uribe, Biden, Benedetti |
| `formato_titulares.csv` | marcas de formato a nivel de titular, emparejado |
| `robustez_sin_rcn.csv`, `robustez_sin_rcn_formas.csv` | resumen de robustez |
| `tamanos.csv`, `rcn_precision_fecha.csv` | tamaños y fecha al día de RCN por mes |
| `lexico.json` | parámetros y cifras clave |
| `ejemplos_lexico.md` | eventos reales con los titulares de cada medio lado a lado |
| `figuras/26`–`29` | palabras distintivas, cambio, formas de nombrar, personalización |

## Borrador para el artículo

> Para separar el encuadre de la agenda comparamos, dentro de cada evento, el
> titular de un medio con los de los otros medios que cubrieron el mismo hecho
> (log-odds con prior de Dirichlet informativo sobre la presencia de cada
> término; inferencia por bootstrap de eventos y FDR). Las diferencias léxicas
> resultan pequeñas y en su mayoría de estilo: El Tiempo escribe nombres
> completos («Gustavo Petro», «Donald Trump») con todos los actores, Blu Radio
> usa formas abreviadas («EE. UU.», «Petro») y La República, léxico económico.
> El contraste más claro está en cómo se nombra al gobierno. Entre los titulares
> que mencionan al gobierno nacional, la forma con el apellido («Gobierno
> Petro») pasa del 4–8 % con Duque al 11–28 % con Petro en los cinco medios, un
> aumento que se mantiene al restringir el periodo de Duque a 2020–2022. Con
> Duque ningún medio se aparta de los demás ante el mismo hecho. Con Petro, El
> Tiempo personaliza 11 puntos más que los otros medios en los mismos eventos
> (IC 95 % 7,5–15,0), mientras que Noticias RCN (−12,7; −16,9 a −8,4), La
> República (−7,9) y Blu Radio (−5,1) prefieren «el Gobierno». Estas cifras
> describen elecciones de redacción en titulares reconstruidos desde la URL,
> sobre eventos emparejados con una precisión del 81 %; no permiten atribuir
> intención ni medir el sesgo ideológico de cada medio.
