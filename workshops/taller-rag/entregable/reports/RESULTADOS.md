# Resultados y análisis

Todas las cifras salen de las ejecuciones indicadas; nada está estimado. Recuperación a **nivel de documento**
(los fragmentos se colapsan al primer rango), `k = 10`, partición de **prueba**: 34 preguntas con respuesta del gold
nuestro y 17 sintéticas del gold de Abel (51 en total).

## 1. Dos índices, dos gold
- **Índice reducido (limpio):** 2.081 documentos citados por los dos gold + 2.000 distractores (semilla 42), segmentación
  256/48 con E5, 8.275 chunks. Colección `rag_gold_e5s_tok256_limpio`.
- **Corpus completo:** colección `rag_e5s_tok256_v1` de Abel, 577.324 chunks, **sin** limpieza.
- **Gold nuestro:** 60 preguntas verificadas, 6 tipos, varios documentos relevantes, 10 sin evidencia.
  **Gold de Abel:** 40 preguntas (34 sintéticas, 6 no respondibles), un documento relevante, sin revisión humana.

## 2. Efecto de la limpieza del relleno de portal (índice reducido, antes → después)
| Gold | Métrica | Antes | Después |
|---|---|---|---|
| Nuestro (34) | Recall@1 | 0,444 | 0,532 |
| Nuestro (34) | Recall@10 | 0,591 | 0,669 |
| Nuestro (34) | MRR | 0,549 | 0,637 |
| Abel (17) | Recall@10 | 0,647 | 1,000 |

Causa: 10 artículos de EL TIEMPO empiezan con el aviso de cookies y el mensaje de inicio de sesión; sus primeros
fragmentos aparecían en el top-10 de 13 de las 64 consultas (8 de 18 fallos de recuperación; 5 de las sin respuesta).
La hipótesis de duplicados exactos se descartó: las tablas con y sin deduplicación fueron idénticas.

## 3. Índice reducido vs corpus completo (prueba, k = 10)
| Tipo | n | R@10 reducido | MRR reducido | R@10 completo | MRR completo |
|---|---|---|---|---|---|
| Todas | 51 | 0,779 | 0,758 | 0,453 | 0,374 |
| Sintética (Abel) | 17 | 1,000 | 1,000 | 0,706 | 0,608 |
| Factual | 15 | 0,867 | 0,867 | 0,533 | 0,335 |
| Comparativa | 8 | 0,344 | 0,400 | 0,073 | 0,150 |
| Temporal | 4 | 0,750 | 0,536 | 0,375 | 0,375 |
| Adversarial | 4 | 0,500 | 0,500 | 0,250 | 0,250 |
| Interpretativa | 3 | 0,667 | 0,444 | 0,000 | 0,000 |

Control de validez: las 17 sintéticas en el corpus completo dan R@1 = 0,529 y R@10 = 0,706, iguales a los del informe de Abel.
Las cifras del corpus completo son una **cota inferior**: hay documentos válidos adicionales que el gold no marca.
R@3 y R@5 de aquí cuentan documentos distintos dentro de 10 fragmentos; los de Abel usan 5 fragmentos (≤ 5 documentos): solo R@1 y R@10 son comparables.

## 4. Abstención
- Con el umbral 0,80, el índice reducido detecta 1 de 13 casos sin respuesta; el corpus completo, 0 de 13.
- Las puntuaciones máximas se solapan (sin respuesta 0,79–0,92; con respuesta 0,85–0,93): el coseno del mejor fragmento no basta.
- El umbral calibrado en desarrollo (0,83–0,84) se obtuvo con solo 3 casos a abstener: poco fiable.
- Barrido en prueba (descriptivo, no para elegir el umbral): mejor F1 = 0,62 en el índice reducido (umbral 0,86) y 0,39 en el completo (0,88).

## 5. Generación (LLM)
La corrida con LLM de este equipo **no se completó**: `gemma2:2b` falló en las 64 preguntas y `qwen2.5:1.5b` respondió 15 de 24
(un 503 tras 241 s, igual al `OLLAMA_TIMEOUT` de 240 s, probablemente por una generación abandonada al interrumpir). No se reportan métricas
de generación de esta corrida. El experimento de Abel (4 modelos, 80 corridas, 17 respondibles) está en su informe: citas válidas en 5–16 de 17
y ningún modelo se abstuvo en las no respondibles. `scripts/ejecutar_experimento_robusto.py --reanudar --reintentar-errores` reintenta solo lo fallido.

## 6. Milvus vs Solr
**Pendiente de ejecución** (ver `docs/SOLR.md`). No hay cifras de Solr; las hipótesis están en ese documento.

## 7. Limitaciones
Índice reducido (1,4 % del corpus) en la parte con gold ampliado; cota inferior de recall en el corpus completo; estratos pequeños
(3–8 preguntas por tipo); gold de Abel sin revisión humana y solo de un tipo; 30 borradores del pool sin revisar (no usados); una repetición, sin intervalos de confianza;
generación sin corrección evaluada; Solr sin ejecutar.

## 8. Recomendaciones
1. Limpiar el relleno de portal antes de segmentar (nueva versión de datos) y reindexar el corpus completo.
2. Reemplazar la abstención por umbral de coseno por otra señal (margen top-1/top-2, reranker o verificación con el LLM) y calibrarla con más casos sin respuesta anotados.
3. Para comparativas, recuperar por documento (agrupar/limitar fragmentos por documento) o consultar en varios pasos.
4. Ejecutar la comparación Milvus vs Solr y probar un híbrido (fusión RRF) si son complementarios.
5. Completar la revisión humana del gold de Abel y de los 30 borradores; repetir cada condición y dar intervalos de confianza.
