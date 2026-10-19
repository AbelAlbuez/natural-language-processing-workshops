# TweetToxic: resumen de experimentos (17-oct-2026)

Punto de partida: `TweetToxic_modelo.ipynb`, un stacking de 5 modelos que obtuvo **0,79160** en el leaderboard público (4.º puesto).
Cada prueba está en su propio notebook, ejecutable de principio a fin y guardado con sus salidas. El código común está en `toxic_base.py`.

## Cómo reproducir
```bash
cd workshops/Kaggle-tweet-toxic
python3 -m venv .venv && .venv/bin/pip install pandas scikit-learn scipy nltk gensim lightgbm jupyter
cd experimentos
../.venv/bin/jupyter nbconvert --to notebook --execute --inplace E0_base_cv_repetida.ipynb   # y así con E1...E7
```
Versiones usadas: Python 3.12.3, numpy 2.5.4, pandas 3.0.6, scikit-learn 1.9.1, scipy 1.18.1, gensim 4.4.0, lightgbm 4.7.0.
Las probabilidades OOF se guardan en caché en `oof/`. Si se borra esa carpeta, todo se recalcula (unos 15-20 min).

## Protocolo
- **CV repetida:** 5 particiones estratificadas por la combinación HS-TR-AG × 3 semillas (42, 43, 44). Se reporta la media ± la desviación.
- **Métrica:** F1 medio, es decir, el F1 de la clase 1 de cada etiqueta promediado entre HS, TR y AG.
- **Criterio de adopción:** mejora ≥ 0,003 en el F1 medio y mejora en al menos 2 de las 3 semillas. Con ~577 filas, el leaderboard público tiene un ruido de ±2,5 puntos, así que no sirve para decidir.

## Resultados

| Prueba | Notebook | Qué se probó | F1 medio (CV repetida) | Δ vs E0 | Decisión |
|---|---|---|---|---|---|
| **E0** | `E0_base_cv_repetida` | Reproducción exacta del stacking enviado (0 filas distintas) | **0,8126 ± 0,0021** | — | Referencia |
| E1 | `E1_umbrales_stacking` | Umbrales por etiqueta con CV anidada; umbrales fijos 0,40-0,55 | 0,8106 – 0,8120 | −0,001 a −0,002 | ✗ Los umbrales óptimos son inestables entre semillas |
| E2 | `E2_reglas_post` | Comillas → AG=1; duplicados; filas `#¿NOMBRE?` | 0,8126 | 0 | ✗ El modelo ya lo hace solo; no cambia nada |
| E3 | `E3_bases_nuevas` | LR/NB-LR con `char` 2-6, LightGBM sobre SVD + léxico, cadena de clasificadores | 0,8110 – 0,8130 | ≤ +0,0004 | ✗ El stacking está saturado |
| E4 | `E4_word2vec` | Word2Vec propio (gensim) como modelo base | 0,8114 (solo: 0,763) | −0,001 | ✗ Muy pocos datos para aprender vectores útiles |
| E5 | `E5_hurtlex` | Léxico HurtLex (17 categorías) en el bloque de léxico | 0,8088 | **−0,004** | ✗ Empeora: el corpus se muestreó con esas mismas palabras |
| **E6** | `E6_stacking_mejorado` | Variantes del metamodelo; ***seed bagging*** de los modelos base (5 semillas) | **0,8150 ± 0,0007** | **+0,0024** (3/3 semillas) | ✓ Candidato: más estable, cambia 19 filas del test |
| E8a | `E8_candidatos_envio` | E6 con umbral 0,45 en las 3 etiquetas | 0,8173 ± 0,0001 | +0,0047 | Candidato (31 filas distintas de E6) |
| E8b | `E8_candidatos_envio` | Bagging de 5 semillas con los 5 modelos + LightGBM | 0,8179 ± 0,0012 | +0,0053 | Candidato (44 filas distintas de E6) |
| E9 | `E9_variantes_bagging` | 16 variantes de bagging + LightGBM (más bases, sin CNB, meta C=0,3, umbrales 0,45) | 0,8164 – 0,8184 | +0,004 a +0,006 | Meseta; 3 candidatos (E9a/b/c) |
| E10a | `E10a_neuronal` | Redes neuronales desde cero (BiGRU, CNN de caracteres, bolsa de embeddings) | 0,8175 (sola: ≤ 0,786) | −0,0004 vs E8b | ✗ |
| **E10b** | `E10b_variables_errores` | Variables H12-H17 a partir del análisis de errores (posesivo + insulto, demostrativo femenino, grupo migrante + deshumanización...) | **0,8299** (genérica: 0,8234) | **+0,012 vs E8b** | ✓ Con sesgo de selección parcial |
| E10c | `E10c_formulaciones` | TR/AG condicionados a HS, ExtraTrees, kNN, Bernoulli NB, LightGBM Powerset | 0,8204 (con LGBM-PS) | +0,0025 vs E8b | Pequeño aporte |
| E10d | `E10d_lm_por_clase` | Modelos de lenguaje Kneser-Ney por clase (caracteres y palabras) | 0,8162 – 0,8189 | ≈ 0 | ✗ |
| **E11** | `E11_combinacion_final` | H12-H17 + LGBM-PS | **0,8300** | +0,012 vs E8b | ✓ Candidatos E11a/b/c |
| E12 | (script, sin notebook) | Promediar los stacks base/genérica/completa; selección hacia adelante de bases extra (Jerarq-LR, ExtraTrees, BNB, LGBM-chi2, Cadena, charc, LM-KN) | 0,8242 – 0,8266 (promedios); ≤ +0,0017 (bases extra) | ≤ 0 vs su referencia | ✗ Meseta, no se envía |
| **E13** | (script; ver `INFORME_EXPERIMENTOS.md`) | H19-H23 diseñadas solo con el 80 % de desarrollo, medidas en un 20 % de control no visto | **0,8284** (control 0,8217) | +0,0040 CV y +0,0051 control vs E11b | ✓ Candidato E13a |
| E7 | `E7_ajuste_por_etiqueta` | `C` por etiqueta, `min_df=1` | LR: 0,8006 – 0,8038 | ≤ +0,0015 en LR | ✗ La zona de hiperparámetros es plana |

