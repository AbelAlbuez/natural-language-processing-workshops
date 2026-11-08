# reports/

| Archivo | Contenido |
|---|---|
| `RESULTADOS.md` | Resultados y análisis (recuperación, limpieza, corpus completo, abstención, estado de la generación). Solo cifras medidas. |
| `crudos/evaluacion_*_antes_de_limpieza.jsonl` | Resultado por pregunta de la primera evaluación (índice reducido, sin limpieza), uno por gold. |
| `demo_trazas.md` | Lo genera `scripts/demo_rag.py` (salida real de la API). Aún no existe: se crea al correr la demo. |

**Copiar desde `data/` tras correr los experimentos** (los generan los scripts; no se pudieron incluir aquí):
`evaluacion_nuestro.json(l)`, `evaluacion_abel.json(l)` (índice reducido y limpio), `exp_full.jsonl` y `exp_full.jsonl.resumen.json`
(corpus completo), `exp_completo2.jsonl` (generación, incompleta), y los de Solr cuando se corran.
No contienen texto de documentos ni de respuestas.
