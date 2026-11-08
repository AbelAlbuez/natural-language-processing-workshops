# Análisis de los commits recientes del equipo y del informe final (entrega 3)

Revisión de solo lectura de los commits del 4 al 8 de noviembre de 2026 en `workshops/media-bias-detection`, hechos por otros integrantes del equipo, y del estado del informe final `informe/entrega3.tex`. No se cambió código ni informe.

Las cifras del informe se compararon una por una con los archivos de resultados versionados (unas 313 cifras). Las rutas abreviadas como `RP/` se refieren a `entrega3/resultados_publico/`. Los números de línea son de `informe/entrega3.tex` en el commit `9968538`.

## Commits analizados

| Hash | Autor | Fecha | Mensaje |
|---|---|---|---|
| 9968538 | Jesus Romero Melo | 2026-11-08 | presentación e informe entrega 3 |
| aff0d27 | Juan Camilo Torres | 2026-11-08 | docs(informe): agrega borrador LaTeX del informe final y guía para terminarlo |
| 25b889a | Juan Camilo Torres | 2026-11-08 | feat(entrega3): analiza el silver standard y agrega el informe final |
| 42e976d | Juan Camilo Torres Peña | 2026-11-08 | Add files via upload |
| 9ed4bbe | Jesus Romero Melo | 2026-11-07 | silver standar 1 |
| 468d4a7 | Juan Camilo Torres | 2026-11-06 | feat(entrega3): agrega lenguaje cargado, léxico en la banda 0,65–0,80 y silver standard |
| 7f9a0e2 | Juan Camilo Torres | 2026-11-06 | feat(entrega3): agrega omisión por tema × gobierno y elección léxica sobre los eventos |
| 76fd26c | Juan Camilo Torres | 2026-11-06 | feat(entrega3): rearma los eventos con el umbral calibrado 0,80 |
| 23b1b88 | Juan Camilo Torres | 2026-11-06 | feat(entrega3): evalúa la calibración con precisión ponderada por población |
| 0f2a13d | Juan Camilo Torres Peña | 2026-11-06 | Add files via upload |
| cd3d086 | Jesus Romero Melo | 2026-11-06 | revision planilla 1 |
| bc21560 | Juan Camilo Torres | 2026-11-06 | docs(entrega3): agrega las planillas de calibración y su guía para el equipo |
| 5490ecb | Juan Camilo Torres | 2026-11-06 | feat(entrega3): agrega la calibración manual del emparejamiento (paso 2) |
| 436e5fe | Juan Camilo Torres | 2026-11-06 | docs(entrega3): documenta el emparejamiento de titulares entre medios |
| bc079cd | Juan Camilo Torres | 2026-11-06 | data(entrega3): agrega eventos entre medios del subcorpus de asuntos públicos |
| 462a8a5 | Juan Camilo Torres | 2026-11-06 | feat(entrega3): empareja titulares del mismo hecho entre medios (pasos 1 y 3) |
| b158d49 | Juan Camilo Torres | 2026-11-05 | fix(entrega3): elige los ejemplos de BERTopic por cercanía al centroide |
| 4882fb0 | Juan Camilo Torres | 2026-11-05 | docs(entrega3): documenta las mejoras y actualiza el resumen ejecutivo |
| fe26a02 | Juan Camilo Torres | 2026-11-05 | data(entrega3): agrega resultados del subcorpus, del consenso y de BERTopic |
| dfe9dab | Juan Camilo Torres | 2026-11-05 | feat(entrega3): agrega subcorpus público, control por sección, LDA de consenso y BERTopic |
| 3126258 | Juan Camilo Torres | 2026-11-05 | data(news-corpus): agrega dump del corpus procesado del 2026-11-05 por Git LFS |
| 43beb2d | Juan Camilo Torres | 2026-11-05 | docs(entrega3): documenta el LDA y agrega resumen ejecutivo de resultados |
| 406cb94 | Juan Camilo Torres | 2026-11-05 | data(entrega3): agrega resultados del LDA K=15 y figuras |
| 5cc1173 | Juan Camilo Torres | 2026-11-05 | feat(entrega3): agrega pipeline LDA conjunto Duque + Petro |
| 48d84c3 | Juan Camilo Torres | 2026-11-04 | docs(news-corpus): documenta el tratamiento del slug y la distribución del corpus |
| 7e498b6 | Juan Camilo Torres | 2026-11-04 | fix(news-corpus): limpia el slug y marca piezas no informativas en enrich |
| 52db8c2 | Juan Camilo Torres | 2026-11-04 | feat(news-corpus): agrega non_news_reason a article y al export |

