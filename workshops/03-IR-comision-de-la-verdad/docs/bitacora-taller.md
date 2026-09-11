# Bitácora del Taller 3 — Recuperación de Información (CEV)

Registro ordenado de lo que se hizo, en qué orden, con qué criterio y con qué
resultado. Sirve como borrador del informe final: cada sección corresponde a una
actividad del enunciado y trae las cifras ya medidas, con el archivo del que
salen para poder verificarlas.

**Cómo usar este documento.** Está escrito para que otra persona redacte el
informe sin volver a ejecutar nada. Todas las cifras que aparecen aquí fueron
medidas sobre los archivos generados, no estimadas. Cuando algo está pendiente o
es una decisión sin justificación empírica todavía, se dice explícitamente.

**Cómo mantenerlo.** Cada vez que se complete un paso, agregar la subsección
correspondiente y una línea en el [registro cronológico](#10-registro-cronológico)
del final. Si una cifra cambia porque se re-generó un corpus, actualizarla aquí
también: el valor viejo en el informe sería un error.

Estado de las actividades del enunciado
([Taller recuperacion.pdf](../Taller%20recuperacion.pdf)):

| # | Actividad | Estado |
|---|---|---|
| 1 | Extracción y preparación del corpus | ✅ Completada |
| 2 | Análisis exploratorio del corpus | 🟡 Cálculos y figuras listos; falta redacción |
| 3 | Modelo de IR (TF-IDF) | 🟡 Implementado; el ranking colapsa (6.4) y la normalización lo mejora a medias (6.5) |
| 4 | Métricas de relevancia (Rocchio, BM25) | 🔴 Pendiente |
| 5 | Comparación de corpus + heatmap | 🔴 Pendiente |
| 6 | Informe final | 🔴 Pendiente |

---

## 1. Objetivo y alcance

El taller pide construir un proceso de recuperación de información que determine
**qué entrevistas están relacionadas con testimonios o secciones de los libros**
de la Comisión para el Esclarecimiento de la Verdad (CEV).

De ahí se desprende la arquitectura de todo el trabajo:

- Las **entrevistas funcionan como consultas**.
- Las **unidades de libro funcionan como documentos recuperables**.
- El resultado final es un vínculo entrevista → libro, que es lo que pide el
  entregable de la actividad 5.

---

## 2. Datos de entrada

| Archivo | Qué es | Dónde |
|---|---|---|
| 9 PDF de los tomos CEV | Fuente de los documentos | `Libros_CEV/contenido/` |
| 9 índices JSON | Tabla de partes/capítulos por página | `Libros_CEV/indices/` |
| `entrevistas_all_2023-03-21_14-24_05.json` | 2.486 entrevistas | `entrevistas/` |

**Decisión:** el archivo de entrevistas (231 MB) **no se versiona**. GitHub
rechaza blobs de más de 100 MB, y si se colara en un commit habría que reescribir
el historial para sacarlo. Está en `.gitignore` como `/workshops/**/entrevistas/`.
`preprocesar_corpus.py` lo busca en `entrevistas/`, en la carpeta del taller y en
`corpus/`, y si no lo encuentra falla con un mensaje que dice dónde buscó.

Estructura de una entrevista: `{"id_doc": "<hash>.pdf", "pages": 30, "text": "..."}`.
No hay fecha, ni persona, ni lugar: **no se puede filtrar ni agrupar por
metadatos**, solo por contenido.

Los índices de libro son listas ordenadas de puntos de inicio; cada nodo aplica
desde su `pagina_inicio` hasta el siguiente:

```json
[{"pagina_inicio": 23, "parte": null, "capitulo": "Introduccion"}]
```

---

## 3. Entorno

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download es_core_news_md
```

`requirements.txt` declara `pymupdf` (lectura de PDF), `spacy` (lematización y
stopwords), `numpy`, `matplotlib` y `wordcloud` (análisis exploratorio).

**Decisión:** el modelo `es_core_news_md` se instala con `spacy download`, no
como línea del `requirements.txt`, porque la URL del wheel del modelo está atada
a la versión exacta de spaCy y se rompe al actualizar.

---

## 4. Actividad 1 — Extracción y preparación del corpus

### 4.1. Morfología de la unidad documental

El enunciado pide "definir la morfología de documento para recuperar y explicar
cómo la van a hacer". La decisión, detallada en
[unidad-documental.md](unidad-documental.md):

- **Documento recuperable = cada unidad segmentada de los libros.** Puede ser un
  párrafo narrativo, un testimonio delimitado o una nota al pie.
- **Consulta = cada entrevista completa.** No se parte por turnos porque el JSON
  no trae intervenciones, hablantes ni marcas de tiempo aprovechables.

**Justificación cuantitativa:** una unidad de libro tiene 37,8 palabras de media
(mediana 17) y una entrevista, 14.331 (mediana 11.768). Tratar un libro completo
como documento mezclaría muchos temas y ocultaría coincidencias locales; tratar
una entrevista completa como unidad de libro produciría documentos no comparables
y demasiado pocos para rankear.

**Consecuencia que hay que declarar en el informe:** consulta y documento tienen
escalas muy distintas (≈4.100 tokens preprocesados contra ≈18). Esa asimetría
castiga a la similitud coseno y es justamente lo que corrige la normalización por
longitud de BM25 — la comparación de la actividad 4 tiene ahí su interés.

### 4.2. Segmentación de los libros (`segmentacion_libros.py`)

El PDF no trae marcado semántico: la estructura se infiere de la tipografía y la
geometría de cada línea, con PyMuPDF. Cuatro etapas:

1. **`extraer_lineas`** — clasifica cada línea por fuente y tamaño de sus spans:

   | Categoría | Firma tipográfica |
   |---|---|
   | Cuerpo | AGaramondPro-Regular, 10,5–11,5 pt |
   | Título | Futura, 15–20 pt |
   | Subtítulo | Futura, < 15 pt |
   | Parte/capítulo | Futura, ≥ 20 pt (se descarta: viene del índice) |
   | Nota al pie | 9 pt, con marcador numérico < 7,5 pt |

   También detecta el **número de página impresa** (el del pie, no el índice del
   PDF), que es el que usan los índices.

2. **`agrupar_en_bloques`** — reconstruye los párrafos por sangría de primera
   línea contra el margen mínimo de la página, lo que permite que un párrafo
   continúe a través de un salto de página.

3. **`segmentar`** — separa narrativa de testimonio. Un bloque entre `«` y `»`
   se emite como unidad aparte y se marca `es_relato=true` si supera las 15
   palabras. Un `»` al inicio de párrafo se interpreta como continuación, no
   como cierre.

4. **`construir_corpus`** — cruza cada unidad con el índice por número de página
   para asignarle `parte` y `capitulo`.

Los umbrales están en el diccionario `CONFIG`. Fueron calibrados con la
diagramación de estos tomos: **un libro diagramado distinto exige recalibrarlos**.

### 4.3. Identificadores estables

Cada unidad lleva un `id` de la forma `libro:<NOMBRE>:<posición en 6 dígitos>`
(por ejemplo `libro:NO_MATARAS:000003`), asignado por la segmentación. Las
entrevistas usan `entrevista:<id_doc>`.

**Por qué:** el mismo id viaja por toda la cadena (corpus segmentado →
`corpus_raw.json` → `corpus_preprocesado.json` → rankings), así que cualquier
resultado de recuperación se puede rastrear hasta la unidad exacta que lo produjo.
Sin eso, un ranking es un número sin evidencia.

**Advertencia:** el id depende de la posición, así que **cambia si se re-segmenta**.
Los ids actuales corresponden a la segmentación del 2026-09-10 descrita en 4.4.

### 4.4. Correcciones de calidad detectadas y aplicadas

Los cuatro problemas se detectaron **mirando las nubes de palabras**: el ranking
de términos no mostraba vocabulario del dominio sino artefactos del formato. Es
un buen argumento para el informe sobre por qué el análisis exploratorio no es
decorativo.

| # | Problema | Medición antes | Después |
|---|---|---|---|
| 1 | Guion de corte de línea (`significa- dos`) | 8.780 ocurrencias en 7.155 unidades | 13 (todos guiones legítimos) |
| 2 | Guion suave U+00AD dentro de palabras | 2.285 | 0 |
| 3 | Párrafos partidos a mitad de palabra | 1.666 unidades terminaban en guion | 223 |
| 4 | URLs de notas al pie tokenizadas (`https`, `www`) | en el top de términos de libros | fuera del índice |

1. **Guiones de corte** — `unir_linea()` reconstruye la palabra al unir líneas.
   Solo une si la línea siguiente arranca en minúscula, para no destruir
   `1980- 2016`, `CI- 00311` o `Vaupés- Guainía`. En una muestra de 25 cortes
   reales del corpus, los 25 eran silábicos.
2. **Guion suave** — es invisible pero no es carácter de palabra, así que
   `huma<U+00AD>nidades` se tokenizaba como `huma` + `nidades`. Ahora cuenta como
   corte y los sobrantes se eliminan.
3. **Falsos cortes de párrafo** — una palabra partida no puede abrir un párrafo
   nuevo: cuando la sangría dispara un corte a mitad de palabra, es un falso
   positivo y se suprime. Esto fusionó 1.593 unidades.
4. **URLs** — se eliminan **en el preprocesamiento, no en la segmentación**: el
   corpus raw conserva la URL de la nota al pie y solo el preprocesado, que es el
   que se indexa, la pierde. Eso respeta el contrato raw/preprocesado que pide el
   enunciado.

### 4.5. Preprocesamiento (`preprocesar_corpus.py`)

Reglas aplicadas por igual a libros y entrevistas, como pide el enunciado:

| Paso | Implementación |
|---|---|
| Tokenización | `\b\w+\b` sobre el texto en minúsculas, previa eliminación de URLs |
| Minúsculas | sí |
| Puntuación | eliminada por el patrón de tokenización |
| Stopwords | lista de spaCy español, evaluada sobre la forma superficial |
| Lematización | spaCy `es_core_news_md` |

**Decisión de implementación:** la lematización se hace sobre el **vocabulario**
(el conjunto de formas distintas), no documento por documento. Con 55.579
documentos y 34,7 millones de tokens, lematizar cada documento sería
innecesariamente costoso; el resultado es el mismo porque el lema se asigna por
forma, sin contexto. Costo actual: ~2 minutos para toda la cadena.

**Trazabilidad:** los documentos que quedan con `texto_preprocesado` vacío **se
conservan**, no se borran. La indexación debe excluirlos del cálculo, pero el id
debe seguir existiendo para auditoría.

### 4.6. Resultados de la actividad 1

Corpus de libros (`corpus/<LIBRO>.json`, manifiesto en `corpus/_manifiesto.json`):

| Libro | Unidades | Relatos | Notas al pie |
|---|---|---|---|
| HASTA_LA_GUERRA_TIENE_LIMITES | 12.288 | 1.102 | 3.570 |
| RESISTIR_NO_ES_AGUANTAR | 7.419 | 817 | 1.723 |
| HALLAZGOS_Y_RECOMENDACIONES | 7.597 | 353 | 1.281 |
| NO_MATARAS | 6.892 | 506 | 1.644 |
| MI_CUERPO_ES_LA_VERDAD | 5.435 | 558 | 1.148 |
| SUFRIR_LA_GUERRA_Y_REHACER_LA_VIDA | 4.644 | 370 | 1.070 |
| LA_COLOMBIA_FUERA_DE_COLOMBIA | 4.644 | 605 | 1.000 |
| NO_ES_UN_MAL_MENOR | 3.897 | 464 | 936 |
| CONVOCATORIA_A_LA_PAZ_GRANDE | 277 | 2 | 0 |
| **Total** | **53.093** | **4.777** | **12.372** |

Corpus unificado (entregable "dos archivos, raw y preprocesado"):

| Archivo | Contenido |
|---|---|
| `data/corpus_raw.json` | 55.579 documentos (53.093 unidades de libro + 2.486 entrevistas), texto sin tocar |
| `data/corpus_preprocesado.json` | los mismos 55.579 ids, con `texto_preprocesado` |
| `data/estadisticas_preprocesamiento.json` | tokens por documento, stopwords removidas, documentos vacíos |

Reducción de tokens por el preprocesamiento:

| Corpus | Tokens originales | Tokens finales | Reducción |
|---|---|---|---|
| Libros | 1.960.812 | 981.473 | 49,95 % |
| Entrevistas | 34.715.069 | 12.626.056 | 63,63 % |

**366 documentos** quedan con `texto_preprocesado` vacío (364 de libros, 2 de
entrevistas). De ellos, 256 son notas al pie cuyo texto era únicamente una URL.
Los dos archivos tienen exactamente el mismo conjunto de ids.

---

## 5. Actividad 2 — Análisis exploratorio (`analisis_exploratorio.py`)

### 5.1. Qué se calculó y con qué método

Para **libros y entrevistas por separado**, y para el texto **crudo y
preprocesado** en cada uno:

- Tokens, vocabulario (tipos), TTR, hapax legomena.
- Longitud de documento: media, mediana, p90, mínimo, máximo, vacíos.
- Términos más frecuentes.
- **Ley de Zipf:** ajuste por mínimos cuadrados de log10(frecuencia) contra
  log10(rango), reportando el exponente α y el R².

**Decisión — medir las dos versiones del texto.** La ley de Zipf se enuncia sobre
el texto tal cual, y el preprocesamiento le corta la cabeza a la distribución
(las stopwords son justamente los rangos más altos) y le fusiona la cola (la
lematización colapsa formas en un mismo lema). Reportar solo la versión
preprocesada daría un exponente no comparable con la literatura; reportar solo la
cruda no diría nada del corpus que efectivamente se va a indexar.

**Decisión — dos ajustes por corpus.** Se reporta el ajuste sobre **todo** el
rango y sobre la **banda de rangos 10–1000**. La cabeza (los primeros rangos) y
la cola de hapax se desvían sistemáticamente de la recta; el tramo central es
donde la ley de potencias se sostiene, y se ve en el R².

### 5.2. Resultados

| Corpus | Versión | Tokens | Vocabulario | TTR | Hapax | α (banda 10–1000) | R² | α (rango completo) | R² |
|---|---|---|---|---|---|---|---|---|---|
| Libros | crudo | 1.960.812 | 45.925 | 0,0234 | 36,7 % | **0,95** | 0,996 | 1,49 | 0,976 |
| Libros | preprocesado | 981.473 | 32.055 | 0,0327 | 36,1 % | 0,76 | 0,991 | 1,56 | 0,968 |
| Entrevistas | crudo | 34.715.069 | 148.026 | 0,0043 | 35,5 % | **1,21** | 0,997 | 1,78 | 0,984 |
| Entrevistas | preprocesado | 12.626.056 | 103.416 | 0,0082 | 40,4 % | 0,93 | 0,993 | 1,76 | 0,981 |

Longitud de documento (tokens):

| Corpus | Versión | Media | Mediana | p90 | Máx |
|---|---|---|---|---|---|
| Libros | crudo | 36,9 | 16 | 99 | 1.676 |
| Libros | preprocesado | 18,5 | 11 | 45 | 1.703 |
| Entrevistas | crudo | 13.964 | 11.524 | 23.730 | 149.409 |
| Entrevistas | preprocesado | 5.079 | 4.134 | 8.725 | 55.116 |

Solapamiento léxico (texto preprocesado):

| Medida | Valor |
|---|---|
| Vocabulario de libros | 32.055 |
| Vocabulario de entrevistas | 103.416 |
| Compartido | 22.975 |
| Jaccard | 0,204 |
| Solo en libros | 9.080 |
| Solo en entrevistas | 80.441 |

### 5.3. Lecturas para el informe

1. **Los dos corpus cumplen la ley de Zipf** sobre el texto crudo, con R² de
   0,996 y 0,997 en la banda central y α cercano a 1 (0,95 y 1,21).
2. **El habla transcrita concentra más masa en pocas palabras** que el texto
   editorial: α de entrevistas (1,21) por encima del de libros (0,95).
3. **El preprocesamiento aplana la curva** (α baja a 0,76 y 0,93) porque eliminar
   stopwords elimina justamente la cabeza de la distribución. Es un argumento
   para no leer el α del corpus preprocesado como si fuera el del lenguaje.
4. **La cola es enorme:** 36 % del vocabulario de libros y 40 % del de entrevistas
   son hapax. Ese es el argumento empírico para poner un `min_df` al construir el
   índice TF-IDF: un tercio del vocabulario no puede aportar a ninguna similitud.
5. **Los libros usan un vocabulario casi contenido en el de las entrevistas:**
   22.975 de sus 32.055 tipos (72 %) aparecen también en las entrevistas, mientras
   que 80.441 tipos son exclusivos de las entrevistas. Jaccard 0,204. Es lo
   esperable entre texto editorial y habla transcrita, y es buena noticia para la
   recuperación: el vocabulario de los documentos está casi todo cubierto por el
   de las consultas.

### 5.4. Hallazgo: ruido de formato

Las nubes de palabras salieron dominadas por artefactos del formato de las
fuentes, no por vocabulario del dominio:

| Corpus | Peso en los tokens preprocesados | Qué es |
|---|---|---|
| Entrevistas | **11,03 %** (1.393.178 tokens, 2.880 tipos) | Etiquetas de hablante `TEST` (344.807) y `ENT` (301.083), variantes `ENT1`/`TEST2`, marcas `[INTERRUP]` (35.728), `[INAD]`, `[CONT]`, `[DUD]`, y dígitos de los marcadores de anonimización (`ORGANIZACIÓN PÚBLICA 1 ----`) |
| Libros | **6,82 %** (66.938 tokens, 3.442 tipos) | Años (`2020`, `2019`, `2021`) y tokens numéricos |

**Decisión:** este ruido se excluye **solo de las figuras de contenido** (nubes y
ranking de términos). El JSON conserva el ranking completo y el detalle de lo
excluido en `ruido_de_formato`, para que la exclusión sea auditable.

**Decisión de no filtrar:** `[RISAS]`, `[LLANTO]` y `[CORTE]` se dejan adentro.
Los corchetes ya los borró el tokenizador y "risas", "llanto" y "corte" también
son palabras corrientes del español: filtrarlas descartaría contenido legítimo.

**Pendiente de decidir para la actividad 3:** si estos marcadores deben salir
también del índice. El IDF los penaliza solo parcialmente —aparecen en casi todas
las entrevistas, así que su IDF tiende a cero— pero sí afectan a BM25 por la vía
de la longitud del documento.

### 5.5. Figuras generadas

| Archivo | Qué muestra |
|---|---|
| `figuras/zipf_preprocesado.png` | Rango-frecuencia log-log, libros vs entrevistas, con la recta ajustada |
| `figuras/zipf_crudo_vs_preprocesado.png` | Efecto del preprocesamiento sobre la distribución, un panel por corpus |
| `figuras/longitud_documentos.png` | Histograma de longitud de documento, un panel por corpus |
| `figuras/top_terminos.png` | Top 15 de términos por corpus, con conteos |
| `figuras/nube_libros.png`, `figuras/nube_entrevistas.png` | Nubes de palabras |

**Criterios de graficación** (por si hay que rehacer alguna): paneles separados
cuando las escalas no son comparables, nunca dos ejes Y en una misma figura;
color categórico fijo por corpus (azul libros, naranja entrevistas); rampa de un
solo tono en las nubes, donde el color codifica magnitud y no identidad; leyenda
siempre presente.

---

## 6. Actividad 3 — Modelo de recuperación TF-IDF (`modelo_ir.py`)

### 6.1. Decisiones tomadas

| Decisión | Elección | Por qué |
|---|---|---|
| Documentos indexados | Narrativa + testimonios, **sin notas al pie** | Las notas son referencias bibliográficas: coinciden por apellidos y topónimos, no por contenido narrativo, y con mediana de 9 tokens BM25 tiende a sobre-puntuarlas. Siguen en el corpus, solo no se indexan |
| Ruido de formato | **Fuera del índice** | Es el 11 % de los tokens de entrevistas. El IDF casi lo anula, pero infla la longitud del documento, que es justo lo que BM25 normaliza en la actividad 4 |
| Corte de vocabulario | `min_df = 2` | Un término en un solo documento no puede emparejar nada; el 36 % del vocabulario de libros son hapax (medido en 5.2) |
| Agregación al nivel de libro | **Suma de las 10 mejores unidades** | El máximo deja que una coincidencia aislada defina el vínculo; el promedio castiga a los libros grandes (de 277 a 12.288 unidades) |
| Implementación | Pesado propio, sin `sklearn` | La actividad 4 exige métricas manuales y debe reutilizar estas mismas estructuras. `scipy.sparse` se usa solo para el álgebra, no para el modelo |

La regla de ruido de formato se movió a `vocabulario.py`, compartida entre el
análisis exploratorio y el índice: con dos copias, el corpus analizado y el
recuperado podrían dejar de ser el mismo.

### 6.2. Pesado

```text
tf   = 1 + log(frecuencia del término en el documento)
idf  = log((1 + N) / (1 + df)) + 1        (suavizado: ningún idf queda en 0)
peso = tf * idf, normalizado en L2 por documento
```

Con los vectores normalizados en L2 la similitud coseno **es** el producto
punto, así que el ranking completo es un producto de matrices dispersas. Se
procesa por bloques de 128 consultas: la matriz de similitudes completa sería de
2.484 × 40.006 celdas.

El vocabulario y el idf se calculan **solo sobre los documentos**: una consulta
no puede alterar el peso de un término del índice.

### 6.3. Resultados de la ejecución

| Magnitud | Valor |
|---|---|
| Documentos indexados | 40.006 |
| Descartados | 12.372 notas al pie, 715 unidades sin términos |
| Consultas | 2.484 (2 entrevistas quedan vacías tras la limpieza) |
| Vocabulario | 15.950 términos con df ≥ 2, de 27.134 distintos |
| No-ceros | 686.727 en documentos, 2.507.081 en consultas |
| Tiempo | ~16 s |

Salida en `data/ranking_tfidf.json` (35 MB): por entrevista, las 20 mejores
unidades con su puntaje, libro, parte, capítulo, título, `es_relato` y un
fragmento del texto crudo como evidencia, más el puntaje agregado de los nueve
libros.

### 6.4. Diagnóstico: el ranking colapsa

**Este es el hallazgo principal de la actividad 3 y hay que reportarlo como tal.**

| Señal | Valor |
|---|---|
| Unidades distintas en el top-1 | **297** para 2.484 consultas |
| Consultas ganadas por una sola unidad | **657** (26 % de todas) |
| Unidades distintas en todo el top-20 guardado | 1.434 de 40.006 |
| Similitud del top-1 | media 0,255 · mediana 0,252 · rango 0,176–0,498 |
| Consultas cuyo top-1 es un testimonio | 2.469 de 2.484 |

Libro ganador por entrevista: RESISTIR_NO_ES_AGUANTAR 1.738, MI_CUERPO_ES_LA_VERDAD 444,
NO_ES_UN_MAL_MENOR 150, LA_COLOMBIA_FUERA_DE_COLOMBIA 108, HASTA_LA_GUERRA_TIENE_LIMITES 39,
HALLAZGOS_Y_RECOMENDACIONES 3, NO_MATARAS 1, SUFRIR_LA_GUERRA_Y_REHACER_LA_VIDA 1,
CONVOCATORIA_A_LA_PAZ_GRANDE 0.

**Interpretación.** El modelo casi no discrimina por tema: le devuelve el mismo
puñado de unidades a todas las entrevistas, y lo que decide el ranking es la
**longitud del documento**.

| | Mediana de tokens preprocesados |
|---|---|
| Corpus indexado | 12 |
| Ganadores del top-1 | **274** (percentil 99,97 del corpus) |

El 84,7 % de los ganadores del top-1 está en el 1 % de unidades más largas del
índice.

El mecanismo: una entrevista aporta ~1.128 términos distintos sobre un
vocabulario de 15.950, así que la consulta cubre casi cualquier cosa que un
documento pueda decir. En `cos = Σ q_t·d_t / ‖d‖`, el numerador crece con la
cantidad de términos que el documento comparte con la consulta, mientras `‖d‖`
crece como la raíz de la suma de cuadrados: con una consulta prácticamente
exhaustiva, el documento más largo gana de forma sistemática. Es el sesgo
conocido de la similitud coseno ante consultas largas, el que motivó la
*pivoted length normalization* de Singhal (1996) y el parámetro `b` de BM25.

Dos precisiones para no repetir errores de lectura:

- La normalización L2 **de la consulta** no interviene: es una constante por
  consulta y no altera el orden dentro de ella. El sesgo lo introduce la
  normalización del documento.
- Que el 99,4 % de los top-1 sean testimonios no es un efecto temático: los
  testimonios son las unidades más largas (mediana 23 tokens contra 11 de la
  narrativa) y los relatos multipárrafo son las más largas de todas.

**No es un error de implementación**, es el comportamiento esperado de la
similitud coseno ante una consulta que cubre casi todo el vocabulario, y es
exactamente el problema que la normalización por longitud de BM25 está diseñada
para corregir. La
actividad 4 tiene así una hipótesis concreta que contrastar, y el diagnóstico
—que el script recalcula en cada corrida bajo la clave `diagnostico`— da la
métrica con la que compararlas: **si BM25 sirve, el número de unidades distintas
en el top-1 debe subir**.

### 6.5. Experimento: normalización de longitud

Primera respuesta al colapso de 6.4, atacando el normalizador del documento.
`modelo_ir.py` implementa tres normalizaciones y un barrido (`--barrido`) que
las compara con la métrica del diagnóstico:

| Modo | Factor por el que se divide cada documento |
|---|---|
| `l2` | `‖d‖` — la similitud coseno |
| `pivotada` | `(1 − s)·pivote + s·‖d‖`, con `pivote = media(‖d‖)` — forma canónica de Singhal (1996) |
| `potencia` | `pivote · (‖d‖/pivote)^α` — con α=1 se reduce a la coseno; α>1 penaliza la longitud **más** que ella |

**La pivotada canónica va en la dirección equivocada para este corpus.** Fue
diseñada para el caso habitual —consultas cortas, donde la coseno penaliza *de
más* a los documentos largos— y por eso con `s < 1` aplana el normalizador y
empeora el problema. Medido sobre 300 consultas de muestra:

| Normalización | Top-1 distintos | Más repetido | Mediana de tokens del top-1 |
|---|---|---|---|
| pivotada s=0,2 | 16 | 99 | 380 |
| pivotada s=0,5 | 29 | 88 | 270 |
| pivotada s=0,8 | 46 | 82 | 270 |
| **l2 (coseno)** | **62** | **78** | **257** |
| potencia α=1,1 | 78 | 59 | 188 |
| potencia α=1,2 | 109 | 61 | 73 |
| **potencia α=1,3** | **133** | **67** | **58** |
| potencia α=1,4 | 120 | 45 | 31 |
| potencia α=1,5 | 92 | 63 | 8 |

(mediana del corpus indexado: 11 tokens)

El óptimo está en **α ≈ 1,3**. Pasado α=1,4 el sesgo se invierte y empiezan a
ganar unidades de uno o dos tokens: una sola palabra rara basta para el match.

**Filtro de unidades muy cortas: probado y descartado.** Se midió el mismo
barrido exigiendo un mínimo de 3 y de 5 tokens por documento; el óptimo se
mueve de 133 a 135 top-1 distintos. No justifica sacar 9.135 unidades del
índice.

**Corrida completa con α = 1,3** (`data/ranking_tfidf_potencia_a1.3.json`),
contra la línea base coseno:

| Señal | Coseno (α=1) | Potencia α=1,3 |
|---|---|---|
| Unidades distintas en el top-1 | 297 | **707** |
| Consultas ganadas por una sola unidad | 657 | 563 |
| Unidades distintas en todo el top-20 | 1.434 | **3.399** |
| Mediana de tokens del top-1 | 274 | **58** |
| Top-1 que son testimonios | 2.469 | 2.351 |
| Similitud del top-1 (media) | 0,255 | 0,186 |

El reparto por libro también se despeja: RESISTIR_NO_ES_AGUANTAR baja de 1.738
entrevistas a 928 y HASTA_LA_GUERRA_TIENE_LIMITES sube de 39 a 463.

**Conclusión.** La normalización corrige una parte real del sesgo —duplica con
creces la diversidad del ranking y acerca la longitud del ganador a la del
corpus— pero **no resuelve el colapso**: una sola unidad sigue ganando 563 de
2.484 consultas. Era previsible: la normalización corrige cómo se penaliza al
documento, no el hecho de que la consulta cubra 1.128 términos del vocabulario
y por lo tanto se parezca un poco a todo. Eso solo lo arregla intervenir la
consulta (podarla o segmentarla en pasajes).

Cada configuración escribe su propio archivo: el ranking coseno es la línea
base del informe y no se pisa.

---

## 7. Próximos pasos

### 7.1. Actividad 4 — Rocchio y BM25 (siguiente)

Implementación manual de ambas, reutilizando el índice de `modelo_ir.py`.

- **BM25** con `k1` y `b` explícitos. La hipótesis a contrastar está en 6.4 y
  6.5: la normalización por longitud corrige parte del sesgo pero no todo, así
  que lo esperable es que BM25 quede cerca de la potencia α=1,3 y que la
  mejora grande venga de intervenir la consulta. La métrica de comparación ya
  está definida (unidades distintas en el top-1).
- **Poda de la consulta:** usar los mejores 50–100 términos de la entrevista
  por tf-idf en lugar de sus ~1.128 términos distintos. Ataca la causa que la
  normalización no puede tocar, y es el andamiaje de Rocchio.
- **Rocchio** necesita juicios de relevancia y **no hay etiquetas**. La salida
  honesta es *pseudo-relevance feedback*: tomar los k primeros del ranking como
  relevantes, reformular la consulta y volver a rankear, declarándolo como tal
  y no como relevancia real.
- Comparar los tres rankings sobre las mismas consultas y discutir las
  diferencias, que es lo que pide el enunciado.

### 7.2. Actividades 5 y 6

Cuadro y heatmap entrevista-libro a partir del puntaje agregado que ya calcula
`modelo_ir.py`, e informe final. Ojo: con el ranking actual el heatmap mostraría
sobre todo el sesgo descrito en 6.4, así que conviene construirlo después de
tener BM25.

---

## 8. Limitaciones conocidas

- **Testimonios sin guillemets.** Algunos testimonios aparecen como bloque de
  cita indentado en 10 pt, sin `« »` (por ejemplo la carta de Daniela Narváez,
  pág. 53 de *Sufrir la guerra y rehacer la vida*). Al no estar delimitados, no
  se capturan como relato.
- **Umbrales acoplados al diseño.** La clasificación depende de nombres de fuente
  concretos (`AGaramondPro-Regular`, `Futura`). Otro tomo exige recalibrar `CONFIG`.
- **Umbral de relato.** `es_relato` se decide por un corte de 15 palabras: una
  cita corta entre guillemets no cuenta como relato.
- **Fragmentos de URL en texto corrido.** Quedan tokens sueltos (`ci`, `pr`, `ep`)
  que vienen de rutas de URL partidas dentro del texto, no de URLs completas.
- **Entrevistas sin metadatos.** No hay fecha, persona ni lugar: toda la
  recuperación depende del contenido.
- **Sin juicios de relevancia.** No hay forma de calcular precisión o recall
  reales; la evaluación será comparativa entre métricas, no contra una verdad
  de referencia.

---

## 9. Cómo reproducir todo

```bash
.venv/bin/python segmentacion_libros.py      # PDF  -> corpus/*.json
.venv/bin/python preprocesar_corpus.py       # corpus + entrevistas -> data/
.venv/bin/python analisis_exploratorio.py    # data/ -> estadísticas + figuras
.venv/bin/python modelo_ir.py                # data/ -> ranking TF-IDF
```

El detalle de cada paso está en [README-base-datos.md](README-base-datos.md).

---

## 10. Registro cronológico

| Fecha | Hecho |
|---|---|
| 2026-09-10 | Segmentación de los 9 tomos con morfología de unidad documentada; corpus por libro en `corpus/` |
| 2026-09-10 | Se agrega `id` estable a cada unidad (`libro:<NOMBRE>:<posición>`) y se propaga a toda la cadena |
| 2026-09-10 | Se crea `requirements.txt` del taller |
| 2026-09-10 | Se incorpora el corpus de entrevistas (231 MB, no versionado); corpus raw y preprocesado completos: 55.579 documentos |
| 2026-09-10 | Análisis exploratorio: Zipf, diversidad léxica, longitudes, solapamiento de vocabulario |
| 2026-09-10 | Nubes de palabras y ranking de términos; se detecta el ruido de formato (11,0 % entrevistas / 6,8 % libros) |
| 2026-09-10 | Correcciones de calidad: guiones de corte, guion suave, falsos cortes de párrafo y URLs; re-generada toda la cadena |
| 2026-09-10 | Se corrigen cifras desactualizadas en `unidad-documental.md` (longitudes de unidad de libro) |
| 2026-09-10 | Se fijan las decisiones del modelo de IR: sin notas al pie, sin ruido de formato, `min_df=2`, agregación por suma de las 10 mejores unidades |
| 2026-09-10 | Modelo TF-IDF implementado y ejecutado; se detecta que el ranking colapsa (297 unidades distintas en el top-1 para 2.484 consultas) |
| 2026-09-10 | Se corrige el diagnóstico de 6.4: ganan los documentos **largos** (mediana 274 tokens, percentil 99,97), no los cortos |
| 2026-09-10 | Experimento de normalización: la pivotada canónica empeora el caso, la de potencia con α=1,3 duplica la diversidad del top-1 (297 → 707) sin resolver el colapso |
