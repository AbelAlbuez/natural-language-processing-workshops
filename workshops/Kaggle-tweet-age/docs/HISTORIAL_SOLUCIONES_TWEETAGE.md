# Historial de soluciones TweetAge

Este documento recoge todas las versiones del reto TweetAge: seis rangos de edad y F1 macro como métrica. Cada cifra sale de leer el notebook correspondiente (celda indicada como "c.N"), de la ejecución de v9 guardada en Drive o de la ejecución local de v10. Lo que no aparece en ninguna fuente se marca como **no registrado**. Revisado el 2026-10-16.

## Antes de leer la tabla

- **Las cifras no siempre se pueden comparar entre sí.**
  - v1 a v5 usan un holdout 80/20 que no agrupa textos repetidos, así que tiene fuga.
  - v6 y v7 (descuento, ordinal) usan la partición agrupada de v6 (`split_idx_v6_seed42.npz`).
  - v7 (hiperparámetros, normalización, neuronal) y todos los v8 usan `split_idx_v7_lower_seed42.npz`, con grupos en minúsculas. Allí la referencia v6 recalculada da OOF 0,440081.
  - v9 y v10 vuelven a la partición de v6.
- **v2, v3, v4, v7 descuento, v7 ordinal y la copia de v9 en el repositorio no tienen salidas guardadas.** Sus cifras vienen de tablas en markdown del propio notebook, del docstring de `tweetage_v3_selector.py`, de valores escritos a mano en notebooks posteriores o, en el caso de v9, del notebook ejecutado en Colab que está en Drive.
- **Kaggle:** solo v3 anota su score público en su propio notebook. Los de v1, v5 y v6 aparecen citados en notebooks posteriores (v7_lm_neuronal c.0, v8_lm_jerarquico c.9). El de v4 (0,62832) fue un dato que comunicó el usuario y v6 lo marca como no verificado.
- **Cumplimiento** se mide contra las reglas del enunciado: solo modelos probabilísticos de lenguaje entrenados por el equipo. Quedan prohibidos los embeddings, Word2Vec, GloVe, TF-IDF, cualquier vectorización (bolsas, n-gramas como features, one-hot, NB-SVM), los modelos preentrenados y los transformers. LSTM y GRU se consideran zona gris.

## Tabla