Los commits de octubre (entrega 2) quedan fuera del análisis. Solo se usan cuando el informe final cita cifras de esa entrega.

## 1. Qué hizo el equipo

- **4–5 de noviembre: corpus y agenda.** Se limpió el slug de las URLs y se marcaron las piezas no informativas en el corpus. Se versionó el dump procesado con Git LFS. Se armó el pipeline LDA conjunto Duque + Petro, el subcorpus de asuntos públicos, el control por sección, un LDA de consenso y BERTopic.
- **6 de noviembre: mismo hecho y encuadre.** Se emparejaron titulares del mismo hecho entre medios. El umbral de similitud se calibró a mano con planillas (una de ellas revisada por un segundo integrante), con precisión ponderada por población, y quedó en 0,80. Sobre esos eventos se midieron la omisión por tema × gobierno, la elección léxica y el lenguaje cargado, y se preparó el silver standard.
- **7–8 de noviembre: silver standard e informe largo.** Se subieron las dos planillas del silver standard; la segunda la anotó un modelo de lenguaje. Se agregó el análisis del silver standard (`silver_analisis.py`, con pruebas) y el informe largo en Markdown, `entrega3/INFORME_FINAL.md`.
- **8 de noviembre: informe LaTeX.** Primero se subió un borrador de 5 páginas con una guía para terminarlo (`informe/GUIA_ENTREGA3.md`). Horas después, la versión reescrita de 10 páginas, con el PDF y la presentación (`entrega3.pdf` y `entrega3.pptx`).

## 2. Estado actual del informe final

**Formato.** `article` a dos columnas, 10 páginas. No es IEEE: la guía deja esa decisión al equipo. La bibliografía está escrita dentro del `.tex` (`thebibliography`, 17 entradas); `informe/referencias.bib` no se usa.

**Secciones completas:**

- Resumen, Introducción, Correcciones respecto a la entrega 2 y Datos.
- Desarrollo del modelo final: componentes; agenda (entrenamiento, evaluación y selección); Δ relativo y control por sección; mismo hecho (emparejamiento y calibración); medidas de encuadre y de selección; silver standard y clasificadores; ejemplos de salida.
- Análisis de resultados: agenda, selección, encuadre, silver standard y coincidencias entre análisis.
- Discusión: patrones, limitaciones y mejoras futuras.
- Conclusiones y una sección sin numerar de Reproducibilidad.

**Lo que ya cumple:**

- No queda ningún `\todo` (el borrador tenía dos).
- Las 17 claves citadas tienen su entrada en la bibliografía, y no sobra ninguna.
- Las 6 figuras existen en disco. El borrador usaba 8; la versión final quitó la 01 y la 17.
- El PDF subido corresponde al `.tex`: aparecen las 23 secciones.
- La anotación del silver standard por un modelo de lenguaje está declarada en Métodos (línea 327), Discusión (línea 570) y Limitaciones (línea 582).

**Lo que falta o queda abierto:**

- **Cifras:** 6 no coinciden con los datos y 3 no tienen fuente en el repositorio (sección 3). El punto de la lista de chequeo de la guía «Todas las cifras coinciden con los CSV citados» no se cumple todavía.
- **Silver standard:** quedan 32 casos pendientes de adjudicar (`RP/silver/evaluacion.json`). El κ = 0,30 es entre una persona y un modelo de lenguaje, no entre dos personas.
- **Decisiones de equipo de la guía:** el formato (IEEE o no) y la extensión no aparecen como resueltas en el repositorio.

## 3. Coherencia entre el informe y los datos

### Discrepancias (6)

1. **Distancia Jensen-Shannon (líneas 428–429).**
   - El informe dice: «la distancia Jensen-Shannon media entre medios pasa de 0,180 a 0,204», en el párrafo sobre BERTopic y el subcorpus de asuntos públicos.
   - Esos valores salen de `entrega3/resultados/distancias_js.csv`, que es el LDA sobre el **corpus completo** (0,1797 → 0,2041).
   - En el subcorpus la distancia **baja**: 0,2815 → 0,2557 con BERTopic (`RP/bertopic/distancias_js.csv`) y 0,1723 → 0,1564 con LDA (`RP/distancias_js.csv`).
   - La frase «las agendas también se separan» no se sostiene para el modelo elegido. `INFORME_FINAL.md` §4.1 tiene el mismo error. Es la discrepancia más importante, porque cambia una conclusión.
