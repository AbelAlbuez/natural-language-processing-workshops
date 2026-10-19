# TweetToxic 2026 PUJ: informe de experimentos (equipo NLP_G1)

Curso de Procesamiento del Lenguaje Natural, Maestría en Inteligencia Artificial, Pontificia Universidad Javeriana.
Documento base para el informe final. Reúne todos los intentos, del notebook original (`../TweetToxic_modelo.ipynb`) a la ronda E13.
Todas las cifras salen de las salidas guardadas en los notebooks `E*.ipynb`, de `RESUMEN.md` y del leaderboard público de Kaggle.

---

## 1. Resumen ejecutivo

| Indicador | Valor | Modelo |
|---|---|---|
| Punto de partida | CV 0,8126 ± 0,0021 · público 0,79160 | Stacking de 5 modelos del notebook original (E0) |
| **Mejor CV** | **0,8300 ± 0,0010** | E11a: variables H12-H17 + *seed bagging* 5 semillas + LightGBM + LGBM-PS (CV inflada por sesgo de selección) |
| Mejor CV sin variables ajustadas a mano | 0,8204 ± 0,0004 | E11c: *bagging* 5 semillas, 5 modelos + LightGBM + LGBM-PS |
| **Mejor público** | **0,80206** | E11c |
| **Selección final recomendada** | **E11c + E11b** | Ver sección 6 |

**Lecciones principales**
1. **Lo que más mueve el F1 son las variables lingüísticas de contexto escritas a mano** (H1-H10 en el original: +2,2 puntos sobre la LR; H12-H17 en E10b: +1,2 puntos de CV). Un léxico genérico (HurtLex) o vectores aprendidos con tan pocos datos (Word2Vec, redes) no capturan ese contexto.
2. **Con 1.731 tweets, lo que funciona es reducir la varianza** (*seed bagging*) y sumar una o dos bases no lineales (LightGBM, LGBM-PS). Más clasificadores sobre los mismos n-gramas no aportan.
3. **Umbrales, reglas posteriores y ajuste de hiperparámetros no mejoran** la estimación honesta.
4. **El leaderboard público (~577 filas, ±2,5 puntos de ruido) no sirve para decidir**. El caso de E11a lo muestra: la mejor CV (0,8300) obtuvo el peor público de su tanda (0,79644), en parte porque su CV está inflada por sesgo de selección.
5. **El sesgo de selección se puede medir y controlar** con una versión genérica de las variables, con la frecuencia de los patrones en el test (solo conteos) y, en E13, con un conjunto de control reservado antes de diseñar las variables.

---

## 2. El reto y las reglas

### 2.1 Tarea
- **Clasificación multietiqueta** de tweets en español (corpus HatEval 2019, SemEval-2019 Task 5) con tres etiquetas binarias:
  - **HS** (*Hate Speech*): discurso de odio contra mujeres o inmigrantes.
  - **TR** (*Targeted*): el odio va dirigido a una persona concreta. TR = 1 implica HS = 1.
  - **AG** (*Aggressiveness*): el tweet es agresivo.
- **Datos:** `toxic_train.csv` con 1.731 filas y `toxic_test.csv` con 1.154 filas, separados por `;` y en latin-1. El corpus perdió los caracteres no ASCII (*cállate* → `cllate`).
- **Combinaciones en el train:** `000` 949, `111` 491, `101` 145, `100` 92, `110` 28, `001` 26. Prevalencias: HS 0,437, TR 0,300, AG 0,382.
- **Métrica de trabajo:** F1 de la clase positiva de cada etiqueta, promediado sobre HS, TR y AG (`f1_score(Y, Yp, average='macro')` sobre la matriz multietiqueta). La PDF del curso solo dice "F1-score". Que Kaggle use esta definición se dedujo de la primera submission: el 0,78516 cae dentro del rango de ruido de esta métrica (0,781-0,831) y fuera del rango del F1-macro de dos clases (0,827-0,865). Ver la sección 8.1 del notebook original.

### 2.2 Reglas (PDF `Competencia_Kaggle_2026.pdf` y reglas del proyecto)
- Se permiten bolsa de palabras, TF-IDF y Word2Vec **si el componente lo entrena el equipo**. También se permiten léxicos y corpus externos citados y con licencia compatible.
- **No se permite** usar modelos de lenguaje, embeddings, clasificadores ni transformers **preentrenados**. Todo modelo que intervenga en la predicción lo construye y entrena el equipo.
- **El test no se usa para entrenar.** En este proyecto se aplicó de forma estricta: el test nunca entra en un `fit` (ni de vectorizadores, ni de escaladores, ni de modelos). Solo se transforma.
- Máximo **3 envíos por día** y por equipo. Cierre y revelación del privado: **19 de octubre de 2026, 6:00 p. m.**
- Criterios mínimos: separación entrenamiento/validación sin fuga, comparación de alternativas con estrategia de selección explícita, F1 por etiqueta, análisis de errores, semillas y versiones, y referencias y licencias.

### 2.3 Cumplimiento de reglas por componente

| Componente | Dónde | ¿Preentrenado? | Ajuste | Cumple |
|---|---|---|---|---|
| Normalización (minúsculas, `xurl`/`xuser`, borrado de no ASCII, alargamientos) | `toxic_base.normalizar` | No (reglas deterministas) | No se ajusta | ✓ |
| TF-IDF de palabras 1-2 y de caracteres `char_wb` 2-5 (y `char` 2-6 en E3) | `toxic_base` | No | Solo con la partición de entrenamiento de cada fold; en el modelo final, solo con el train | ✓ |
| TruncatedSVD (300 dim.) para LightGBM, LGBM-PS y ExtraTrees | `toxic_base`, `ext_formulaciones` | No | Solo con la partición de entrenamiento | ✓ |
| Selección chi² (LGBM-chi2) | `ext_formulaciones` | No | Solo con la partición de entrenamiento | ✓ |
| Léxicos y patrones regex H1-H10, H12-H17, H19-H23 | `toxic_base`, `ext_variables`, `ext_variables2` | No: escritos por el equipo leyendo el train | Regex fijas; el escalador se ajusta dentro del fold | ✓ |
| HurtLex v1.2 (español) | Solo E5 | Léxico externo (no es un modelo), citado, CC BY-NC-SA 4.0 | Conteos por categoría | ✓ (no adoptado) |
| Word2Vec (gensim, skip-gram) | Solo E4 | No: entrenado desde cero | Solo con los textos de la partición de entrenamiento | ✓ (no adoptado) |
| CNB, LR, SVM calibrado, NB-LR, Powerset, LightGBM, LGBM-PS, ExtraTrees, kNN, BNB, Jerarq-LR, Cadena | `toxic_base`, `ext_formulaciones` | No: entrenados desde cero (scikit-learn, LightGBM) | Dentro del fold | ✓ |
| Redes BolsaEmb, BiGRU, CharCNN, Mix (PyTorch) | Solo E10a | No: embeddings aprendidos desde cero | Vocabulario y pesos solo con la partición de entrenamiento | ✓ (no adoptado) |
| LMs Kneser-Ney por clase | Solo E10d | No: implementados a mano con `Counter` | Solo con la partición de entrenamiento, con CV interna | ✓ (no adoptado) |
| Metamodelo LR del stacking | `toxic_base.stacking`, `stacking_bagged` | No | Sobre probabilidades OOF del train | ✓ |
| Corpus etiquetado de HatEval 2019 | — | — | **Descartado a propósito**: el test sale de ahí; usarlo sería fuga de etiquetas | — |

> **Nota de transparencia.** En E10b y en E13 se contó **con qué frecuencia aparece cada patrón en el test** (solo conteos sobre el texto, sin etiquetas). Se hizo como diagnóstico del sesgo de selección: un patrón mucho más raro en el test que en el train sugiere que está ajustado a la redacción de tweets concretos del train. **No se cambió ninguna variable ni ninguna decisión por esos conteos**, y el test nunca entró en un ajuste.

---

## 3. Metodología de evaluación

