# Protocolo de evaluación

## 1. Gold standard

El gold standard contiene 40 preguntas. Las cuotas siguientes corresponden al idioma de la pregunta y la fuente esperada de la evidencia:

| Fuente esperada | es | en | Total |
|---|---:|---:|---:|
| `media_cloud` | 16 | 9 | 25 |
| `bluesky` | 5 | 9 | 14 |
| `gdelt` | 1 | 0 | 1 |
| **Total** | **22** | **18** | **40** |

Hay 18 preguntas en inglés de 40, es decir, 45 %. Esto supera el mínimo de 15 %. El idioma de los documentos relevantes se registrará por separado del idioma de la pregunta.

## 2. Hipótesis y criterio de decisión

Se conserva la hipótesis PI6 de [propuestas_investigacion.md](propuestas_investigacion.md):

> Recall@5 es menor en Bluesky que en Media Cloud para preguntas del mismo idioma, comparando cada idioma por separado; además, la abstención correcta es menor para preguntas en inglés que para preguntas en español.

Criterio de PI6: se considerará refutada si el intervalo de confianza del 95 % de las diferencias incluye cero o apunta en sentido contrario. Los intervalos se estimarán con remuestreo de las preguntas del gold standard.

Se reportarán Recall@k (k = 1, 3, 5, 10), MRR, nDCG@10, abstención correcta y fidelidad de citas, desglosados por fuente esperada, idioma de la pregunta e idioma de los documentos relevantes.

## 3. Advertencia sobre el tamaño de muestra

Bluesky en español cuenta con solo 5 preguntas y GDELT con 1. Los resultados de esos estratos se presentarán como estimaciones con sus intervalos, no como conclusiones firmes. En particular, el intervalo de Bluesky-es será muy amplio; el único caso GDELT no permite una conclusión generalizable.

## 4. Evaluación final y preguntas de desarrollo

Las 40 preguntas del gold standard se usan para la evaluación final. Todos los parámetros (chunking, encoder, índice, `top-k`, prompt y LLM) se congelan antes de correr el experimento y no se ajustan mirando el gold standard.

Si hace falta ajustar algún parámetro, se usan preguntas de desarrollo separadas, escritas aparte del gold standard y marcadas como tales. Su número y sus cuotas se definirán más adelante.

## 5. Evaluación humana

Dos anotadores evaluarán de forma independiente una submuestra de respuestas con la misma rúbrica de corrección, fidelidad y citas. Se calculará kappa de Cohen para medir el acuerdo antes de resolver discrepancias. La selección de la submuestra se hará procurando cubrir las condiciones evaluables; en estratos pequeños se anotarán todos los casos disponibles y se informará su tamaño.

LLM-as-judge será solo complementario: no sustituirá la evaluación humana ni la referencia anotada. Se reportará por separado y se contrastará con las valoraciones humanas.

## 6. Variables controladas

Se mantienen fijos en todos los experimentos:

- Corpus y versión de los datos.
- Estrategia y parámetros de chunking.
- Encoder.
- Índice y su configuración.
- `top-k` de recuperación.
- Prompt.

Entre condiciones experimentales, solo cambia el LLM. La configuración de cada condición se congela antes de correr la evaluación final. Cualquier desviación de estas variables invalida la comparación directa y debe documentarse.

## 7. Registro por corrida

Cada corrida debe registrar:

- Fecha y hora.
- Fecha de congelación de parámetros: pendiente de llenar.
- Hardware utilizado.
- Semilla de la corrida y semilla del remuestreo (42).
- Versiones de software, bibliotecas, encoder, índice y LLM.
- Configuración experimental y condición evaluada.
- Tiempos de ejecución y latencias.
- Tokens de entrada y salida.
- Métricas agregadas y por estrato.

## 8. Intervalos de confianza del 95 %

Método: bootstrap pareado y estratificado por fuente e idioma de la pregunta, remuestreando preguntas completas para conservar emparejadas las condiciones; usar el intervalo percentil del 95 %.

Número de remuestreos: 10.000, como propuesta sujeta a revisión. Semilla: 42. Se registra en este protocolo y en el registro por corrida.

Con estratos de 5 o 1 preguntas, el bootstrap no elimina la incertidumbre derivada del tamaño muestral. Sus intervalos se interpretarán con cautela y esos resultados seguirán siendo estimaciones, no conclusiones firmes.