2. **Calibración del umbral (líneas 285–287).**
   - El informe dice: «Por debajo de 0,75, una de cada cuatro parejas aceptadas no es el mismo hecho».
   - En `RP/calibracion/precision_por_umbral.csv`, con umbral ≥ 0,75 la precisión es del 75 % (una de cada cuatro mal), y con ≥ 0,70 es del 62 %.
   - Dentro de la banda 0,60–0,75 solo el 25–27 % son el mismo hecho. La frase confunde el umbral con la banda.
3. **«Donald Trump» en El Tiempo (líneas 480–481).**
   - El informe dice 75 % de los titulares sobre Trump.
   - En `RP/lexico/nombre_completo_actores.csv`, ese 75,1 % (325 de 433) es solo con Petro. Con Duque es 24,7 % (20 de 81), y juntando los dos gobiernos, 67 %.
   - Falta decir que la cifra es del periodo Petro.
4. **n efectivo del silver standard (líneas 584–585).**
   - El informe dice «n efectivo de ~10».
   - En `RP/silver/analisis/tasas_por_definicion.csv`, el `n_efectivo` por celda va de 4,3 a 8,8 para la persona y para la IA (media ≈ 6,9). Solo con las etiquetas combinadas se acerca a 10.
   - `INFORME_FINAL.md` repite el «~10».
5. **Diferencias Petro − Duque (líneas 524–525).**
   - El informe dice «Ninguna diferencia Petro − Duque por medio es significativa».
   - En `RP/silver/analisis/diferencias_petro_duque.csv`, La República con la definición `combinado_estricto` y la variable «sesgado» da −15,5 pp, IC (−41,3; −0,2), p = 0,039: significativa sin corrección.
   - La frase solo vale para las etiquetas de la persona, de la IA y la definición laxa. Hay que acotarla o mencionar la corrección por comparaciones múltiples.
6. **Ejemplos de BERTopic (leyenda en las líneas 395–396 frente a las filas 405–406).**
   - La leyenda dice que se muestra «el titular más cercano al centroide».
   - En `RP/bertopic/topic_examples.csv`, para los tópicos T4 y T17 el titular mostrado es el segundo más cercano, no el primero. Las similitudes redondeadas que aparecen son correctas.

### Cifras sin fuente en el repositorio (3)

- **Líneas 145–146:** «Descargar el cuerpo sólo fue posible para cerca del 1 % de las URLs». No aparece en `entrega3/README.md`, `INFORME_FINAL.md`, `RESUMEN_EJECUTIVO.md`, los documentos de `news-retrieval/docs/` ni los `.tex` de la entrega 2. Las únicas cifras de cobertura de cuerpo son las del piloto: 15 % Blu Radio, 30 % Caracol y 99 % El Tiempo.
- **Líneas 213–214:** «HDBSCAN suele dejar el 30–40 % como ruido». Solo aparece como comentario en `entrega3/bertopic_topics.py` (líneas 8–9); ningún resultado lo mide.
- **Líneas 601–602:** «~100 por celda, para bajar los IC por medio a ±10–15 pp». Solo aparece como texto en `INFORME_FINAL.md` §8; no hay un cálculo que lo respalde.

### Matices menores (las cifras coinciden, pero conviene precisarlas)

- **Línea 491, «3 pp como mucho»:** vale para la carga negativa (máximo |−3,09|). Con «cualquier carga», `RP/carga/carga_medio_gobierno.csv` llega a −3,78 (La República, Petro) y +3,49 (Caracol, Duque).
- **Leyenda de la tabla de Δ (línea 436):** dice «Δ relativo significativo», pero la tabla aplica un filtro más estricto, «fiable», que además exige el mismo signo en las semillas. Dos cambios de La República son significativos por Holm en `RP/bertopic/deltas.csv` y quedan fuera por ese filtro.
- **Líneas 583 y 599, «32 desacuerdos»:** de los 32 pendientes, 23 son desacuerdos sobre «sesgado sí/no»; los otros 9 son sobre tipo o dirección.
- **Línea 632, «100 funciones de prueba»:** son 86 en `entrega3/tests` más 14 en `entrega2/tests`. Conviene decir que cuenta las dos carpetas.
- **Línea 526, «IC de ±30–50 pp»:** vale para la persona (36–53 pp). Varias diferencias de la IA son mucho más estrechas (±2–5 pp).