- **CV estratificada repetida.** 5 particiones estratificadas por la combinación HS-TR-AG (`StratifiedKFold(5, shuffle=True)`), repetidas con las semillas **42, 43 y 44**. Se reporta la media ± la desviación entre semillas y el F1 medio por semilla. Las particiones son las mismas para todos los modelos, así que sus OOF son comparables.
- **OOF (*out-of-fold*).** Cada fila del train recibe la predicción de un modelo que no la vio. Todo bloque (TF-IDF, SVD, escalador, Word2Vec, LMs) se ajusta solo con los 4/5 de entrenamiento de cada fold. Las probabilidades OOF y de test quedan en caché en `oof/`.
- **Stacking.** Un metamodelo `LogisticRegression(C=1, class_weight='balanced')` por etiqueta recibe las probabilidades OOF de las bases (3 por base). Se evalúa con **otra CV de 5 particiones con semilla + 1**, así que nunca predice una fila con la que se entrenó. En test, el metamodelo se entrena con todos los OOF.
- **Restricción jerárquica.** Toda predicción aplica TR := TR · HS. Las filas `#¿NOMBRE?` (texto perdido por Excel) reciben `000`.
- ***Seed bagging*** (desde E6). Los OOF de cada base se promedian sobre 5 semillas de partición (**42-46**) antes del stacking. En test, cada base aporta el promedio de sus 5 × 5 = 25 modelos de partición (`pred_test_folds`), entrenados con 4/5 del train igual que los OOF. La semilla del metamodelo recorre 42, 43 y 44. En las filas con *bagging*, la desviación ± solo refleja la semilla del metamodelo.
- **Criterio de adopción** (fijado en E0 para todas las pruebas): mejora **≥ +0,003** en el F1 medio **y** mejora en **al menos 2 de las 3 semillas**.
- **Conjuntos definidos de antemano.** Las combinaciones de bases, umbrales y metamodelos se fijaron antes de evaluar (no hubo búsqueda exhaustiva), para no sobreajustar la selección a la CV.
- **Por qué se decide con la CV y no con el público.** El leaderboard público califica ~50 % del test (~577 filas). Con ese tamaño, el ruido de muestreo del F1 medio es de unos **±2,5 puntos** (percentiles 5-95: 0,781-0,831 para un modelo de CV 0,809). Las diferencias entre versiones (0,2-1,2 puntos) quedan dentro de ese ruido. El puesto final lo define el **privado**, la otra mitad del test.

---

## 4. Experimentos

Formato de las tablas: F1 de la clase positiva por etiqueta, F1 medio ± desviación entre semillas (cuando existe) y F1 medio por semilla 42 / 43 / 44.

### 4.0 Notebook original (`../TweetToxic_modelo.ipynb`)

**Qué se hizo.** Lectura de los datos y de ~900 tweets, normalización a partir de tres defectos del corpus (tildes borradas, errores de Excel `#¿NOMBRE?`, filas entrecomilladas siempre con AG = 1), 11 hipótesis verificadas con P(etiqueta | patrón) frente a la prevalencia, tres bloques de representación y cinco modelos combinados por *stacking*.

| # | Hipótesis (resumen) | Evidencia |
|---|---|---|
| H1 | Los insultos femeninos son la señal más fuerte de HS, TR y AG | P(HS) 0,44 → 0,55 (0,65 sin intensificador) |
| H2 | *Puta* como intensificador (*la puta boca*, *ni puta idea*) no es odio | P(HS) ≈ 0,07 |
| H3 | El género del blanco decide: *hijo de puta* no es HS, *hija de puta* sí; la concordancia masculina anula el insulto femenino | 0,05 frente a 0,69; concordancia masc. ≈ 0,14, fem. ≈ 0,78 |
| H4 | *Cállate* solo indica odio con un insulto femenino | 0,10 sin insulto, 0,63 con insulto |
| H5 | Insultos de grupo migrante: HS genérico (TR ≈ 0, AG alto) | *putos* + grupo: 100 % odio agresivo |
| H6 | Encuadre de invasión/expulsión: HS agresivo | Confirmada |
| H7 | Palabras clave ambiguas suelen ser benignas (*árabe*, *güero*, *cómemela*) | *árabe* ≈ 0,19 en general, ≈ 0,04 en música/comida |
| H8 | Generalizaciones y chistes sobre mujeres: HS con TR y AG bajos | Confirmada |
| H9 | Con HS = 1, la mención inicial o el insulto femenino llevan TR a ≈ 1; el tema migrante a ≈ 0 | P(TR) ≈ 0,95 frente a ≈ 0,14 |
| H10 | Las filas entrecomilladas tienen AG = 1 (artefacto) | 39/39 |
| H11 | Los n-gramas de caracteres generalizan mejor por las tildes perdidas | A medias: solos 0,757; combinados +1 punto |

**Representación.** TF-IDF de palabras 1-2 (`min_df=2`, `sublinear_tf`, incluye tokens de una letra), TF-IDF `char_wb` 2-5 y bloque de léxico (38 variables H1-H10, estandarizado y ponderado con `PESO_LEX=0,3`). Sin *stopwords* ni *stemming*, a propósito (H2, H3, H9).

**Ablación y modelos (CV de una semilla, del notebook original).**

| Configuración | F1 HS | F1 TR | F1 AG | F1 medio | EMR |
|---|---|---|---|---|---|
| LR · palabras | 0,754 | 0,817 | 0,741 | 0,771 | 0,713 |
| LR · caracteres | 0,759 | 0,785 | 0,726 | 0,757 | 0,698 |
| LR · palabras + caracteres | 0,777 | 0,817 | 0,749 | 0,781 | 0,723 |
| LR · palabras + caracteres + léxico | 0,793 | 0,823 | 0,791 | 0,803 | 0,755 |
| CNB | 0,759 | 0,780 | 0,709 | 0,749 | 0,716 |
| SVM (Platt) | 0,791 | 0,830 | 0,788 | 0,803 | 0,756 |
| NB-LR | 0,796 | 0,821 | 0,787 | 0,801 | 0,760 |
| Powerset | 0,796 | 0,835 | 0,788 | 0,806 | 0,780 |
| Ensamble LR + Powerset | 0,798 | 0,836 | 0,791 | 0,809 | 0,769 |
| **Stacking de 5 modelos** | **0,805** | **0,839** | **0,802** | **0,815** | 0,775 |

También se probaron umbrales por etiqueta con CV anidada sobre el ensamble (0,806, peor que 0,5) y la sensibilidad a `C`, `PESO_LEX` y rangos de n-gramas (rango 0,806-0,810: zona plana).

**Público.** Ensamble `toxic_submission_v1.csv` **0,78516**; stacking `toxic_submission.csv` **0,79160** (4.º puesto en ese momento). La primera submission se había elegido con el F1-macro de dos clases (0,847 en CV), y eso explica por qué el 0,785 parecía bajo.

---

### E0 · Línea base con CV repetida (`E0_base_cv_repetida.ipynb`)

**Hipótesis.** La CV de una sola semilla del notebook original puede ser optimista. Hace falta una referencia más honesta antes de comparar mejoras de 0,3-0,6 puntos.

**Qué se hizo.** Se extrajo el pipeline original a `toxic_base.py` sin cambios y se midió con 3 semillas. Se verificó que con la semilla 42 el CSV generado es idéntico al enviado (0 filas distintas).

| Configuración | F1 HS | F1 TR | F1 AG | F1 medio | ± | Por semilla |
|---|---|---|---|---|---|---|
| CNB | 0,7509 | 0,7794 | 0,7086 | 0,7463 | 0,0023 | 0,749 / 0,744 / 0,746 |
| LR | 0,7924 | 0,8246 | 0,7899 | 0,8023 | 0,0020 | 0,803 / 0,805 / 0,800 |
| SVM | 0,7890 | 0,8279 | 0,7882 | 0,8017 | 0,0009 | 0,803 / 0,801 / 0,801 |
| NB-LR | 0,7916 | 0,8231 | 0,7883 | 0,8010 | 0,0009 | 0,801 / 0,802 / 0,800 |
| Powerset | 0,7937 | 0,8284 | 0,7889 | 0,8037 | 0,0021 | 0,806 / 0,804 / 0,801 |
| Ensamble LR + Powerset | 0,7975 | 0,8299 | 0,7921 | 0,8065 | 0,0015 | 0,809 / 0,806 / 0,805 |
| **Stacking 5 modelos** | **0,8038** | **0,8345** | **0,7994** | **0,8126** | **0,0021** | 0,815 / 0,810 / 0,813 |

**Conclusión.** Referencia: **0,8126 ± 0,0021**. El 0,815 original salió de una semilla favorable (0,8152 con la semilla 42). `toxic_submission_E0.csv` es idéntico a la base y **no se envía**.

---

### E1 · Umbrales por etiqueta sobre el stacking (`E1_umbrales_stacking.ipynb`)

**Hipótesis.** El stacking predice HS en el 39 % del test frente al 44 % del train. Bajar el umbral podría subir el F1 de la clase positiva. Se mide con CV anidada (el umbral de cada partición se elige con las otras 4) y con umbrales fijos.

