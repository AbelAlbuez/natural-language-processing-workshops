# Alternativas para TweetAge después de v10

Este documento **no decide qué correr**. Ordena las opciones por ganancia esperada y riesgo, a partir de lo que ya muestra el historial (`HISTORIAL_SOLUCIONES_TWEETAGE.md`). Ninguna alternativa se ha ejecutado.

**Reglas que valen para todas:**
- Solo modelos probabilísticos de lenguaje entrenados por el equipo.
- Prohibido: embeddings, Word2Vec, GloVe, TF-IDF, cualquier vectorización (incluidos one-hot, bolsas de palabras y NB-SVM), modelos preentrenados y transformers. LSTM y GRU están en zona gris y no son candidatas a solución final.
- Partición: `split_idx_v6_seed42.npz` y sus cinco pliegues, sin regenerarla. El holdout solo se usa si se pasa el criterio, y una sola vez.
- Referencia: v6 sin calibrar, con (0,75; 0,25; 0), que reproduce 0,443844 en el pliegue 1.

## Antes de elegir: cuántas veces se ha probado ya

- Se han comparado **284 configuraciones** en total, 217 de ellas en versiones conformes o en zona gris.
- Desde v7 se hicieron **23 pruebas pareadas contra v6**, y ninguna pasó.
- Con la regla actual (media > 0 y media > desviación, con 5 pliegues), cada prueba sin mejora real pasa por azar alrededor del 4,5 % de las veces. En 23 pruebas eso da cerca de 1 falso positivo esperado.

**Propuesta, que el equipo debe decidir y registrar en `DECISION_REGLAS_TWEETAGE.md` antes de correr nada:** para las alternativas nuevas, exigir **media > 0 y media > 2 × desviación muestral (ddof=1)**. Eso baja la tasa de falso positivo por prueba a un 0,55 %, aproximadamente. Si se mantiene la regla actual, cualquier "pasa" por poco debería tratarse con cautela.

En todos los criterios de abajo, "regla" significa la versión que el equipo fije, y la diferencia es F1 macro de la alternativa menos F1 macro de v6 en los mismos cinco pliegues.

---

## 1. Calibración de sesgos por clase, anidada

- **Qué cambia:** a cada clase se le suma un sesgo b_c, igual que en v6. La diferencia es que los sesgos se ajustan **solo en el 10 % interno de cada pliegue** (el *inner* de v10) y luego se aplican sin tocarlos a la validación exterior. Los modelos de lenguaje no cambian: caracteres 4 y palabras 3, con pesos (0,75; 0,25).
- **Por qué podría ayudar:** las predicciones OOF de v6 están desbalanceadas:
  - 35-49: se predicen 18.701 frente a 22.219 reales.
  - 50-64: se predicen 25.040 frente a 21.959.
  - 65-xx: se predicen 23.032 frente a 21.002.

  El F1 macro castiga ese desbalance. En v6, calibrar sobre el OOF subió el F1 de 0,44106 a 0,44353 (+0,0025). Esa cifra es optimista porque se calibró con las mismas etiquetas que se evaluaron; la versión anidada mide cuánto de esa ganancia es real.
- **Cumple el enunciado:** sí. Son 6 desplazamientos sobre log P(texto | clase) + log prior, equivalentes a reajustar el prior. No hay ninguna representación del texto.
- **Riesgo:**
  - **Puede sobreajustar.** El inner tiene unas 10.600 filas, y la búsqueda por coordenadas de v6 puede perseguir ruido.
  - Hay además un pequeño desajuste: los sesgos se aprenden sobre modelos entrenados con el 90 % (core) y se aplican a modelos entrenados con el 100 %.
  - Mitigación: usar la misma rejilla y el mismo número de pasadas de `calibrate_bias` de v6, sin afinarlos.
- **Costo:** bajo. Se reutiliza el código de v10 (scores de *inner* y exteriores); en local son unos 3 minutos para los cinco pliegues, y en Colab con CPU algo más. No hay que entrenar modelos nuevos si se conservan los `.npz` de v10.
- **Criterio fijado antes de correr:**
  - Pasa si la diferencia frente a v6 sin calibrar cumple la regla.
  - Se reporta también el F1 OOF calibrado y el de v6 calibrado sobre el OOF (0,44353), solo como contexto.
  - Si F1 en inner sube y F1 exterior baja en 3 o más pliegues, se registra como sobreajuste.

## 2. Mantener las mayúsculas en el modelo de palabras

- **Qué cambia:** el tokenizador de palabras de v6 deja de pasar el texto a minúsculas. `TOKEN_RE` no cambia. El modelo de caracteres ya conserva las mayúsculas. Orden 3 y pesos (0,75; 0,25) fijos.
- **Aclaración sobre "separar la puntuación":** v6 ya lo hace. `TOKEN_RE` separa cada signo como un token propio (`[^\w\s]`). Probar "separar puntuación" no sería una hipótesis nueva. Una variante distinta sería agrupar las rachas de signos (`!!!` como un solo token), pero eso se solapa con la limitación de repeticiones que ya probó v7_normalizacion (brazo B, −0,000375).
- **Por qué podría ayudar:** en v7_normalizacion, pasar más texto a minúsculas (brazo C) costó −0,0032. Eso sugiere que las mayúsculas llevan información de edad que el modelo de palabras hoy descarta.
- **Cumple el enunciado:** sí.
- **Riesgo:** el vocabulario crece y aumentan los tokens que pasan a UNK (frecuencia < 2), lo que puede anular la ganancia. El efecto esperado es pequeño.
- **Costo:** bajo. Es una ejecución tipo v6 con un cambio de una línea; unos 3 minutos en local para los cinco pliegues.
- **Criterio fijado antes de correr:** pasa si la diferencia frente a v6 cumple la regla. Los pesos y los órdenes no se tocan.