### Lectura general (para el informe)
1. **El modelo de partida está cerca del techo de los métodos de bolsa de palabras en este corpus.** Ningún clasificador ni representación nueva mueve el F1 medio más allá de la variación entre semillas.
2. **La información útil está en el contexto y no en el vocabulario.** Las variables hechas a mano (H1-H10) suman +2,2 puntos porque distinguen, por ejemplo, *hija de puta* de *hijo de puta* o *puta* como insulto de *puta* como intensificador. Un léxico genérico (HurtLex) o vectores Word2Vec no capturan eso y en este corpus agregan ruido.
3. **El ruido de anotación limita el resultado:** el mismo *cállate perra* aparece como `000` y como `110`.
4. **Con este tamaño de datos, lo que funciona es reducir la varianza** (*seed bagging*), no agregar complejidad.

## Envíos

| Archivo | Modelo | CV | Kaggle público | Estado |
|---|---|---|---|---|
| `../toxic_submission_v1.csv` | Ensamble LR + Powerset (original) | 0,8065 | 0,78516 | Enviado |
| `../toxic_submission.csv` | Stacking 5 modelos (original) | 0,8126 | **0,79160** | Enviado (mejor actual) |
| `submissions/toxic_submission_E0.csv` | Idéntico al anterior (verificación de reproducción) | 0,8126 | — | **No enviar** |
| `submissions/toxic_submission_E6_bagging5.csv` | Stacking con *seed bagging* de 5 semillas | 0,8150 | 0,79100 | Enviado (empate con la base: solo cambia 19 filas) |
| `submissions/toxic_submission_E8a_umbral045.csv` | E6 con umbral 0,45 | 0,8173 | 0,79637 | Enviado |
| `submissions/toxic_submission_E8b_bagging_lgbm.csv` | Bagging con 5 modelos + LightGBM | 0,8179 | **0,80168** | Enviado (mejor público) |
| `submissions/toxic_submission_E9a_todos9.csv` | Bagging, los 9 modelos base | 0,8184 | 0,79940 | Enviado |
| `submissions/toxic_submission_E9b_meta_c03.csv` | Bagging 5 + LGBM, meta C=0,3 | 0,8183 | 0,79734 | Enviado |
| `submissions/toxic_submission_E9c_sin_cnb_umbral.csv` | Bagging sin CNB, umbrales 0,45/0,5/0,45 | 0,8183 | 0,79663 | Enviado |
| `submissions/toxic_submission_E11a_variables_lgbmps.csv` | H12-H17 + bagging 5 + LGBM + LGBM-PS | 0,8300 | 0,79644 | Enviado |
| `submissions/toxic_submission_E11b_generica_lgbmps.csv` | H12-H17 genérica + LGBM-PS | 0,8244 | 0,79895 | Enviado |
| `submissions/toxic_submission_E11c_base_lgbmps.csv` | Bagging 5 + LGBM + LGBM-PS (sin variables nuevas) | 0,8204 | 0,80206 | Enviado |
| `submissions/toxic_submission_E13a_generica_h19_23.csv` | H12-H17 genérica + H19-H23 + bagging 5 + LGBM + LGBM-PS | 0,8284 | _pendiente_ | Candidato |

> Ojo con los nombres: en la tabla "Versiones enviadas" del notebook original, la v1 aparece como `toxic_submission.csv`. Pero la prevalencia predicha (0,393/0,298/0,373) muestra que ese archivo es el **stacking** (0,79160), y que `toxic_submission_v1.csv` es el ensamble (0,78516).