| Configuración | F1 HS | F1 TR | F1 AG | F1 medio | ± | Por semilla |
|---|---|---|---|---|---|---|
| E0 · umbral 0,5 | 0,8038 | 0,8345 | 0,7994 | **0,8126** | 0,0021 | 0,815 / 0,810 / 0,813 |
| Umbral por etiqueta, CV anidada, rejilla 0,20-0,70 | 0,8049 | 0,8316 | 0,7978 | 0,8114 | 0,0022 | 0,814 / 0,812 / 0,808 |
| Umbral por etiqueta, CV anidada, rejilla 0,30-0,60 | 0,8057 | 0,8315 | 0,7978 | 0,8117 | 0,0019 | 0,814 / 0,812 / 0,809 |
| Umbral fijo 0,40 | 0,8043 | 0,8323 | 0,7993 | 0,8120 | 0,0021 | 0,810 / 0,815 / 0,811 |
| Umbral fijo 0,45 | 0,8044 | 0,8334 | 0,7974 | 0,8117 | 0,0017 | 0,814 / 0,812 / 0,810 |
| Umbral fijo 0,55 | 0,8036 | 0,8331 | 0,7952 | 0,8106 | 0,0011 | 0,811 / 0,809 / 0,812 |

Umbrales óptimos por semilla: HS 0,48 / 0,44 / 0,34; TR 0,54 / 0,56 / 0,62; AG 0,52 / 0,40 / 0,38.

**Conclusión: no se adopta.** Los umbrales óptimos son inestables entre semillas (se estaría ajustando ruido) y el `class_weight='balanced'` del metamodelo ya deja 0,5 cerca del óptimo.

---

### E2 · Reglas posteriores a la predicción (`E2_reglas_post.ipynb`)

**Hipótesis.** Tres reglas deterministas: (1) comillas → AG = 1 (39/39 en train; 25 filas en test); (2) misma predicción para textos duplicados del test; (3) algo mejor que `000` para las 6 filas `#¿NOMBRE?` del test.

| Configuración | F1 medio | ± |
|---|---|---|
| E0 · stacking | 0,8126 | 0,0021 |
| + comillas → AG = 1 | 0,8126 | 0,0021 |

**Conclusión: no se adopta ninguna regla, porque no cambian nada.** El modelo ya predice AG = 1 en el 100 % de las filas entrecomilladas (OOF y test). Los 5 textos duplicados del test son justamente las filas `#¿NOMBRE?`, que ya reciben `000`. El train solo tiene una fila de ese tipo (`#NOME?`, etiquetada `000`).

---

### E3 · Más modelos base (`E3_bases_nuevas.ipynb`)

**Hipótesis.** Bases que se equivocan en tweets distintos darían más información al metamodelo. Nuevas: **LR-charc** y **NB-LR-charc** (caracteres `char` 2-6 que cruzan palabras), **LGBM** (LightGBM sobre SVD(300) + léxico crudo, el único no lineal) y **Cadena** (HS → AG → TR).

| Modelo solo | F1 HS | F1 TR | F1 AG | F1 medio | ± |
|---|---|---|---|---|---|
| LR-charc | 0,7914 | 0,8278 | 0,7921 | 0,8038 | 0,0033 |
| NB-LR-charc | 0,7903 | 0,8214 | 0,7863 | 0,7993 | 0,0017 |
| LGBM | 0,7858 | 0,8182 | 0,7743 | 0,7928 | 0,0007 |
| Cadena | 0,7924 | 0,8168 | 0,7868 | 0,7987 | 0,0014 |

Correlación de las OOF de HS con LR: LR-charc 0,995, Cadena 1,000, NB-LR-charc 0,965, LGBM 0,910.

| Stacking | F1 HS | F1 TR | F1 AG | F1 medio | ± | Por semilla |
|---|---|---|---|---|---|---|
| E0 · 5 originales | 0,8038 | 0,8345 | 0,7994 | 0,8126 | 0,0021 | 0,815 / 0,810 / 0,813 |
| + LR-charc + NB-LR-charc | 0,8046 | 0,8336 | 0,7978 | 0,8120 | 0,0018 | 0,813 / 0,810 / 0,813 |
| + LGBM | 0,8072 | 0,8336 | 0,7982 | 0,8130 | 0,0013 | 0,814 / 0,813 / 0,811 |
| + Cadena | 0,8021 | 0,8319 | 0,7989 | 0,8110 | 0,0023 | 0,814 / 0,808 / 0,811 |
| Los 9 modelos | 0,8038 | 0,8333 | 0,7981 | 0,8117 | 0,0015 | 0,810 / 0,813 / 0,813 |
| LR + Powerset + NB-LR-charc + LGBM | 0,8063 | 0,8322 | 0,7996 | 0,8127 | 0,0007 | 0,812 / 0,812 / 0,814 |

**Conclusión: no se adopta.** El stacking está saturado: todas las variantes quedan dentro de ±0,002. LGBM es el único que mueve algo (+0,0004), por ser el menos correlacionado. Se retomó en E8b con *bagging*.

---

### E4 · Word2Vec entrenado por el equipo (`E4_word2vec.ipynb`)

**Hipótesis.** Vectores densos harían que *zorra* y *guarra* compartan información y generalizarían a grafías raras. Word2Vec skip-gram (gensim), ventana 5, `min_count=2`, 40 épocas, 100 dim., semilla 0, un hilo, **entrenado desde cero solo con la partición de entrenamiento de cada fold**. Representación: media y máximo de los vectores (200 columnas).

| Configuración | F1 HS | F1 TR | F1 AG | F1 medio | ± |
|---|---|---|---|---|---|
| LR (TF-IDF + léxico) | 0,7924 | 0,8246 | 0,7899 | 0,8023 | 0,0020 |
| LR-w2v (Word2Vec + léxico) | 0,7479 | 0,7851 | 0,7568 | 0,7633 | 0,0058 |
| LR-w2v+tfidf | 0,7543 | 0,7771 | 0,7611 | 0,7642 | 0,0008 |
| Stacking E0 | 0,8038 | 0,8345 | 0,7994 | 0,8126 | 0,0021 |
| Stacking + LR-w2v | 0,8036 | 0,8329 | 0,7976 | 0,8114 | 0,0013 |
| Stacking + LR-w2v+tfidf | 0,8044 | 0,8338 | 0,7961 | 0,8114 | 0,0014 |

**Conclusión: no se adopta.** Con ~1.400 tweets por partición (vocabulario de 1.977 palabras) los vectores son ruidosos: los vecinos de *moros* son *putos, negros, trabajar*. Trabajo futuro: entrenarlo con un corpus grande de tweets en español sin etiquetas, con licencia clara.

---

### E5 · Léxico externo HurtLex (`E5_hurtlex.ipynb`)

**Hipótesis.** Un léxico de palabras ofensivas cubriría vocabulario que no está en el train. HurtLex v1.2 en español (5.006 lemas, 17 categorías; CC BY-NC-SA 4.0): 18 columnas de conteo en el bloque de léxico.

| Configuración | F1 medio sin HurtLex | F1 medio con HurtLex |
|---|---|---|
| LR | 0,8023 | 0,8005 |
| SVM | 0,8017 | 0,7969 |
| NB-LR | 0,8010 | 0,7958 |
| Powerset | 0,8037 | 0,8002 |
| **Stacking** | **0,8126** | **0,8088 ± 0,0012** (−0,004) |

**Conclusión: no se adopta (empeora).** En casi todas las categorías P(HS | coincidencia) queda cerca de la prevalencia (0,44): *animales* (por *perra*, 1.042 tweets) 0,54; *prostitución* (por *puta*, 957) 0,54. El corpus se **recolectó con esas mismas palabras**, que aparecen igual en tweets con y sin odio.

---

### E6 · Metamodelo y *seed bagging* (`E6_stacking_mejorado.ipynb`)

**Hipótesis.** (1) Otro metamodelo combinaría mejor. (2) Promediar los OOF de varias semillas de partición reduce su varianza.

| Metamodelo | F1 medio | ± |
|---|---|---|
| E0 · LR C=1, balanced | 0,8126 | 0,0021 |
| LR C=0,1 | 0,8135 | 0,0025 |
| LR C=0,3 | 0,8135 | 0,0033 |
| LR C=3 | 0,8120 | 0,0024 |
| LR sin `class_weight` | 0,8068 | 0,0015 |
| LightGBM (4 hojas) | 0,8114 | 0,0024 |
| LR + 8 variables de léxico | 0,8124 | 0,0038 |

*Seed bagging* por modelo base (1 semilla → OOF promediado de 3): CNB +0,0050, LR +0,0017, SVM +0,0046, NB-LR +0,0042, Powerset +0,0020.

