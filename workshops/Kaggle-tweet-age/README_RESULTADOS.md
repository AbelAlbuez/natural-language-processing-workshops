# Resultados TweetAge: índice

**Estado de v10 (raíces con Kneser-Ney modificado): NO PASA.** La media de las diferencias F1(v10) − F1(v6) es +0,001095 y la desviación muestral (ddof=1) es 0,001713. La regla exige que la media sea positiva y mayor que la desviación, y no se cumple. No se evaluó el holdout ni se generó submission.

Las rutas son relativas a `workshops/Kaggle-tweet-age/`.

## Notebook

| Archivo | Ruta | Contenido |
|---|---|---|
| TweetAge_v10_raices_kn.ipynb | `TweetAge_v10_raices_kn.ipynb` | Experimento v10 para Colab, guardado sin salidas. Lee de `/content/drive/MyDrive/PLN/tweet-age-2026-puj/` y escribe en `/content/drive/MyDrive/PLN/RESULTS/tweetage_v10_raices/`. |

## Documentos (`docs/`)

| Archivo | Ruta | Contenido |
|---|---|---|
| RESULTADO_TWEETAGE_V10_RAICES.md | `docs/RESULTADO_TWEETAGE_V10_RAICES.md` | Resultado de v10: qué se probó, tabla por pliegue, decisión, gates, diagnósticos y notas. |
| HISTORIAL_SOLUCIONES_TWEETAGE.md | `docs/HISTORIAL_SOLUCIONES_TWEETAGE.md` | Todas las versiones (de la línea base a v10) con F1, holdout, score público, decisión, cumplimiento de reglas y conteo de hipótesis probadas. |
| ALTERNATIVAS_TWEETAGE.md | `docs/ALTERNATIVAS_TWEETAGE.md` | Seis alternativas ordenadas por ganancia esperada y riesgo, cada una con su criterio de decisión fijado antes de correr. |

Los tres documentos también están en `PLN/claude/`, fuera del repositorio, con el mismo contenido.

## Ejecución local de v10 (`resultados/tweetage_v10_raices/`)

Es la ejecución original del 2026-10-16, en CPU local, con los mismos datos y la misma partición que Colab.

| Archivo | Ruta | Contenido |
|---|---|---|
| tabla_cv.csv | `resultados/tweetage_v10_raices/tabla_cv.csv` | F1 de v6, F1 de v10, diferencia y combinación elegida en cada pliegue. |
| metricas_cv.json | `resultados/tweetage_v10_raices/metricas_cv.json` | La misma tabla, más la media, la desviación, la decisión y el F1 OOF de v6 y v10. |
| diagnostico_pliegues.csv | `resultados/tweetage_v10_raices/diagnostico_pliegues.csv` | F1 de cada modelo solo (caracteres, palabras, raíces), v6 y v10, con los pesos elegidos en cada pliegue. |
| diagnostico_raices.csv | `resultados/tweetage_v10_raices/diagnostico_raices.csv` | Porcentaje de tokens que cambia la raíz y tamaño del vocabulario de palabras y de raíces en cada pliegue. |
| distribucion_predicciones.csv | `resultados/tweetage_v10_raices/distribucion_predicciones.csv` | Cuántos casos hay de cada clase y cuántos predicen v6 y v10 (OOF). |
| ejecucion.log | `resultados/tweetage_v10_raices/ejecucion.log` | Log con hashes, gates, tiempos y memoria de la primera ejecución y de la reanudación desde caché. |
| fold_k/resultado.json | `resultados/tweetage_v10_raices/fold_{1..5}/resultado.json` | Resultado de cada pliegue con su huella: combinación, F1 interno, F1 de v6 y v10, y F1 de cada modelo solo. |
| fold_k/combinaciones_internas.csv | `resultados/tweetage_v10_raices/fold_{1..5}/combinaciones_internas.csv` | Las 15 combinaciones de pesos ordenadas por F1 en el 10 % interno. |
| fold_k/exterior_*.npz | `resultados/tweetage_v10_raices/fold_{1..5}/exterior_{caracteres,palabras,raices}.npz` | Scores (log-probabilidad por clase) de cada modelo sobre la validación exterior. Es la caché que reutiliza el notebook. |
| fold_k/interno_*.npz | `resultados/tweetage_v10_raices/fold_{1..5}/interno_{caracteres,palabras,raices}.npz` | Scores de los modelos entrenados con core sobre el 10 % interno. |
| fold_k/predicciones_exterior.npz | `resultados/tweetage_v10_raices/fold_{1..5}/predicciones_exterior.npz` | Predicciones de v6, de v10 y de cada modelo solo en la validación exterior. |

La carpeta ocupa unos 24 MB, casi todo en los `.npz`. Conviene decidir si los `.npz` se suben al repositorio o solo las tablas.
