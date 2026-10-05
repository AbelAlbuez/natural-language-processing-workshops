# Entrega 2: resumen ejecutivo verificado

**Proyecto:** Analisis exploratorio del corpus Duque para estudiar sesgo editorial.

**Institucion:** Pontificia Universidad Javeriana, Maestria en Inteligencia Artificial (identificacion proporcionada por el equipo).

**Periodo:** 2018-08-07 a 2022-08-06, equivalente al intervalo semiabierto `[2018-08-07, 2022-08-07)`.

## Datos y alcance

- **708.768 registros**, seis medios presentes: cinco medios principales y Cambio, que aporta solo **98 titulos** en este corte.
- **707.553 titulos disponibles (99,83 %)**, todos reconstruidos desde URLs y marcados `slug`; **1.215 titulos ausentes**.
- **0 cuerpos HTML**. El analisis no estudia citas, contexto completo ni titulares publicados verificados.
- **670.147 fechas de precision diaria** y **38.621 de precision mensual**. Precision diaria puede proceder de `lastmod`; no garantiza fecha editorial autentica.

## Resultados medidos

### Textometria

Se contaron **4.737.325 tokens depurados** y **98.418 tipos**. La correlacion log-log rango-frecuencia fue **r = -0,98211**. El ajuste descriptivo de rangos 10-10.000 obtuvo pendiente **-1,03495** y **R2 = 0,96898**.

Esto describe un patron compatible con Zipf; **no demuestra una ley de potencia**. El p-value numerico cero es redondeo/underflow, no una probabilidad exactamente nula.

| Medio | TTR agregado | MSTTR agregado, ventana 50 |
|---|---:|---:|
| La Republica | 0,062338 | 0,972207 |
| El Tiempo | 0,040343 | 0,953985 |
| Noticias Caracol | 0,053445 | 0,958202 |
| Blu Radio | 0,043499 | 0,959712 |
| Noticias RCN | 0,063897 | 0,956980 |
| Cambio | 0,802521 | 0,957778 |

El TTR agregado depende del tamano del corpus: el valor alto de Cambio refleja una muestra diminuta y **no permite ordenar medios por diversidad**. El TTR promedio por titulo ronda 0,996-0,999, porque los titulos cortos repiten pocas palabras. No se obtuvo ni se sostiene la afirmacion de que La Republica sea un 35 % mas diversa que Cambio.

La medida Yule K y los n-gramas estan calculados en las tablas reproducibles. Los n-gramas frecuentes describen coocurrencias despues de retirar stopwords, no significancia estadistica. **"programa completo" lidera los bigramas**: la mezcla de programas de radio, emisiones y notas escritas es un confusor de formato/archivo.

### Coincidencias tematicas por medio

Porcentajes respecto a los titulos disponibles de cada medio. Las cohortes de keywords pueden solaparse.

| Medio | Reforma tributaria | Conflicto armado | Corrupcion |
|---|---:|---:|---:|
| La Republica | 1,08 % | 0,10 % | 0,35 % |
| El Tiempo | 0,41 % | 1,33 % | 0,44 % |
| Noticias RCN | 0,37 % | 1,97 % | 0,53 % |
| Blu Radio | 0,42 % | 1,97 % | 0,67 % |
| Noticias Caracol | 0,32 % | 1,66 % | 0,51 % |
| Cambio | 0,00 % | 0,00 % | 0,00 % |

Totales: **3.374 coincidencias tributarias**, **10.203 de conflicto** y **3.565 de corrupcion**. Son temas amplios recuperados por keywords; no eventos verificados ni una medicion directa de framing. El cero de Cambio **no demuestra ausencia de cobertura**, especialmente con solo 98 titulos.

Tambien se construyeron candidatos temporales para reforma/paro 2021, bombardeo/menores 2019 y Centros Poblados 2021, con ejemplos y URLs para revision humana. No se certifico que cada pareja de articulos describa el mismo acontecimiento.

### LDA sobre corpus completo

Se entrenaron **cinco modelos, K = 3, 5, 7, 10 y 15**, con **10 pasadas, 50 iteraciones internas y semilla 42**, sin muestreo. El diccionario tiene 10.000 terminos. Se utilizaron **706.083 documentos**; los **2.685 sin vocabulario util** quedaron con topico `-1`.

**K=5 obtuvo el mayor c_v de la grilla: 0,359546.** Es una seleccion por coherencia de entrenamiento, no un optimo universal ni validacion externa. La perplejidad de entrenamiento favorecio K=3: ambos criterios no son equivalentes.