| Stacking | F1 HS | F1 TR | F1 AG | F1 medio | ± | Por semilla del meta |
|---|---|---|---|---|---|---|
| E0 · sin *bagging* | 0,8038 | 0,8345 | 0,7994 | 0,8126 | 0,0021 | 0,815 / 0,810 / 0,813 |
| *Bagging* 3 semillas (42-44) | 0,8123 | 0,8422 | 0,8029 | 0,8191 | 0,0014 | 0,818 / 0,818 / 0,821 |
| ***Bagging* 5 semillas (42-46)** | 0,8092 | 0,8368 | 0,7988 | **0,8150** | 0,0007 | 0,814 / 0,815 / 0,815 |

**Conclusión: candidato.** Las variantes del metamodelo son ruido. El *bagging* de 5 semillas da +0,0024 en las 3 semillas: no llega al +0,003, pero es consistente y tiene una explicación clara (reducción de varianza). Cambia solo 19 filas del test. **Público: 0,79100** (empate con la base 0,79160).

---

### E7 · Regularización por etiqueta (`E7_ajuste_por_etiqueta.ipynb`)

**Hipótesis.** Un `C` distinto por etiqueta o `min_df=1` ajustarían mejor cada etiqueta.

| Modelo | C=1 | C=2 | C=4 | C=8 | C=16 |
|---|---|---|---|---|---|
| LR (F1 medio) | 0,7987 | 0,8008 | 0,8023 | 0,8021 | 0,8014 |
| Powerset (F1 medio) | 0,8032 | 0,8037 | 0,8037 | 0,8023 | 0,8018 |

| Configuración LR | F1 medio | ± |
|---|---|---|
| C=4 (E0) | 0,8023 | 0,0020 |
| C por etiqueta {HS: 4, TR: 8, AG: 8} (optimista) | 0,8038 | 0,0010 |
| `min_df=1` | 0,8006 | 0,0032 |

**Conclusión: no se adopta.** La zona de hiperparámetros es plana (menos de 0,004 entre C=1 y C=16). El C por etiqueta se eligió sobre la misma CV y aun así solo gana +0,0015.

---

### E8 · Candidatos que cambian más filas (`E8_candidatos_envio.ipynb`)

**Motivo.** E6 cambia tan pocas filas que el público no puede distinguirlo de la base. Dos variantes justificadas: **E8a** (E6 con umbral 0,45, porque se predice menos HS que la prevalencia) y **E8b** (*bagging* de 5 semillas con los 5 modelos + LightGBM, la base menos correlacionada).

| Configuración | F1 HS | F1 TR | F1 AG | F1 medio | ± | Por semilla | Público |
|---|---|---|---|---|---|---|---|
| E6 · *bagging* 5, umbral 0,5 | 0,8092 | 0,8368 | 0,7988 | 0,8150 | 0,0007 | 0,814 / 0,815 / 0,815 | 0,79100 |
| E8a · E6 con umbral 0,45 | 0,8108 | 0,8387 | 0,8023 | 0,8173 | 0,0001 | 0,817 / 0,817 / 0,817 | 0,79637 |
| **E8b · *bagging* 5 modelos + LGBM** | 0,8071 | 0,8405 | 0,8062 | **0,8179** | 0,0012 | 0,819 / 0,818 / 0,816 | **0,80168** |

**Conclusión.** Ambas mejoran a E6 en las 3 semillas (+0,002-0,003, en el límite del ruido). E8a cambia 31 filas frente a E6 y E8b 44. E8b pasa a ser la nueva referencia (B6 = CNB, LR, SVM, NB-LR, Powerset y LGBM).

---

### E9 · Variantes del *bagging* + LightGBM (`E9_variantes_bagging.ipynb`)

**Hipótesis.** Extender E8b: más bases (LR-charc, NB-LR-charc, Cadena), quitar CNB, metamodelo C=0,3 y umbrales 0,45. 16 combinaciones definidas de antemano.

| Configuración (selección de las 16) | F1 HS | F1 TR | F1 AG | F1 medio | ± |
|---|---|---|---|---|---|
| **E9a · los 9 modelos** | 0,8107 | 0,8408 | 0,8036 | **0,8184** | 0,0002 |
| **E9b · E8b, meta C=0,3** | 0,8102 | 0,8402 | 0,8045 | 0,8183 | 0,0003 |
| **E9c · sin CNB, umbrales (0,45; 0,5; 0,45)** | 0,8104 | 0,8390 | 0,8055 | 0,8183 | 0,0014 |
| 5 + LGBM + Cadena | 0,8099 | 0,8389 | 0,8053 | 0,8180 | 0,0005 |
| E8b · 5 + LGBM | 0,8071 | 0,8405 | 0,8062 | 0,8179 | 0,0012 |
| 5 + LGBM + charc | 0,8065 | 0,8407 | 0,8044 | 0,8172 | 0,0005 |
| Sin CNB, umbral 0,5 | 0,8076 | 0,8385 | 0,8043 | 0,8168 | 0,0016 |
| 5 + LGBM + charc · umbral 0,45 (la peor) | 0,8078 | 0,8367 | 0,8048 | 0,8164 | 0,0012 |

**Conclusión: meseta** (0,8164-0,8184, todas a ±0,002 de E8b). Se enviaron las 3 mejores que difieren entre sí. **Público:** E9a 0,79940, E9b 0,79734, E9c 0,79663, todas por debajo de E8b pese a una CV igual o mayor: es ruido del público.

---

### E10a · Redes neuronales desde cero (`E10a_neuronal.ipynb`, `ext_neuronal.py`)

**Hipótesis.** Una red que lee la secuencia (quién insulta a quién) daría diversidad. PyTorch, embeddings aprendidos desde cero, 3 sigmoides con BCE y `pos_weight`, AdamW, hasta 40 épocas con *early stopping* (paciencia 5) sobre un 15 % interno, 3 inicializaciones promediadas.

| Modelo | F1 HS | F1 TR | F1 AG | F1 medio | ± |
|---|---|---|---|---|---|
| LR (referencia) | 0,7924 | 0,8246 | 0,7899 | 0,8023 | 0,0020 |
| NN-BolsaEmb-lex | 0,7698 | 0,8151 | 0,7722 | 0,7857 | 0,0036 |
| NN-BiGRU-lex | 0,7588 | 0,8052 | 0,7534 | 0,7724 | 0,0022 |
| NN-BolsaEmb | 0,7074 | 0,7706 | 0,7004 | 0,7261 | 0,0034 |
| NN-BiGRU (solo semilla 42) | 0,7047 | 0,7952 | 0,7153 | 0,7384 | — |
| NN-CharCNN / NN-Mix (primer fold, semilla 42) | — | — | — | 0,690 / 0,713 | descartadas |
| Stacking E8b · B6 | 0,8071 | 0,8405 | 0,8062 | 0,8179 | 0,0012 |
| B6 + NN-BolsaEmb-lex | 0,8083 | 0,8385 | 0,8056 | 0,8175 | 0,0006 |

**Conclusión: no se adopta.** Con 1.731 tweets y sin vectores preentrenados (prohibidos), el orden de las palabras no compensa. Las versiones con léxico solo reciben las mismas señales que ya usan las otras bases.

---

### E10b · Variables nuevas a partir del análisis de errores (`E10b_variables_errores.ipynb`, `ext_variables.py`)

**Hipótesis.** Si el valor está en patrones de contexto escritos leyendo el corpus, repetir el ejercicio sobre los **errores OOF de E8b** (145 FP y 146 FN de HS, 96 FP y 73 FN de TR) encontraría patrones que el modelo todavía no capta.

| # | Hipótesis | Variable | n | P(HS) | Pred. E8b |
|---|---|---|---|---|---|
| H12 | *mi/su* + insulto femenino = mascota o afecto (se excluye *eres mi puta*, n=12, P(HS)=0,75) | `posesivo_fem_sin_eres` | 23 | 0,13 | 0,48 |
| H13 | Insulto negado o refutado (*no es una guarra por…*) | `negacion_fem` | 13 | 0,46 | 0,85 |
| H14 | *Árabe* en estereotipo u hostilidad (al revés que H7) | `arabe_hostil` | 44 | 0,57 | 0,16 |
| H15 | Migrante + deshumanización o expulsión/violencia: HS y AG, TR = 0 | `hostilidad_migrante`, `expulsion_migrante` | 29 | 0,93 (AG 0,86) | 0,55 |
| H16 | Demostrativo o *putos* + grupo en plural | `demostrativo_grupo` | 28 | 0,89 (AG 0,86) | 0,64 |
| H17 | Con HS = 1, demostrativo femenino (*esta puta*, *esa vieja*) → TR | `demostrativo_fem` | 18 con HS=1 | P(TR)=1,00 | 0,67 |

Descartadas: titular de prensa sobre migración (P(HS)=0,40, igual al tema migrante), risa + insulto femenino (0,79, ya bien predicho), *hijos de puta* en plural (0,18), estereotipo doméstico (n=7).