## 3. Otro suavizado: Witten-Bell o interpolación con descuento absoluto

- **Qué cambia:** se reemplaza el Kneser-Ney modificado por Witten-Bell, o por interpolación con descuento absoluto único, en ambos niveles. Órdenes 4 y 3, pesos (0,75; 0,25) fijos.
- **Por qué podría ayudar:** casi no hay razón para esperar mejora.
  - Chen y Goodman (1999) muestran que KN modificado suele superar a los dos.
  - El historial apunta en la misma dirección:
    - PPM-C (v8), cuyo escape es de tipo Witten-Bell, quedó 1,8 puntos por debajo.
    - El descuento con concentración (v7) movió solo milésimas, hacia abajo.
    - v5, con un D único de 0,75, es básicamente la interpolación absoluta, y quedó por debajo de v6.
- **Cumple el enunciado:** sí.
- **Riesgo:** bajo de implementar, pero lo más probable es un resultado negativo más. Sumaría una prueba al conteo de comparaciones múltiples.
- **Costo:** medio-bajo. Hay que escribir y validar el suavizado (normalización a 1, pruebas como `test_modified_kn`) y luego ejecutar unos 3 minutos.
- **Criterio fijado antes de correr:** pasa si la diferencia frente a v6 cumple la regla. Antes de la CV, un gate: las probabilidades de cada historial suman 1 con tolerancia 1e-9.

## 4. Otros órdenes de KN con pesos fijos

- **Qué cambia:** caracteres de orden 3 o 5 y palabras de orden 2 o 4, con pesos (0,75; 0,25) fijos y sin búsqueda.
- **Por qué podría ayudar:** es poco probable que ayude. Estos órdenes ya se cubrieron:
  - v6 recorrió caracteres 3 a 6 y palabras 1 a 3, y eligió 4 y 3.
  - v7_hiperparametros probó 8 combinaciones, entre ellas caracteres 5 con palabras 4; la mejor quedó −0,0024 por debajo.
  - v8 probó caracteres 6 y 7, ambos por debajo.

  Repetirlo sería volver a hacer pruebas ya hechas, y solo inflaría el conteo.
- **Cumple el enunciado:** sí.
- **Riesgo:** casi seguro negativo. Si alguna variante "pasara", probablemente sería por azar, dado el número de pruebas previas sobre la misma familia.
- **Costo:** bajo, unos 3 minutos por variante en local.
- **Criterio fijado antes de correr:** solo si el equipo lo decide, como máximo **una** variante elegida antes de correr (no varias). Pasa si cumple la regla más estricta (media > 2 × desviación).

## 5. Raíces fijas (0,75; 0; 0,25) o raíces conservando la ñ (no recomendada)

- **Qué cambia:** fijar la combinación que v10 eligió más veces, o rehacer v10 sin convertir la ñ en n.
- **Por qué podría ayudar:** en v10, la combinación (0,75; 0; 0,25) se eligió en 3 de 5 pliegues.
- **Cumple el enunciado:** sí.
- **Riesgo:** **alto de sesgo.** Esa combinación se descubrió mirando resultados de v10 en los mismos pliegues. Evaluarla en esos pliegues sería elegir con los datos de evaluación, y el único dato limpio que queda es el holdout. Lo de la ñ afecta a pocas palabras, así que su efecto esperado es mínimo.
- **Costo:** bajo.
- **Criterio fijado antes de correr:** no se recomienda correrla. Si se hiciera, debería contar como una prueba nueva con la regla estricta, dejando escrito que la hipótesis viene de v10.

## 6. Parar y quedarse con v6

- **Qué cambia:** nada. v6 sigue siendo la solución conforme, con holdout 0,418466 y público 0,45737 citado.
- **Por qué:**
  - Las 23 pruebas desde v7 no pasaron.
  - Las mejoras observadas son de milésimas y menores que la variación entre pliegues.
  - La familia de modelos de lenguaje de n-gramas parece estar en su techo con estos datos.
- **Cumple el enunciado:** sí.
- **Costo:** ninguno. Libera tiempo para documentar y para el informe.
- **Criterio:** no aplica.

---

## Orden sugerido (por ganancia esperada y riesgo)

| Orden | Alternativa | Ganancia esperada | Riesgo | Costo |
|---|---|---|---|---|
| 1 | Calibración anidada de sesgos | Pequeña pero plausible (hasta unos +0,002) | Sobreajuste | Bajo |
| 2 | Mayúsculas en el modelo de palabras | Pequeña (0 a +0,002) | Bajo | Bajo |
| 3 | Witten-Bell / descuento absoluto | Negativa o nula | Bajo, pero suma pruebas | Medio-bajo |
| 4 | Otros órdenes KN | Nula (ya probado) | Falso positivo | Bajo |
| 5 | Raíces fijas / ñ | Mínima | Alto (sesgo de selección) | Bajo |
| 6 | Parar con v6 | No aplica | Ninguno | Ninguno |

Si se corre algo, conviene limitarlo a las alternativas 1 y 2, con el criterio estricto registrado antes. Si ninguna pasa, la alternativa 6.