| Versión | Enfoque | Modelo | Normalización | F1 OOF | Holdout | Score público | Decisión | Cumple reglas | Dónde están los resultados | Lección principal |
|---|---|---|---|---|---|---|---|---|---|---|
| **TweetAge_modelo** (v1, línea base de clase) | Clasificador sobre vectorización | TF-IDF de palabras 1-2 + `char_wb` 2-5 → LinearSVC C=0,3; ensamble con SGD-log | `strip` + `html.unescape`; excluye vacíos y `#¿NOMBRE?` (155); conserva @usuarios, mayúsculas y alargamientos | no registrado (`RUN_CV=False`) | 80/20: LinearSVC 0,5549; ensamble 0,5557; rango de las celdas de evaluación 0,5276 a 0,5576 (c.27, c.30, c.32) | 0,56175 (citado en v3 c.0) | Solo TF-IDF, el modelo más simple dentro de una tolerancia de 0,003 | **No** (TfidfVectorizer) | Repo, c.27/30/32/37 | Las variables de estilo explican pero suman poco F1; pesa más el preprocesamiento |
| **TweetAge_descriptivo** | Análisis exploratorio | Ninguno predictivo | `strip`, sin unescape | no aplica | no aplica | no aplica | Conservar el ruido y las @usuarios. 1.238 tuits del test son idénticos a tuits del train (c.5) | **Zona gris / no aplica** (no clasifica, pero usa CountVectorizer para log-odds) | Repo, c.5/9/12/14 | La edad se nota en la longitud, las menciones y la red (homofilia) |
| **v2** | NB-SVM | NB-SVM (Wang y Manning) sobre TF-IDF de palabras 1-3 + `char_wb` 2-5 + `char` 1-5 | igual que v1 | no registrado | 0,5810 (tabla en markdown c.0) | no registrado | +0,026 por la representación (+0,0137 ponderación NB, +0,0065 vocabulario completo, +0,0056 bloque `char`) | **No** | Repo, c.0 y c.18 (markdown, sin salidas) | La representación pesa más que el clasificador; el techo lineal ronda 0,58 |
| **v3_selector** | NB-SVM + variables de red + stacking | NB-SVM fuera de muestra + 10 familias G0-G9 + selector en 3 niveles + gradient boosting | igual que v1 | no registrado | 0,6075 (docstring del `.py`, líneas 24-27) | **0,61765** (c.0, c.38) | Solo se añade G6 (homofilia de @cuentas y #hashtags), +0,015 | **No** (TF-IDF, CountVectorizer, NMF, LSA, NB-SVM) | Repo, c.34 (markdown) y `tweetage_v3_selector.py` | La homofilia de red es la mejor señal *nueva*, pero la base sigue siendo NB-SVM (al permutarla el F1 cae 0,301) |
| **v4** | Stacking ampliado | NB-SVM + NB-SVM de palabras + ComplementNB + G6 + H5 + G0 → gradient boosting con pesos por clase | igual que v1 | no registrado (se calcula, pero no hay salida) | 0,6193 (c.0, markdown) | "por medir" en v4; 0,62832 lo comunicó el usuario y no está verificado (v6 c.0) | +0,012 sobre v3 (0,6074 → 0,6193); H5 aporta +0,004 | **No** (TF-IDF, CountVectorizer, NB-SVM, ComplementNB) | Repo, c.0 (markdown) | Las relaciones de red son la señal más rentable |
| **v5_charLM_kn** | Primer modelo de lenguaje por clase | KN interpolado de caracteres y palabras, D=0,75 fijo; 60 combinaciones | URL→`<url>`, @→`<user>`, repeticiones a 3, mayúsculas conservadas | 0,43539 → 0,43847 con sesgo por clase (optimista, c.10/c.15) | 0,44945 (c.12), inflado por fuga: 2.561 filas del holdout tienen su texto en el desarrollo (c.4) | 0,45643 (citado en v7_lm_neuronal c.0) | Mejor: caracteres 4 + palabras 3, λ 0,75 | **Sí** | Repo, c.10/12/15 | Cumple las reglas pero pierde unos 16 puntos frente a v3; 25-34 es la clase más difícil |
| **v6_charLM_kn** | KN modificado + partición agrupada | KN modificado por clase (D1/D2/D3+); 120 configuraciones | Normalización "A" (la de v5); grupos por texto normalizado | 0,44106 bruto / 0,44353 calibrado (optimista) (c.14) | **0,418466** (c.11) | 0,45737 (citado en v7_lm_neuronal c.0 y v8 c.9; v6 no envió nada) | **Referencia válida**: caracteres 4, palabras 3, λ 0,75, bruto | **Sí** | Repo, c.9/11/14; `split_idx_v6_seed42.npz` | Agrupar por texto elimina la fuga; el holdout baja frente a v5 |
| **v7_descuento_concentracion** | Otro suavizado | Interpolación descontada con concentración θ sobre el KN de v6 | A; partición v6 | 0,440875 (θ=0,5) / 0,440788 (θ=1,0); −0,00018 frente a v6. Sin salidas: cifras escritas a mano en v7_lm_neuronal c.0 | no evaluado | no aplica | NO PASA | **Sí** | Sin salidas en el repo; cifras en v7_lm_neuronal c.0 | Cambiar el suavizado solo mueve milésimas |
| **v7_hiperparametros** | Última ronda de n-gramas | KN modificado, 8 combinaciones (car, pal, λ) contra la referencia | A; partición v7_lower | Referencia 0,440081; la mejor, C7 (5, 4, 0,6), da 0,437677 (diferencia media −0,002367 ± 0,001548). Ninguna tiene media > 0 (c.4, c.8) | omitido | no aplica | NO PASA; familia de n-gramas cerrada | **Sí** | Repo, c.4/5/8 | Los órdenes y el λ de v6 ya estaban en el óptimo local |
| **v7_lm_neuronal** | Red recurrente | GRU de caracteres por clase (128 unidades, one-hot) + 0,25·KN de palabras | A; partición v7_lower | Solo pliegue 1: GRU 0,360561; GRU+KN 0,411131; referencia 0,440843 (c.11) | omitido | no aplica | NO PASA en la etapa 1 | **Zona gris** (GRU sobre one-hot) | Repo, c.11/13 | La red recurrente queda unos 3 puntos por debajo de KN |
| **v7_normalizacion_ablacion** | Ablación de la normalización | Modelo de v6 fijo; brazos A (referencia), B (sin límite de repeticiones), C (más minúsculas) | Crea la partición v7_lower. En la partición v6 había 61 textos compartidos en minúsculas en el pliegue 1 (162 filas) | A 0,440081; B 0,439709 (−0,000375); C 0,436893 (−0,003184) (c.5) | omitido | no aplica | NO PASA; A sigue siendo la mejor; v7_lower queda como partición de control | **Sí** | Repo, c.3/5/6 | La normalización A de v6 no se mejora con estas variantes |
| **v7_ordinal_kn** | Decodificación ordinal | 5 cortes binarios bajo/alto, cada uno con KN de caracteres y palabras | A; partición v6 | 0,42321 sin calibrar / 0,42468 calibrado. Sin salidas: cifras escritas a mano en v7_descuento c.10 y v7_lm_neuronal c.0 | no evaluado | no aplica | NO PASA | **Sí** | Sin salidas en el repo | Descomponer por cortes empeora unos 2 puntos |
| **v8_lm_jerarquico** | Respaldo jerárquico | Cada clase se respalda en un KN global (Dirichlet, β ∈ {10, 50}) | A; partición v7_lower | β=10 0,414583; β=50 0,410969 (c.11). Diferencia frente a A por clase: −0,027 (13-17) y −0,032 (65-xx) (c.19) | omitido | no aplica | NO PASA; no se elige ningún β | **Sí** | Repo, c.11/13/19 | Respaldarse en el modelo global empeora las 6 clases |
| **v8_naive_bayes** | Modelo de lenguaje de orden 0 | NB multinomial por clase (unigramas de caracteres + palabras, Laplace) hecho a mano | A; partición v7_lower | 0,376727 (c.9) | omitido | no aplica | NO PASA (−0,063) | **Sí** (es un LM de unigramas por clase, sin matriz de conteos) | Repo, c.9/11 | Sin contexto se pierden unos 6 puntos: el orden de los n-gramas importa |
| **v8_ordenes_y_ensamble** | Órdenes altos y mezcla EM | Caracteres de orden 6 y 7; mezcla lineal EM de KN (car 3-6, pal 2-4) | A; partición v7_lower | O6 0,434686; O7 0,434295; E 0,437352 (c.11) | omitido | no aplica | NO PASA (E −0,002693 ± 0,003285) | **Sí** | Repo, c.11/13 | Subir el orden por encima de 4 no ayuda. EM no convergió (llegó al tope de 50 iteraciones) |
| **v8_ppm** | Otro suavizado | PPM-C de caracteres por clase, orden 4 | A; partición v7_lower | 0,421730 (c.9) | omitido | no aplica | NO PASA (−0,018) | **Sí** | Repo, c.9/11 | PPM-C solo de caracteres queda 1,8 puntos por debajo de KN de caracteres + palabras |
| **v9_LSTM_LM** | Red recurrente | 6 LSTM de caracteres (h=256, one-hot fijo, máximo 30 épocas, paciencia 3) | A; partición v6 | v9 0,375158 frente a v6 0,441056. Diferencias por pliegue: −0,071922; −0,066865; −0,057134; −0,069524; −0,066296. Media −0,066348; desviación 0,005620 | omitido | no aplica | **NO PASA**. Los 30 trabajos llegaron a 30 épocas con mejor época 30: el tope de épocas cortó el entrenamiento en todos | **Zona gris** (LSTM sobre one-hot) | Drive: notebook ejecutado `TweetAge_v9_LSTM_LM.ipynb` (c.24/26/28/34) y `RESULTS/tweetage_v9/v9_lstm_onehot_h256_c140_seed42_v1/`. El .ipynb del repo no tiene salidas | Queda unos 6,6 puntos por debajo de KN; aún no había convergido |
| **v10_raices_kn** | Tercer modelo sobre raíces | KN modificado de caracteres 4 + palabras 3 + raíces Snowball 3; pesos en un simplex de 15, elegidos en un 10 % interno | A + raíces (minúsculas, sin tildes, Snowball); partición v6 | v6 0,441056 / v10 0,442193. Diferencias por pliegue +0,001160; +0,000040; +0,003335; −0,001083; +0,002025. Media +0,001095; desviación 0,001713 | omitido | no aplica | **NO PASA** | **Sí** | Local: `claude/v10_resultados_locales/`; ver `RESULTADO_TWEETAGE_V10_RAICES.md` | La raíz aporta poco y de forma inestable: casi siempre reemplaza a las palabras en lugar de sumarse |

## Conteo

- **Conformes con las reglas: 11** (v5, v6, los cuatro v7 de KN, los cuatro v8 y v10).
- **No conformes: 4** (modelo base, v2, v3 y v4).
- **Zona gris: 3.** Dos son redes: v7_lm_neuronal y v9. La otra es el descriptivo, que no es un modelo.
- **La única versión conforme con holdout y score público es v6** (holdout 0,418466; público 0,45737 citado). Ninguna versión conforme posterior superó la regla frente a v6.

## Hipótesis probadas

Se cuentan dos cosas distintas:

**A. Configuraciones comparadas para seleccionar** (cada una es una comparación con datos de evaluación):

| Versión | Configuraciones | Cómo se contó |
|---|---|---|
| modelo | 16 | 4 ablaciones + 7 clasificadores + 5 pesos del ensamble |
| v2 | 15 | 4 pasos + 11 variantes descartadas |
| v3 | 24 | 10 familias + 10 pasos adicionales del wrapper + 4 modelos del nivel 3 |
| v4 | 12 | 5 de ablación + 7 descartados (sin contar 378 evaluaciones de pesos) |
| v5 | 60 | 4 órdenes de caracteres × 3 de palabras × 5 λ |
| v6 | 120 | 4 × 3 × 5 λ × 2 tipos de score |
| v7 descuento | 2 | θ ∈ {0,5; 1,0} |
| v7 hiperparámetros | 8 | lista de combinaciones |
| v7 neuronal | 1 | |
| v7 normalización | 2 | brazos B y C frente a A |
| v7 ordinal | 1 | |
| v8 jerárquico | 2 | β ∈ {10, 50} |
| v8 Naive Bayes | 1 | |
| v8 órdenes y ensamble | 3 | O6, O7, E |
| v8 PPM | 1 | |
| v9 | 1 | |
| v10 | 15 | combinaciones del simplex (elegidas en el 10 % interno) |
| **Total** | **284** | 67 en líneas no conformes (v1-v4) y **217** en las versiones conformes o en zona gris (v5-v10) |

**B. Pruebas pareadas contra v6 con la regla "media > 0 y media > desviación"** (de v7 en adelante): 2 + 8 + 1 + 2 + 1 + 2 + 1 + 3 + 1 + 1 + 1 = **23 pruebas. Ninguna pasó.**

**Lectura.** Con 5 pliegues, la regla equivale a exigir t > √5 ≈ 2,24 con 4 grados de libertad. Si no hubiera ninguna mejora real y las diferencias fueran normales, cada prueba pasaría por azar con probabilidad de alrededor del **4,5 %**. En 23 pruebas cabe esperar **cerca de 1 falso positivo**, y la probabilidad de que al menos una pase por azar es de alrededor del **65 %**. Que ninguna haya pasado refuerza que v6 está cerca del techo de esta familia de modelos. También significa que, si la próxima prueba pasara por poco, habría que desconfiar. Con una exigencia de media > 2 × desviación, el riesgo por prueba baja a un 0,55 %. Todas estas probabilidades son aproximadas: suponen diferencias normales e independientes, y los pliegues no lo son del todo.