| Configuración | F1 HS | F1 TR | F1 AG | F1 medio | ± | Por semilla |
|---|---|---|---|---|---|---|
| E0 · stacking 5 modelos | 0,8038 | 0,8345 | 0,7994 | 0,8126 | 0,0021 | 0,815 / 0,810 / 0,813 |
| E0 + H12-H17 | 0,8183 | 0,8424 | 0,8120 | 0,8242 | 0,0011 | 0,826 / 0,824 / 0,823 |
| E0 + H12-H17 genérica | 0,8131 | 0,8391 | 0,8077 | 0,8200 | 0,0035 | 0,822 / 0,823 / 0,815 |
| E6 + H12-H17 | 0,8245 | 0,8458 | 0,8144 | 0,8283 | 0,0020 | 0,826 / 0,831 / 0,828 |
| E8b · *bagging* B6 | 0,8071 | 0,8405 | 0,8062 | 0,8179 | 0,0012 | 0,819 / 0,818 / 0,816 |
| **E8b + H12-H17** | 0,8211 | 0,8497 | 0,8188 | **0,8299** | 0,0014 | 0,829 / 0,829 / 0,832 |

Ablación sobre E0 + H12-H17 (0,8242), quitando una variable: posesivo 0,8179 (−0,006), demostrativo femenino 0,8226, demostrativo + grupo 0,8232, negación 0,8245, expulsión 0,8245, hostilidad 0,8249, árabe hostil 0,8256 (quitarla sube). Cada LR, SVM, NB-LR y Powerset gana +1,1 a +1,5 puntos por separado; CNB no cambia porque no usa el léxico.

**Controles del sesgo de selección.**
1. La **versión genérica** (sin palabras copiadas de tweets concretos: *flojo, lapidar, subfusil, tus queridos, mina…*) conserva +0,0074 de los +0,0116 sobre E0, con más varianza.
2. **Frecuencia en el test** (solo conteos, sin etiquetas), test/train por tweet: posesivo 1,11, demostrativo femenino 1,26; negación 0,35, expulsión 0,43, demostrativo + grupo 0,48, árabe hostil 0,51, hostilidad 0,57. Los patrones más hechos a medida aparecen la mitad de veces en el test.

Se probó también una normalización que reinserta la vocal borrada (`cllate` → `callate`, aprendida solo del train): E0 0,8138 (+0,001), E10b 0,8237 (nada). No se adopta.

**Conclusión: adoptado con cautela.** La mejora es grande y consistente en las 3 semillas, pero la CV está inflada por sesgo de selección. La ganancia real esperada está más cerca de la versión genérica y se concentra en H12 y H17. Combinado en E11.

---

### E10c · Otras formulaciones y familias de modelos (`E10c_formulaciones.ipynb`, `ext_formulaciones.py`)

**Hipótesis.** Modelos que formulan el problema de otra forma o de otra familia tendrían errores menos correlacionados.

| Modelo solo | Descripción | F1 medio | ± | Corr. media con LR |
|---|---|---|---|---|
| Jerarq-LR | TR y AG condicionados a HS | 0,7985 | 0,0010 | 0,988 |
| ExtraTrees | Árboles aleatorizados sobre SVD + léxico | 0,7885 | 0,0026 | 0,935 |
| kNN | 25 vecinos, coseno | 0,7411 | 0,0024 | 0,819 |
| BNB | Bernoulli NB, presencia de palabras | 0,7373 | 0,0008 | 0,830 |
| LGBM-PS | LightGBM *Label Powerset* (6 combinaciones) | 0,7915 | 0,0032 | 0,937 |
| LGBM-chi2 | LightGBM sobre TF-IDF filtrado con chi² | 0,7837 | 0,0012 | 0,922 |

kNN se descartó en el filtro rápido (resta al stacking). Los otros cinco se calcularon con 5 semillas:

| Stacking con *bagging* (5 semillas) | F1 HS | F1 TR | F1 AG | F1 medio | ± | Δ vs E8b | Semillas que mejoran |
|---|---|---|---|---|---|---|---|
| **B6 + LGBM-PS** | 0,8123 | 0,8400 | 0,8088 | **0,8204** | 0,0004 | +0,0025 | 3 |
| B6 + ExtraTrees + LGBM-PS | 0,8120 | 0,8409 | 0,8075 | 0,8201 | 0,0005 | +0,0022 | 3 |
| B6 + Jerarq-LR | 0,8082 | 0,8389 | 0,8091 | 0,8187 | 0,0004 | +0,0008 | 3 |
| E8b · B6 | 0,8071 | 0,8405 | 0,8062 | 0,8179 | 0,0012 | 0 | — |
| B6 + BNB | 0,8073 | 0,8391 | 0,8041 | 0,8168 | 0,0007 | −0,0011 | 1 |
| B6 + los 5 nuevos | 0,8093 | 0,8351 | 0,8054 | 0,8166 | 0,0002 | −0,0013 | 1 |
| Sin CNB + 3 árboles | 0,8103 | 0,8364 | 0,8029 | 0,8166 | 0,0010 | −0,0013 | 1 |
| B6 + LGBM-chi2 | 0,8084 | 0,8356 | 0,8046 | 0,8162 | 0,0030 | −0,0017 | 1 |
| B6 + ExtraTrees | 0,8071 | 0,8395 | 0,8013 | 0,8159 | 0,0012 | −0,0020 | 1 |
| B6 + 3 árboles | 0,8082 | 0,8346 | 0,8027 | 0,8152 | 0,0012 | −0,0027 | 1 |

**Conclusión: pequeño aporte, no cumple el criterio.** Solo LGBM-PS suma de forma consistente (+0,0025, 3/3 semillas, desviación 0,0004): sirve la formulación conjunta, no la familia de árboles. Varias bases casi colineales a la vez empeoran. Cambia 25 filas del test frente a E8b. Se usó en E11.

---

### E10d · Modelos de lenguaje Kneser-Ney por clase (`E10d_lm_por_clase.ipynb`, `ext_lm.py`)

**Hipótesis.** Un modelo generativo (cómo se escribe un tweet de odio frente a uno que no lo es) sería una vista distinta. Para cada etiqueta, un LM por clase con KN modificado interpolado, implementado a mano: caracteres (órdenes 3-6) y palabras (1-3). Variables: *log-likelihood ratio* por orden → LR. Las LLR de entrenamiento salen de una CV interna para evitar fuga.

| Modelo | F1 HS | F1 TR | F1 AG | F1 medio | ± | Corr. media con LR |
|---|---|---|---|---|---|---|
| LR (referencia) | 0,7924 | 0,8246 | 0,7899 | 0,8023 | 0,0020 | — |
| LM-KN | 0,7621 | 0,7917 | 0,7214 | 0,7584 | 0,0010 | 0,835 |
| LM-KN-PS (Powerset generativo) | 0,7389 | 0,7740 | 0,6841 | 0,7323 | 0,0042 | 0,818 |
| LM-KN+lex | 0,7959 | 0,8133 | 0,7896 | 0,7996 | 0,0026 | 0,961 |

| Stacking con *bagging* (5 semillas) | F1 medio | ± | Δ por semilla |
|---|---|---|---|
| E8b · B6 | 0,8179 | 0,0012 | — |
| B6 + LM-KN | 0,8162 | 0,0007 | −0,0018 / −0,0029 / −0,0004 |
| B6 + LM-KN+lex | 0,8189 | 0,0008 | −0,0010 / +0,0015 / +0,0026 |

**Conclusión: no se adopta.** El LM es una vista distinta (correlación 0,835, como CNB) pero débil, y esa diversidad no se convierte en F1. LM-KN+lex (+0,0010) queda dentro de la meseta y su aporte puede venir del léxico.

---

### E11 · Combinación final (`E11_combinacion_final.ipynb`)

**Hipótesis.** Ver si LGBM-PS (E10c) suma sobre las variables H12-H17 (E10b) y generar los candidatos de envío.

| Configuración | F1 HS | F1 TR | F1 AG | F1 medio | ± | Por semilla | Público |
|---|---|---|---|---|---|---|---|
| base · B6 (= E8b) | 0,8071 | 0,8405 | 0,8062 | 0,8179 | 0,0012 | 0,819 / 0,818 / 0,816 | 0,80168 |
| **E11c** · base · B6 + LGBM-PS | 0,8123 | 0,8400 | 0,8088 | 0,8204 | 0,0004 | 0,820 / 0,820 / 0,821 | **0,80206** |
| H12-H17 · B6 | 0,8211 | 0,8497 | 0,8188 | 0,8299 | 0,0014 | 0,829 / 0,829 / 0,832 | — |
| **E11a** · H12-H17 · B6 + LGBM-PS | 0,8243 | 0,8475 | 0,8183 | **0,8300** | 0,0010 | 0,829 / 0,831 / 0,831 | 0,79644 |
| H12-H17 genérica · B6 | 0,8153 | 0,8443 | 0,8105 | 0,8234 | 0,0017 | 0,822 / 0,823 / 0,826 | — |
| **E11b** · H12-H17 genérica · B6 + LGBM-PS | 0,8174 | 0,8453 | 0,8105 | 0,8244 | 0,0015 | 0,822 / 0,825 / 0,826 | 0,79895 |

