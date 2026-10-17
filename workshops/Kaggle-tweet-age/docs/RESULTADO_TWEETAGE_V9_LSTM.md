# Resultado TweetAge v9: LSTM de caracteres por clase

**Estado: resultado negativo. NO PASA la regla de decisión. Zona gris respecto a las reglas del enunciado.**
Ejecutado en Google Colab con una GPU A100 el 2026-10-16. Las cifras de este documento salen de las salidas del notebook `TweetAge_v9_LSTM_LM.ipynb` ejecutado (celdas 24, 26, 28 y 34).

## 1. Qué se probó

Seis modelos generativos, uno por clase. Cada uno es una LSTM de caracteres que estima log P(tuit | edad). El tuit se asigna a la clase con mayor log-probabilidad (incluido EOS) más log prior, sin calibrar sesgos.

- **Arquitectura:** una capa LSTM con 256 unidades y dropout 0,2 en la salida.
- **Entrada:** one-hot mediante una matriz identidad congelada, que no se aprende.
- **Entrenamiento:** Adam con lr 0,001, batch 128, como máximo 30 épocas y paciencia 3. El early stopping usa el 10 % interno de grupos de cada pliegue.
- **Datos:** 140 caracteres de contenido por tuit, semilla 42.
- **Partición:** `split_idx_v6_seed42.npz`, con los mismos cinco pliegues de v6.
- **Referencia:** v6 recalculado en los mismos pliegues (caracteres 4, palabras 3, λ 0,75, sin calibración).

## 2. Resultados por pliegue (F1 macro en la validación exterior)

| Pliegue | F1 v6 | F1 v9 | Diferencia |
|---|---|---|---|
| 1 | 0,443844 | 0,371922 | −0,071922 |
| 2 | 0,444670 | 0,377804 | −0,066865 |
| 3 | 0,433306 | 0,376171 | −0,057134 |
| 4 | 0,442226 | 0,372701 | −0,069524 |
| 5 | 0,441174 | 0,374878 | −0,066296 |

- Media de las diferencias: **−0,066348**.
- Desviación muestral (ddof=1): **0,005620**.
- F1 OOF de todo el desarrollo: v6 0,441056 · v9 0,375158.

## 3. Observación sobre el entrenamiento

- En los 30 trabajos de la validación cruzada (5 pliegues × 6 clases), el número de épocas fue 30 y **la mejor época fue siempre la 30** (celda 34).
- El entrenamiento se detuvo porque se alcanzó el máximo de épocas, no por la paciencia.
- La pérdida de validación interna seguía bajando al cortar. Por ejemplo, en el log `fold_3_class_65-xx` la NLL interna pasa de 1,6579 en la época 29 a 1,6479 en la 30.
- El modelo **no había convergido**, así que el resultado mide una LSTM con entrenamiento incompleto.
- El pliegue 1 reutilizó los checkpoints de la prueba de rendimiento con N=6, también de 30 épocas. Los pliegues 2 a 5 se entrenaron desde cero.

## 4. Decisión

Regla: pasa solo si la media de las diferencias es positiva y mayor que su desviación. La media es negativa en los cinco pliegues.

**NO PASA.** No se evaluó el holdout, no se generó submission y no se envió nada a Kaggle (celdas 30, 32 y 34).

**Zona gris:** es una red neuronal recurrente sobre una entrada one-hot. LSTM y GRU no son candidatas a solución final, y el one-hot figura entre las vectorizaciones prohibidas, aunque aquí sea una identidad fija y no un embedding aprendido.

## 5. Dónde están los datos completos

- **Drive:** carpeta `PLN/RESULTS/tweetage_v9/v9_lstm_onehot_h256_c140_seed42_v1/`. Contiene checkpoints `.pt`, predicciones OOF, los logs por clase y pliegue, las carpetas `fold_k_orchestrator` y `execution_checks`.
- **Repositorio:**
  - Notebook con las salidas de Colab: `TweetAge_v9_LSTM_LM.ipynb`.
  - Informes de orquestación por pliegue: `resultados/tweetage_v9_lstm/fold_{1..5}/orchestrator_report.json`.

## 6. Qué no se verificó

- Ninguna de las cifras de F1 de este documento quedó sin verificar: las de los cinco pliegues están en las salidas del notebook.
- No se volvió a calcular nada: este documento solo transcribe las salidas de la ejecución.
- No se comprobó que los checkpoints `.pt` de Drive reproduzcan esas cifras.