### Recomendación para la selección final en Kaggle (2 submissions)
- **A: `toxic_submission_E11c_base_lgbmps.csv`** (CV 0,8204, público 0,80206): el mejor público, y su CV no depende de variables ajustadas a mano.
- **B: `toxic_submission_E11b_generica_lgbmps.csv`** (CV 0,8244, público 0,79895): la versión genérica de H12-H17, con menos sesgo de selección que E11a.

E11a (CV 0,8300) no se elige porque esa CV está inflada por el sesgo de selección y obtuvo el peor público de los tres. Si no se marcan manualmente, Kaggle elige las 2 de mejor puntaje público. El detalle completo está en `INFORME_EXPERIMENTOS.md`.

## Recursos externos y licencias
- **HurtLex** v1.2 (español): Bassignana, E., Basile, V. y Patti, V. (2018). *Hurtlex: A Multilingual Lexicon of Words to Hurt*. CLiC-it 2018. Licencia CC BY-NC-SA 4.0. https://github.com/valeriobasile/hurtlex. Se usó solo en E5 y no se adoptó.
- Librerías: scikit-learn (BSD-3), gensim (LGPL-2.1), LightGBM (MIT), pandas/numpy/scipy (BSD).
- No se usó ningún modelo, embedding ni transformer preentrenado. Word2Vec (E4) se entrenó desde cero, solo con la partición de entrenamiento de cada fold.
- **Descartado a propósito:** el corpus etiquetado de HatEval 2019. El test de esta competencia sale de ahí, así que entrenar con él sería fuga de las etiquetas del test.

## Glosario
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
| **Leaderboard público / privado** | Kaggle califica ~50 % del test en el público (visible ahora) y el otro ~50 % en el privado (se revela al cierre y **define el puesto**) |
| **CV** (*Cross-Validation*, validación cruzada) | Se parte el train en 5 trozos (*folds*). Se entrena con 4 y se evalúa con el 5.º, rotando |
| **CV repetida** | La misma CV con varias semillas aleatorias. Promediar reduce la "suerte" de una sola partición |
| **CV anidada** | Una CV dentro de otra, para elegir algo (p. ej. umbrales) sin usar los datos con que se evalúa |
| **OOF** (*Out-Of-Fold*) | Predicción para cada fila del train hecha por un modelo que **no** la vio al entrenar |
| **Fuga de información** (*leakage*) | Que el modelo vea, directa o indirectamente, datos de evaluación al entrenar. Infla el puntaje de forma engañosa |
| **Semilla** (*seed*) | Número que fija el azar para que los resultados se puedan reproducir |
| **Umbral** | Probabilidad a partir de la cual se predice 1 (por defecto 0,5) |
| **Prevalencia** | Proporción de 1s de una etiqueta (HS=0,44 significa que el 44 % de los tweets son odio) |
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
| **LR** (*Logistic Regression*) | Regresión logística: clasificador lineal que da probabilidades |
| **SVM** (*Support Vector Machine*) | Clasificador lineal que busca el margen máximo entre clases |
| **Calibrar (Platt / sigmoide)** | Convertir la salida de un SVM en probabilidades 0-1 |
| **NB / CNB** (*Naive Bayes / Complement NB*) | Clasificador probabilístico simple basado en conteo de palabras. CNB es una variante para clases desbalanceadas |
| **NB-LR** | LR sobre palabras reponderadas por cuánto se asocian a cada clase según NB (Wang & Manning, 2012) |
| **Label Powerset** | Convierte las 3 etiquetas en una sola clase combinada (`000`, `111`, `101`...) |
| **Cadena de clasificadores** | Predice HS primero y usa esa predicción como dato para AG y TR |
| **LightGBM** | Modelo de árboles de decisión potenciados (*gradient boosting*), no lineal |
| **Ensamble** | Promediar las probabilidades de varios modelos |
| **Stacking / metamodelo** | Un segundo modelo aprende a combinar las predicciones OOF de los modelos base |
| **Seed bagging** | Repetir el entrenamiento con varias semillas de partición y promediar. Reduce la varianza |
| **Varianza** | Cuánto cambian las predicciones si se entrena con otra muestra de los datos |
| **Hiperparámetro** (`C`, `min_df`...) | Ajuste que no se aprende de los datos. `C` alto = modelo más flexible; `min_df` = mínimo de tweets en que debe aparecer un término |
| **`class_weight='balanced'`** | Hace que el modelo dé más peso a la clase minoritaria |
| **HurtLex** | Léxico multilingüe de palabras ofensivas por categoría (CC BY-NC-SA 4.0) |
| **venv** | Entorno virtual de Python con las librerías del proyecto |