Filas distintas frente a E8b: E11a 52, E11b 46, E11c 25.

**Conclusión.** H12-H17 es la mejora grande en CV. LGBM-PS suma sobre la base (+0,0025) pero no sobre H12-H17 (aportan señal parecida). En el público el orden se invierte (E11c > E11b > E11a), lo que es coherente con el sesgo de selección de E11a, aunque las tres diferencias caben en el ruido de ±2,5 puntos.

---

### E12 · Promedios de stacks y selección hacia adelante (script, sin notebook)

**Hipótesis.** (1) Promediar las probabilidades de los stacks base, genérica y completa reduciría la varianza. (2) Una selección hacia adelante de bases extra sobre B7 (B6 + LGBM-PS) encontraría alguna que sume.

| Promedio de stacks | F1 medio |
|---|---|
| base + genérica | 0,8242 |
| base + genérica + completa | 0,8260 |
| genérica + completa | 0,8266 |
| (referencia: completa sola) | 0,8300 |

| Base extra sobre **base B7** (0,8204) | F1 medio | Base extra sobre **genérica B7** (0,8244) | F1 medio |
|---|---|---|---|
| + Jerarq-LR | 0,8206 | + Jerarq-LR | 0,8242 |
| + ExtraTrees | 0,8201 | + ExtraTrees | 0,8247 |
| + BNB | 0,8201 | + BNB | 0,8250 |
| + LGBM-chi2 | 0,8176 | + LGBM-chi2 | 0,8256 |
| + Cadena | 0,8211 | | |
| + LR-charc | 0,8197 | | |
| + NB-LR-charc | 0,8206 | | |
| + LM-KN | 0,8201 | | |
| + LM-KN+lex | 0,8221 (única aceptada, +0,0017) | | |

**Conclusión: meseta, no se envía.** Ningún promedio supera a su mejor componente, y la única base aceptada (+0,0017) está dentro del ruido.

---

### E13 · Nueva ronda de variables con protocolo anti-sesgo (en curso; `ext_variables2.py`)

**Motivo.** En E10b el sesgo de selección no se pudo medir directamente porque las variables se diseñaron mirando los errores de todo el train. E13 repite el ejercicio con una partición de control que no se mira.

**Protocolo.**
- Se reservó un **20 % del train como CONTROL**: `StratifiedKFold(5, shuffle=True, random_state=2026)` por combinación HS-TR-AG, partición 0. Son **347 filas**, con índices guardados en `recursos/control_E13.npy`.
- Las variables se diseñaron leyendo **solo los 292 errores** del stacking E11b (genérica + LGBM-PS) en el **80 % de desarrollo (1.384 filas)**. El test no se miró para diseñarlas.
- Cada hipótesis se verificó en desarrollo con P(etiqueta | patrón) frente a la prevalencia (HS 0,436).

| # | Hipótesis | Variable | n (desarrollo) | P(HS) | Decisión |
|---|---|---|---|---|---|
| H19 | *Perra* como mascota (contexto animal: *ladra, pasear, veterinario…*) → menos HS/TR | `perra_mascota` | 5 | 0,20 | Adoptada para la prueba |
| H20 | Estereotipo sexista sin insulto (*feminazi*, *a fregar*, *a la cocina*, *mujer al volante*) | `estereotipo_sexista` | 9 | 1,00 | Adoptada para la prueba |
| H22 | Fórmula de chiste racista *"racismo es que…"* | `racismo_es` | 4 | 0,75 | Adoptada para la prueba |
| H23 | *Puta* aplicada a algo no humano (*puta vida, ni puta, hostia puta…*): intensificador ampliado | `puta_no_humano` | 106 | 0,14 | Adoptada para la prueba |
| — | Sexual explícito: *polla* | — | 51 | 0,20 | Descartada |
| — | Sexual explícito dirigido a 2.ª persona | — | 27 | 0,41 | Descartada |
| — | *Güero* | — | 53 | 0,19 | Descartada |
| — | Insulto femenino + tono de broma/afecto | — | 79 | 0,72 | Descartada (más odio, no menos) |
| — | Insulto + *soy* | — | 14 | 0,57 | Descartada (igual al insulto solo) |

Uso: `d = tb.Datos(extra_lex=[ev.variables(generica=True), ev2.variables()])`. La caché va a `oof/base+h18/`.

#### Resultados E13

Stacking B7 (5 modelos originales + LGBM + LGBM-PS) con bagging de 5 semillas. F1 medio por semilla del metamodelo (42 / 43 / 44). **Control** = 347 filas que no se miraron al diseñar H19–H23 (sus predicciones son OOF, como en la CV).

| Configuración | CV completa | Desarrollo (80 %, 1384 filas) | **Control (20 %, 347 filas)** |
|---|---|---|---|
| base | 0,8204 (0,820 / 0,820 / 0,821) | 0,8213 | 0,8170 (0,820 / 0,819 / 0,812) |
| base + H19–H23 | 0,8225 (0,821 / 0,822 / 0,824) | 0,8239 | 0,8172 (0,815 / 0,817 / 0,819) |
| H12–H17 genérica (E11b) | 0,8244 (0,822 / 0,825 / 0,826) | 0,8264 | 0,8166 (0,818 / 0,818 / 0,813) |
| **H12–H17 genérica + H19–H23 (E13a)** | **0,8284** (0,827 / 0,827 / 0,832) | 0,8301 | **0,8217** (0,823 / 0,822 / 0,820) |

**Conclusión: se adopta E13a.**
- Sobre E11b, la CV sube +0,0040 y mejora en las 3 semillas, así que cumple el criterio de adopción.
- Lo importante: en el **control**, que nadie miró, la mejora es de **+0,0051** y también se da en las 3 semillas. La mejora en desarrollo (+0,0037) no es mayor que en el control, así que no hay señal de sesgo de selección en H19–H23.
- Sin H12–H17, H19–H23 suma poco: +0,0021 en CV y +0,0002 en control. Las variables nuevas se complementan con las anteriores.
- Advertencia: el control es pequeño (ruido de unos ±0,5 puntos), así que la estimación es indicativa. Aun así, es la primera mejora medida sobre datos que no influyeron en el diseño.
- Hallazgo lateral: sobre el control, H12–H17 genérica (0,8166) no supera a la base (0,8170). Esas variables se diseñaron mirando todo el train, control incluido, así que este número no es una medida limpia. De todos modos refuerza la cautela con la CV de E11a/E11b.

Scripts: `scripts/E12_*.py` y `scripts/E13_1..4_*.py`, que se ejecutan desde `experimentos/` con `../.venv/bin/python`.

Submission: `submissions/toxic_submission_E13a_generica_h19_23.csv`. Difiere en 26 filas de E11b y en 56 de E11c. Prevalencia predicha: HS 0,406, TR 0,302, AG 0,371.

---

## 5. Historial de envíos a Kaggle

| # | Archivo | Descripción | CV (F1 medio) | Público |
|---|---|---|---|---|
| 1 | `../toxic_submission_v1.csv` | Ensamble LR + Powerset (original) | 0,8065 | 0,78516 |
| 2 | `../toxic_submission.csv` | Stacking 5 modelos (original) | 0,8126 | 0,79160 |
| 3 | `submissions/toxic_submission_E6_bagging5.csv` | Stacking con *seed bagging* de 5 semillas | 0,8150 | 0,79100 |
| 4 | `submissions/toxic_submission_E8a_umbral045.csv` | E6 con umbral 0,45 | 0,8173 | 0,79637 |
| 5 | `submissions/toxic_submission_E8b_bagging_lgbm.csv` | *Bagging* 5 modelos + LightGBM | 0,8179 | 0,80168 |
| 6 | `submissions/toxic_submission_E9a_todos9.csv` | *Bagging*, los 9 modelos base | 0,8184 | 0,79940 |
| 7 | `submissions/toxic_submission_E9b_meta_c03.csv` | *Bagging* 5 + LGBM, meta C=0,3 | 0,8183 | 0,79734 |
| 8 | `submissions/toxic_submission_E9c_sin_cnb_umbral.csv` | *Bagging* sin CNB, umbrales 0,45 / 0,5 / 0,45 | 0,8183 | 0,79663 |
| 9 | `submissions/toxic_submission_E11a_variables_lgbmps.csv` | H12-H17 + *bagging* 5 + LGBM + LGBM-PS | 0,8300 | 0,79644 |
| 10 | `submissions/toxic_submission_E11b_generica_lgbmps.csv` | H12-H17 genérica + LGBM-PS | 0,8244 | 0,79895 |
| 11 | `submissions/toxic_submission_E11c_base_lgbmps.csv` | *Bagging* 5 + LGBM + LGBM-PS (sin variables nuevas) | 0,8204 | **0,80206** |