Varias cifras correctas no salen de los archivos que indica la guía, sino de `entrega3/resultados/`, de los `.tex` y el resumen ejecutivo de la entrega 2, o de los documentos de `news-retrieval/docs/`. No es un error, pero la tabla de fuentes de la guía está incompleta.

## 4. Qué se puede mejorar, por impacto en la entrega

### Correcciones urgentes (antes de entregar)

1. **Reescribir la frase de la distancia Jensen-Shannon** (líneas 428–429). Dar el valor del subcorpus y decir que ahí las agendas se acercan, o aclarar que 0,180 → 0,204 es del LDA sobre el corpus completo. Corregir también `INFORME_FINAL.md` §4.1.
2. **Corregir la frase de la calibración** (líneas 285–287): distinguir el umbral ≥ 0,75 (75 % de precisión) de la banda 0,60–0,75.
3. **Acotar «ninguna diferencia es significativa»** (líneas 524–525) a las definiciones en que se cumple, o mencionar la excepción de La República y la corrección por comparaciones múltiples.
4. **Precisar el 75 % de «Donald Trump»** (líneas 480–481) como cifra del periodo Petro.
5. **Ajustar el n efectivo** (líneas 584–585) a «entre 4 y 9 por anotador», y corregir lo mismo en `INFORME_FINAL.md`.
6. **Dar fuente o quitar las tres cifras sin respaldo** (el 1 % de cuerpos descargados, el 30–40 % de ruido de HDBSCAN y los ~100 por celda), o presentarlas como estimaciones.

### Mejoras de contenido

- Cambiar «el más cercano al centroide» por «uno de los más cercanos», o usar los ejemplos más cercanos de T4 y T17.
- Ajustar la leyenda de la tabla de Δ a «fiable (significativo por Holm y con el mismo signo en las semillas)».
- Decidir si se adjudican los 32 casos pendientes o si una segunda persona anota la planilla 2, para tener un κ entre humanos. La guía estima unas 2 horas.
- Resolver con el equipo el formato (IEEE o no) y el límite de páginas, como pide la guía.

### Mejoras de reproducibilidad

- **Compilación:** completar en la guía cómo compilar. El `.tex` usa `newunicodechar`, que no está en instalaciones mínimas de TeX; la imagen de Docker de la guía sí lo trae.
- **Tabla de fuentes:** agregar a la guía las fuentes reales de las cifras que no salen de `resultados_publico/` (resultados del corpus completo y documentos de la entrega 2 y de `news-retrieval`).
- **Informe largo:** mantener `INFORME_FINAL.md` sincronizado con el `.tex`; hoy repite al menos dos de las discrepancias.
- **Rutas de figuras:** las figuras se leen con una ruta relativa (`../entrega3/resultados_publico/`). Para compilar en Overleaf hay que subir las dos carpetas con esa estructura.

## 5. Riesgos

- **Datos no versionados.** Los artefactos grandes (`prepared.parquet`, `theta.npy`, `embeddings.npy`, asignaciones por semilla y la mayoría de los modelos) están ignorados por git y se regeneran con `./run.sh`. Reproducir los resultados exige volver a correr los pipelines, con semillas fijas pero con tiempo de cómputo.
- **Git LFS.** Los dos dumps del corpus están en Git LFS. Clonar sin LFS deja punteros en lugar de los datos, y el almacenamiento LFS de GitHub tiene cuota.
- **Referencias sin verificar.** Las 17 referencias no llevan DOI ni URL. No hay constancia de que se hayan verificado contra la fuente.
- **Cifras sin fuente.** Son las tres de la sección 3. Además, el silver standard tiene 32 casos pendientes de adjudicar, que pueden mover las tasas.
- **Clave de API en el código.** `generar_corpus_newsapi.py`, agregado en el commit `00358d9` de octubre (anterior a este análisis), tiene una clave de NewsAPI escrita en el código como valor por defecto. El repositorio es público. Hay que revocarla en NewsAPI, generar otra y quitar el valor por defecto del código. Borrarla del archivo no la elimina del historial.
- **Correo personal.** `PRESENTACION_REPLIT_ENTREGA2_COMPLETA.md` contiene un correo personal. Conviene quitarlo.
- **Anotador automático.** La segunda planilla del silver standard la anotó un modelo de lenguaje. Está declarado en el informe, pero cualquier cifra de acuerdo debe leerse como persona frente a modelo, no como acuerdo entre anotadores humanos.
