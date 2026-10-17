# Resultado TweetAge v10: raíces con Kneser-Ney modificado

**Estado: resultado negativo. NO PASA la regla de decisión.**
Fecha de ejecución: 2026-10-16. Se ejecutó en la máquina local (CPU), con los mismos datos y el mismo `split_idx_v6_seed42.npz` que usa Colab.

## 1. Qué se probó

Un ensamble de tres modelos de lenguaje por clase, todos con Kneser-Ney modificado (el código es el de v6, copiado sin cambios):

- Caracteres, orden 4.
- Palabras, orden 3.
- Raíces, orden 3. Se aplica Snowball en español (`nltk.stem.snowball.SnowballStemmer('spanish')`) a los tokens alfabéticos de v6, después de pasarlos a minúsculas y quitarles las tildes. `<url>`, `<user>`, los números y la puntuación se dejan igual.

Pesos: un simplex con paso 0,25, que da 15 combinaciones (w_car; w_pal; w_raiz) que suman 1. En cada pliegue exterior se separa un 10 % interno del entrenamiento (agrupado por texto normalizado y estratificado por clase, con `inner_split` de v9). Los modelos se entrenan con el 90 % restante, la combinación se elige en ese 10 % y luego se reentrena con el 100 % del pliegue. La validación exterior nunca se usó para elegir.

Referencia: v6, con pesos (0,75; 0,25; 0) más log prior y sin calibrar sesgos.

## 2. Resultados por pliegue (F1 macro en la validación exterior)

| Pliegue | F1 v6 | F1 v10 | Diferencia | Pesos (car; pal; raíz) |
|---|---|---|---|---|
| 1 | 0,443844 | 0,445004 | +0,001160 | (0,75; 0; 0,25) |
| 2 | 0,444670 | 0,444710 | +0,000040 | (0,50; 0; 0,50) |
| 3 | 0,433306 | 0,436640 | +0,003335 | (0,50; 0,25; 0,25) |
| 4 | 0,442226 | 0,441142 | −0,001083 | (0,75; 0; 0,25) |
| 5 | 0,441174 | 0,443199 | +0,002025 | (0,75; 0; 0,25) |

F1 OOF de todo el desarrollo: v6 0,441056 · v10 0,442193.

## 3. Decisión

Ambas cifras se recalcularon a partir de la tabla:

- Media de las diferencias: **+0,001095**.
- Desviación muestral (ddof=1): **0,001713** (valor exacto 0,0017134, sea con los F1 completos o con los redondeados a seis decimales). El borrador decía 0,001714; la cifra correcta es 0,001713.
- Regla (la de v6): pasa solo si la media es positiva **y** mayor que la desviación. Aquí 0,001095 < 0,001713.

**NO PASA.** La mejora media es pequeña y menor que la variación entre pliegues; en el pliegue 4, v10 queda por debajo de v6.

## 4. Gates verificados

- **Reproducción:** en el pliegue 1, la combinación (0,75; 0,25; 0) da F1 0,4438442. La diferencia con 0,443844 es 1,5e-7 y la tolerancia era 1e-6.
- **AST idéntico:** `URL_RE`, `MENTION_RE`, `REPEAT_RE`, `replace_url`, `normalize_text`, `TOKEN_RE`, `tokenize`, `make_encoder`, `encode_text`, `estimate_discounts`, `discount_for`, `ModifiedKN` y `test_modified_kn` tienen el mismo AST que en v6, e `inner_split` el mismo que en v9. Se comparó contra la copia literal guardada en el notebook y contra los notebooks originales.
- **Datos:** el SHA-256 de `age_train.csv` coincide con el `train_sha256` del NPZ. Hay 155 exclusiones.
- **Pliegues:** los tamaños de validación son 26.519, 26.654, 26.979, 26.627 y 26.286, los esperados.
- **Pesos:** las 15 combinaciones suman 1 (tolerancia 1e-12) e incluyen la de v6.
- **Disjunción:** en cada pliegue, core, inner y la validación exterior no comparten filas ni textos normalizados.
- **Raíces:** al volver a tokenizar el texto de raíces se obtienen exactamente las mismas raíces, en train y en test.
- **Cumplimiento:** una guardia AST sobre todo el código ejecutado no encontró vectorizadores, embeddings, redes, lematizadores ni modelos preentrenados.
- **Reanudación:** en la segunda ejecución todo salió de la caché y los resultados fueron idénticos (las huellas coincidieron).

## 5. Diagnósticos

- **Cada modelo solo** (F1 macro con log prior, rango en los cinco pliegues): caracteres 0,416 a 0,429; raíces 0,405 a 0,417; palabras 0,403 a 0,408. La raíz sola queda entre palabras y caracteres.
- **Tokens que cambian** al aplicar la raíz: cerca del 31 % (30,87 % a 30,96 % según el pliegue). La cifra incluye los tokens que solo pierden la tilde.
- **Vocabulario** (frecuencia ≥ 2) por pliegue: de unos 39.500 tipos de palabra se pasa a unas 25.700 raíces. Sin umbral, de unos 91.000 tipos se pasa a unos 61.000.
- **Pesos elegidos:** (0,75; 0; 0,25) en 3 de 5 pliegues, (0,50; 0; 0,50) en uno y (0,50; 0,25; 0,25) en otro. En 4 de 5 pliegues la raíz reemplaza a las palabras en vez de sumarse a ellas.
- **Predicciones OOF:** v10 corrige un poco la sobrepredicción de 65-xx que tenía v6 (23.032 → 22.336, frente a 21.002 reales). Sigue faltando 35-49 (18.713 predichas frente a 22.219 reales).

## 6. Qué no se hizo y por qué

La regla no se cumplió, así que no se evaluó el holdout, no se entrenó con el train completo y no se generó submission. No se envió nada a Kaggle. El holdout sigue sin usar para esta línea.

## 7. Notas

- Quitar las tildes con NFD y descartar las marcas `Mn` también convierte la **ñ en n** (por ejemplo, "año" y "ano" comparten raíz). Es un efecto secundario del método copiado del notebook de análisis del corpus. **Falta decidir** si se conserva la ñ en una versión futura.
- El notebook cita `claude/DECISION_REGLAS_TWEETAGE.md`. Ese documento está en el Proyecto, no en el repositorio.
- La submission, si la regla hubiera pasado, se habría escrito en `RESULTS/tweetage_v10_submission.csv`.

## 8. Referencias

- Notebook: `workshops/Kaggle-tweet-age/TweetAge_v10_raices_kn.ipynb`. Está en la copia local del repositorio, sin salidas y sin commit.
- Ejecución local: `claude/v10_resultados_locales/` contiene `tabla_cv.csv`, `metricas_cv.json`, `diagnostico_pliegues.csv`, `diagnostico_raices.csv`, `distribucion_predicciones.csv`, `ejecucion.log`, y el `resultado.json` y la tabla de las 15 combinaciones de cada pliegue. Las matrices de scores (`.npz`) no se copiaron. En Colab, el mismo notebook escribe todo en `RESULTS/tweetage_v10_raices/`.
- `claude/PROMPT_TWEETAGE_V10_RAICES_KN.md` (instrucciones del experimento).
- `claude/DECISION_REGLAS_TWEETAGE.md` (reglas).