Notas:
- **Nombres cruzados en el notebook original.** Su tabla "Versiones enviadas" llama v1 a `toxic_submission.csv`. La prevalencia predicha (0,393 / 0,298 / 0,373) muestra que ese archivo es el **stacking** (0,79160) y que `toxic_submission_v1.csv` es el **ensamble** (0,78516).
- **No enviados:** `toxic_submission_E0.csv` (idéntico a la base) y los archivos `toxic_submission_E10b_variables*.csv` (sustituidos por las versiones E11).
- Los envíos de E11 se hicieron el **18-oct-2026 a las 02:48 UTC**.
- **Incidente con el límite de envíos.** Un envío programado de E9a, E9b y E9c que se creía cancelado se ejecutó y volvió a subir esos tres archivos como **duplicados el 18-oct a las 00:01 UTC** (con los mismos puntajes). Por eso, en esa ventana se **excedió el límite del curso de 3 envíos por día**. Los duplicados no aportan información nueva ni cambian la selección; se deja constancia para el informe.

---

## 6. Selección final recomendada

Kaggle permite marcar 2 submissions para el privado. Si no se marcan a mano, elige las 2 de mejor puntaje público. **Hay que marcarlas antes del cierre (19-oct-2026, 6:00 p. m.).**

| Elección | Archivo | CV | Público | Justificación |
|---|---|---|---|---|
| **A** | `toxic_submission_E11c_base_lgbmps.csv` | 0,8204 ± 0,0004 | 0,80206 | Mejor público. Su CV no depende de variables ajustadas a mano mirando errores, así que es la estimación menos sesgada. Es la de menor desviación entre semillas |
| **B** | `toxic_submission_E11b_generica_lgbmps.csv` | 0,8244 ± 0,0015 | 0,79895 | Aporta la mejora de las variables de contexto H12-H17 en su versión genérica, con menos sesgo de selección que E11a. Diversifica la apuesta frente a A (con y sin variables nuevas) |

**Por qué no E11a.** Su CV (0,8300) es la más alta, pero está inflada: las variables se escribieron mirando los errores del mismo train, la versión genérica conserva solo dos terceras partes de la mejora, varios de sus patrones aparecen la mitad de veces en el test y obtuvo el peor público de los tres E11 (0,79644). E11b captura la parte generalizable de esa mejora con menos riesgo.

Si E13 confirma una ganancia en el conjunto de control, se puede revisar la elección B.

---

## 7. Análisis de errores y lecciones

### 7.1 Patrones de error (del análisis OOF del original y de E10b)
- **Ruido de anotación.** El mismo *cállate perra* aparece como `000` y como `110`; *"Cllate todo te queda bien zorra te amo"* es `000`, pero *"Tú eres bien perra"* es `110`. Pone un techo a cualquier modelo de bolsa de palabras.
- **El blanco no es una mujer.** *"cllate zorra acá los leprosos no opinan"* (`000`) o *"cállate que asustas a la perra"* (el animal). El modelo da P ≈ 0,95 porque la fórmula *cállate* + insulto domina. H12 y H19 atacan este caso.
- **Frontera opinión/odio xenófobo.** Titulares como *"los asaltantes subsaharianos de la valla de Ceuta…"* están anotados `000` y comparten casi todo el vocabulario de `101`.
- **Estereotipos implícitos.** *"el árabe es un flojo"*, *"indios hijos de puta"* (donde *hijos de puta* empuja al no-odio por H3), estereotipos sin insultos. H14, H16 y H20 apuntan aquí.
- **TR es la etiqueta más fácil** (mención o insulto femenino explícitos) y **AG la más difícil** (frontera sutil entre opinión "moderada" y llamado a la expulsión).

### 7.2 Lo que funcionó
| Técnica | Efecto en CV | Prueba |
|---|---|---|
| Variables lingüísticas de contexto H1-H10 | +2,2 puntos sobre la LR | Original |
| Stacking de 5 modelos | +0,6 sobre el ensamble | Original, E0 |
| *Seed bagging* de 5 semillas | +0,0024 (3/3 semillas) | E6 |
| LightGBM como base no lineal (con *bagging*) | +0,0029 sobre E6 | E8b |
| LGBM-PS (formulación conjunta) | +0,0025 (3/3 semillas) | E10c, E11c |
| Variables H12-H17 a partir de errores | +0,012 (genérica: +0,0055 a +0,0065) | E10b, E11 |

### 7.3 Lo que no funcionó
| Técnica | Efecto | Por qué |
|---|---|---|
| Umbrales por etiqueta | −0,001 a −0,002 | Óptimos inestables entre semillas; `balanced` ya corrige |
| Reglas posteriores | 0 | El modelo ya aprendió el artefacto de comillas |
| Más bases lineales sobre los mismos n-gramas | ≤ +0,0004 | Correlación 0,96-1,00 con LR |
| Word2Vec sin corpus externo | −0,001 (solo: 0,763) | ~25 mil palabras por partición |
| HurtLex | −0,004 | El corpus se recolectó con esas palabras |
| Ajuste de `C` por etiqueta, `min_df=1` | ≤ +0,0015 | Zona de hiperparámetros plana |
| Variantes del metamodelo | ≤ +0,0009 | E0 ya está bien regularizado |
| Redes neuronales desde cero | −0,0004 | Pocos datos sin vectores preentrenados |
| LMs Kneser-Ney por clase | −0,0017 / +0,0010 | Vista distinta pero débil |
| Más familias (ExtraTrees, kNN, BNB, Jerarq-LR, LGBM-chi2) | −0,0027 a +0,0008 | Débiles o colineales |
| Promedios de stacks y selección hacia adelante | ≤ +0,0017 | Meseta |

### 7.4 Sesgo de selección y su control
- **Fuentes.** Escribir reglas mirando los errores del conjunto de evaluación; elegir el mejor de muchos conjuntos de bases; elegir umbrales o `C` sobre la misma CV.
- **Controles aplicados.** CV anidada para umbrales (E1); conjuntos definidos de antemano (E3, E9, E10c); criterio de adopción con 3 semillas; versión genérica de las variables (E10b); frecuencia de los patrones en el test, solo conteos (E10b, E13); **partición de control no mirada** (E13).
- **Lección.** La mejor CV no fue la mejor en el público. Una mejora de CV que depende de variables diseñadas sobre los mismos errores debe descontarse antes de elegir.

---

## 8. Reproducibilidad

| Componente | Versión |
|---|---|
| Python | 3.12.3 |
| numpy | 2.5.4 |
| pandas | 3.0.6 |
| scikit-learn | 1.9.1 |
| scipy | 1.18.1 |
| lightgbm | 4.7.0 |
| gensim | 4.4.0 |
| torch | 2.14.1+cpu |

- **Semillas.** CV repetida: 42, 43, 44. *Seed bagging*: 42-46. Metamodelo: semilla + 1. Word2Vec: semilla 0, un hilo. Partición de control de E13: `random_state=2026`, partición 0.
- **Caché.** `oof/` guarda las OOF y las predicciones de test por partición de cada base y semilla. **No está versionada** (`.gitignore`). Si se borra, todo se recalcula (15-20 min para E0-E7; E8-E11 y las redes tardan más; cada LM de E10d tarda ~2 min por semilla).
- **Código.** `toxic_base.py` (pipeline común), `ext_neuronal.py` (E10a), `ext_variables.py` (E10b, H12-H17), `ext_formulaciones.py` (E10c), `ext_lm.py` (E10d), `ext_variables2.py` (E13, H19-H23).
- **Datos.** `../tweet-toxic-2026-puj/` (`toxic_train.csv`, `toxic_test.csv`, `submission.csv`).

```bash
cd workshops/Kaggle-tweet-toxic
python3 -m venv .venv && .venv/bin/pip install pandas scikit-learn scipy nltk gensim lightgbm torch jupyter
cd experimentos
../.venv/bin/jupyter nbconvert --to notebook --execute --inplace E0_base_cv_repetida.ipynb
# y así con E1 ... E11 (E10a lee las redes de la caché; para recalcularlas, borrar oof/base/NN-*)
```

---

## 9. Referencias y licencias