| Topico del modelo, indice 0-4 | Terminos principales | Lectura exploratoria, no etiqueta validada |
|---|---|---|
| 0 | emision, bogota, martes, jueves, nacional | Programacion/fechas y noticias generales |
| 1 | covid, colombia, dos, bogota, anos, coronavirus | Pandemia y noticias generales |
| 2 | colombia, duque, ucrania, unidos, presidente, rusia | Politica nacional/internacional mezclada |
| 3 | colombia, asi, video, tras, pico, mundial, placa | Movilidad, video y deportes mezclados |
| 4 | petro, gustavo, luis, caso, diaz, covid, fiscalia | Actores politicos/deportivos y casos mezclados |

**La distribucion no es uniforme ni cercana al 20 % en todos los medios.** Por ejemplo, el topico 1 representa **36,76 %** de Caracol y **24,68 %** de La Republica; el topico 4 llega a **34,69 %** de Cambio, cuya muestra pequena impide generalizar. Estas proporciones son de topico dominante e incluyen en el denominador los registros con topico `-1`.

No hay evidencia suficiente para afirmar una agenda editorial comun, ausencia de sesgo selectivo, correlacion o ausencia de correlacion con postura politica. Esas preguntas no se sometieron a pruebas o anotaciones adecuadas en esta entrega.

## Conclusiones para presentar

> Se analizaron 708.768 registros de seis medios durante el corte Duque. Se calcularon textometria, coincidencias tematicas normalizadas por medio y LDA sobre el corpus completo. La Republica presenta mas coincidencias tributarias relativas; RCN y Blu, mas coincidencias del tema amplio de conflicto. K=5 obtuvo la mayor coherencia de la grilla. La diversidad, las proporciones y los topicos estan condicionados por longitud, volumen, precision temporal y mezcla de formatos. Son resultados exploratorios de proxies slug: no permiten confirmar ni descartar sesgo editorial sin validar acontecimientos y recuperar texto publicado.

**Siguiente paso:** una submuestra balanceada por medio/fecha/formato, titulares reales y cuerpos, verificacion de pares del mismo acontecimiento y anotacion humana de framing. No usar sentimiento, volumen o LDA como sinonimos de sesgo.

## Entregables disponibles

- [Notebook ejecutado: 30 celdas, 15 de codigo](../entrega2/entrega2.ipynb).
- [Informe PDF, cinco paginas](entrega2.pdf) y [fuente LaTeX](entrega2.tex).
- [Presentacion editable, 10 diapositivas](entrega2.pptx).
- [Explorador pyLDAvis](../entrega2/resultados/lda_visualization.html).
- [Documentacion y reproduccion Docker](../entrega2/README.md).
- [Metricas verificables](../entrega2/resultados/resumen.json), [diversidad](../entrega2/resultados/diversidad_por_medio.csv), [keywords por medio](../entrega2/resultados/eventos_polemicos.csv), [distribucion de topicos](../entrega2/resultados/topics_by_medium_norm.csv) y [grilla LDA](../entrega2/resultados/lda_optimization.csv).

Hay **siete figuras analiticas principales**, mas una figura auxiliar de cobertura, en [la carpeta de figuras](../entrega2/resultados/figuras). El HTML y los PNG no estan en la carpeta informe. No se crearon las guias externas o de Replit mencionadas en el borrador. No se publico ni verifico una rama/remoto GitHub como parte de esta ejecucion.

## Validacion y limites

- Nueve tests del nucleo aprobados; prueba sintetica end-to-end sin publicar datos sinteticos.
- Notebook ejecutado sin errores desde la raiz del workspace y validado como JSON.
- Cinco modelos completos y distribuciones normalizadas; IDs de asignaciones unicos.
- PDF compilado; sin referencias indefinidas ni cajas Overfull.
- PPT comprobado estructuralmente y con formas dentro del lienzo; **no renderizado en PowerPoint**.
- Figuras no vacias y checksum del Parquet de entrada conservado; sin modificaciones a PostgreSQL.

El calculo principal completo duro aproximadamente **17 minutos y 25 segundos**, segun el registro del 2026-10-05; no incluye preparacion del entorno, depuracion o generacion/revision posterior de documentos. No se ha certificado reproduccion en Replit ni validacion academica independiente. El estado correcto es **entregables generados y pruebas tecnicas realizadas; interpretacion exploratoria pendiente de validacion sustantiva**, no "100 % probado para difusion".

Fecha: 2026-10-05.