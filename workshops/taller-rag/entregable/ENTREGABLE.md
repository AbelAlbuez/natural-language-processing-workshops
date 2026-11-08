# Entregable: asistente RAG con Milvus y Solr

Carpeta autocontenida del repositorio. Qué pide la entrega y dónde está:

| Requisito | Dónde |
|---|---|
| **Código fuente completo (API, indexadores y evaluadores)** | API: `app/api.py`, `app/rag.py`, `app/solr_backend.py`, `app/core.py`, `app/milvus_schema.py`, `app/frontend.py`. Indexadores: `scripts/ingest.py`, `scripts/ingest_milvus.py`, `scripts/embed_chunks.py`, `scripts/ingest_solr.py`, `data/ingest_gold.py`. Evaluadores: `scripts/ejecutar_experimento_robusto.py`, `data/evaluar_gold.py`, `scripts/metricas_rag.py`, `scripts/comparar_backends.py`, `scripts/analisis_resultados.py`. Demo: `scripts/demo_rag.py`. Pruebas: `tests/` |
| **`docker-compose.yml` funcional** | `docker-compose.yml` (Milvus, Ollama, Solr, API, interfaz). Guía paso a paso: `docs/EJECUCION.md` |
| **Carpeta `reports/`** | `reports/RESULTADOS.md` (resultados y análisis), `reports/informe_evaluacion_rag.pdf`, `reports/crudos/` (resultados por pregunta), `reports/comparacion_milvus_solr.*` y `reports/demo_trazas.md` (se generan al correr la demo y la comparación) |
| **Queries y gold estándar** | `data/gold/queries.csv` (las 100 preguntas de los dos gold), `data/gold/gold.jsonl` (gold ampliado, 60 verificadas), `docs/gold_standard.csv` (gold de Abel, 40), `data/gold/pool_final.xlsx` (pool de trabajo), `docs/cuotas_gold.json`, `docs/temas_gold.json` |

## Arranque rápido
```
copy .env.example .env
docker compose up -d --build
docker compose ps
```
Todo el detalle (modelos, indexación en Milvus y Solr, demo, evaluación, problemas frecuentes) está en `docs/EJECUCION.md`.

## Estado honesto
- Verificado con datos reales: recuperación en Milvus (índice reducido y corpus completo), limpieza del relleno de portal, evaluación de los dos gold.
- **Solr:** el código tiene pruebas unitarias y se probó contra simuladores; los resultados de Solr de `reports/` dependen de haberlo corrido contra un Solr real (ver `docs/SOLR.md`). Si `reports/comparacion_milvus_solr.md` no existe, esa comparación no se ha ejecutado.
- La corrida de generación con LLM de la evaluación complementaria no se completó (ver `reports/RESULTADOS.md`, sección 5).
- Datos restringidos y pesos de modelos **no** están en el repositorio: `data/documentos_rag.parquet`, embeddings y `.env`.