- Basile, V., Bosco, C., Fersini, E., Nozza, D., Patti, V., Rangel, F., Rosso, P. y Sanguinetti, M. (2019). *SemEval-2019 Task 5: Multilingual Detection of Hate Speech Against Immigrants and Women in Twitter* (HatEval). Proceedings of SemEval-2019. Origen del corpus. Su corpus etiquetado **no se usó** para entrenar.
- Wang, S. y Manning, C. D. (2012). *Baselines and Bigrams: Simple, Good Sentiment and Topic Classification*. ACL 2012. Base de NB-LR (NB-SVM).
- Bassignana, E., Basile, V. y Patti, V. (2018). *Hurtlex: A Multilingual Lexicon of Words to Hurt*. CLiC-it 2018. **CC BY-NC-SA 4.0**. https://github.com/valeriobasile/hurtlex. Solo en E5; no adoptado.
- Chen, S. F. y Goodman, J. (1999). *An Empirical Study of Smoothing Techniques for Language Modeling*. Computer Speech & Language. Kneser-Ney modificado de E10d.
- Pedregosa, F. et al. (2011). *Scikit-learn: Machine Learning in Python*. JMLR. Licencia BSD-3.
- Ke, G. et al. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*. NeurIPS. Licencia MIT.
- Řehůřek, R. y Sojka, P. (2010). *Software Framework for Topic Modelling with Large Corpora* (gensim). Licencia LGPL-2.1.
- Paszke, A. et al. (2019). *PyTorch: An Imperative Style, High-Performance Deep Learning Library*. NeurIPS. Licencia BSD-3.
- pandas, numpy, scipy: licencia BSD. NLTK (solo para *stopwords* del análisis exploratorio del original): Apache 2.0.

No se usó ningún modelo, embedding, clasificador ni transformer preentrenado.

---

## 10. Glosario

| Término | Significado |
|---|---|
| **HS** (*Hate Speech*) | Etiqueta 1: el tweet contiene discurso de odio (contra mujeres o inmigrantes, según HatEval) |
| **TR** (*Targeted*) | Etiqueta 2: el odio va dirigido a una persona concreta y no a un grupo genérico. Solo puede ser 1 si HS=1 |
| **AG** (*Aggressiveness*) | Etiqueta 3: el tweet es agresivo o violento |
| **HatEval 2019** | Competencia académica (SemEval-2019, tarea 5) de la que salen estos tweets |
| **Multietiqueta** | Cada tweet tiene varias etiquetas 0/1 a la vez, no una sola clase |
| **F1-score** | Media armónica entre *precision* (de lo que predije como 1, cuánto acierto) y *recall* (de los 1 reales, cuántos encuentro). Va de 0 a 1 |
| **F1 medio** | F1 de la clase 1 de cada etiqueta, promediado sobre HS, TR y AG. Es la métrica de este trabajo |
| **F1-macro 2 clases** | Promedia el F1 de la clase 0 y el de la clase 1. Siempre da más alto que el F1 medio |
| **EMR** (*Exact Match Ratio*) | Porcentaje de tweets con las 3 etiquetas correctas a la vez |
| **Train / Test** | Datos con etiquetas (para aprender) / datos sin etiquetas (los que Kaggle califica) |
| **Leaderboard público / privado** | Kaggle califica ~50 % del test en el público (visible) y el otro ~50 % en el privado (se revela al cierre y **define el puesto**) |
| **CV** (*Cross-Validation*) | Se parte el train en 5 trozos (*folds*). Se entrena con 4 y se evalúa con el 5.º, rotando |
| **CV repetida** | La misma CV con varias semillas aleatorias. Promediar reduce la "suerte" de una sola partición |
| **CV anidada** | Una CV dentro de otra, para elegir algo (p. ej. umbrales) sin usar los datos con que se evalúa |
| **OOF** (*Out-Of-Fold*) | Predicción para cada fila del train hecha por un modelo que **no** la vio al entrenar |
| **Fuga de información** (*leakage*) | Que el modelo vea, directa o indirectamente, datos de evaluación al entrenar. Infla el puntaje de forma engañosa |
| **Sesgo de selección** | Si las reglas o configuraciones se eligen mirando un conjunto, medirlas en ese mismo conjunto exagera su mérito |
| **Conjunto de control** | Parte del train que se aparta antes de diseñar variables y no se mira, para medir la ganancia sin sesgo de selección (E13) |
| **Semilla** (*seed*) | Número que fija el azar para que los resultados se puedan reproducir |
| **Umbral** | Probabilidad a partir de la cual se predice 1 (por defecto 0,5) |
| **Prevalencia** | Proporción de 1s de una etiqueta (HS=0,44 significa que el 44 % de los tweets son odio) |
| **FP / FN** | Falso positivo (el modelo dice 1 y era 0) / falso negativo (dice 0 y era 1) |
| **Ablación** | Quitar una variable o un bloque a la vez para ver cuánto aporta |
| **Token / n-grama** | Unidad de texto (palabra) / secuencia de n unidades seguidas (*hija de* es un bigrama) |
| **BoW** (*Bag of Words*) | Representar el texto contando sus palabras, sin importar el orden |
| **TF-IDF** | BoW ponderado: sube el peso de lo frecuente en el tweet y baja el de lo común en todo el corpus |
| **`char_wb` / `char`** | n-gramas de caracteres dentro de cada palabra / que cruzan espacios entre palabras |
| **Stopwords / stemming** | Palabras funcionales (*la*, *de*, *tú*) / recortar a la raíz (*hija* → *hij*). No se usan, a propósito |
| **Léxico / variables de léxico** | Listas de palabras o patrones (regex) convertidas en columnas numéricas (p. ej. "tiene insulto femenino") |
| **Regex** | Expresión regular: un patrón para buscar texto |
| **Word2Vec** | Algoritmo que aprende un vector por palabra a partir de las palabras que la rodean |
| **Embedding** | Vector denso que representa una palabra o un texto |
| **SVD** (*TruncatedSVD*) | Reduce miles de columnas TF-IDF a unas cientas que resumen la información |
| **chi²** | Prueba estadística que mide cuánto se asocia cada n-grama con la etiqueta |
| **LR** (*Logistic Regression*) | Regresión logística: clasificador lineal que da probabilidades |
| **SVM** (*Support Vector Machine*) | Clasificador lineal que busca el margen máximo entre clases |
| **Calibrar (Platt / sigmoide)** | Convertir la salida de un SVM en probabilidades 0-1 |
| **NB / CNB / BNB** | Naive Bayes / Complement NB (para clases desbalanceadas) / Bernoulli NB (solo presencia o ausencia de palabras) |
| **NB-LR** | LR sobre palabras reponderadas por cuánto se asocian a cada clase según NB (Wang & Manning, 2012) |
| **Label Powerset** | Convierte las 3 etiquetas en una sola clase combinada (`000`, `111`, `101`...) |
| **LGBM-PS** | LightGBM multiclase sobre la combinación HS-TR-AG (Powerset) |
| **Cadena de clasificadores** | Predice HS primero y usa esa predicción como dato para AG y TR |
| **Jerarq-LR** | Formulación condicional: P(TR) = P(HS) · P(TR \| HS=1) |
| **LightGBM** | Modelo de árboles de decisión potenciados (*gradient boosting*), no lineal |
| **ExtraTrees / kNN** | Árboles aleatorizados promediados / predicción con los k tweets más parecidos |
| **Modelo de lenguaje (LM) / Kneser-Ney** | Modelo que da la probabilidad de un texto símbolo a símbolo / técnica de suavizado de n-gramas |
| **LLR** (*log-likelihood ratio*) | Log-verosimilitud bajo el LM de la clase 1 menos la de la clase 0 |
| **BiGRU / CNN de caracteres** | Red recurrente bidireccional / red convolucional sobre letras |
| **Ensamble** | Promediar las probabilidades de varios modelos |
| **Stacking / metamodelo** | Un segundo modelo aprende a combinar las predicciones OOF de los modelos base |
| **B6 / B7** | Bases de E8b (CNB, LR, SVM, NB-LR, Powerset, LGBM) / B6 + LGBM-PS |
| **Seed bagging** | Repetir el entrenamiento con varias semillas de partición y promediar. Reduce la varianza |
| **Varianza** | Cuánto cambian las predicciones si se entrena con otra muestra de los datos |
| **Hiperparámetro** (`C`, `min_df`...) | Ajuste que no se aprende de los datos. `C` alto = modelo más flexible; `min_df` = mínimo de tweets en que debe aparecer un término |
| **`class_weight='balanced'`** | Hace que el modelo dé más peso a la clase minoritaria |
| **HurtLex** | Léxico multilingüe de palabras ofensivas por categoría (CC BY-NC-SA 4.0) |
| **venv** | Entorno virtual de Python con las librerías del proyecto |
