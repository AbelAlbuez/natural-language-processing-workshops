# Aportes al repositorio (evaluación, limpieza, robustez y Solr)

Esta carpeta se **superpone** al repositorio de Abel: copia su contenido encima, conservando las rutas.
No incluye los archivos de Abel que no cambian (rag.py, milvus_schema.py, core.py, ingest*.py, embed_chunks.py, metricas_rag.py...).

## Qué contiene
| Ruta | Qué es | ¿Modifica algo de Abel? |
|---|---|---|
| `app/api.py` | API con `backend: milvus \| solr` y estado de Solr en `/health` | **Sí**: reemplaza `app/api.py` (diferencia: solo agrega el backend; el flujo Milvus no cambia) |
| `app/solr_backend.py` | Cliente Solr (esquema, indexación, BM25) | No (nuevo) |
| `docker-compose.solr.yml` | Servicio Solr y variables de la API | No (se usa junto a `docker-compose.yml`) |
| `data/ingest_gold.py` | Indexa los gold más distractores en Milvus y/o Solr, con `--limpiar` | No (nuevo) |
| `data/evaluar_gold.py`, `scripts/ejecutar_experimento_robusto.py`, `scripts/diagnostico_errores.py` | Evaluadores (ambos gold, `--backend`, reanudar, reintentar errores) | No (nuevos) |
| `scripts/demo_rag.py` | Demo: misma pregunta con Milvus y con Solr | No (nuevo) |
| `scripts/ingest_solr.py` | Indexa en Solr los chunks de `chunks_tok256.parquet` (corpus completo, mismos chunks que Milvus) | No (nuevo) |
| `scripts/comparar_backends.py` | Tabla Milvus vs Solr (Markdown y LaTeX) a partir de los dos resúmenes | No (nuevo) |
| `docs/EJECUCION.md` | **Guía paso a paso para ejecutar la pila (Milvus + Solr)** | No |
| `scripts/gold_excel.py`, `scripts/validar_gold.py`, `data/{traer_documentos,exportar_pool,semillas,buscar_frases}.py` | Construcción y validación del gold | Si ya existen `gold_excel.py`/`validar_gold.py` en `scripts/`, compara antes de reemplazar |
| `data/gold/gold.jsonl`, `data/gold/pool_final.xlsx`, `data/gold/queries.csv` | Gold ampliado (60 verificadas) y lista plana de las 100 preguntas de los dos gold | No |
| `docs/gold_standard.csv`, `docs/cuotas_gold.json`, `docs/temas_gold.json` | Copia del gold de Abel (referencia) | Ya existen en su repo; son idénticos |
| `docs/SOLR.md` | Diseño, comandos y limitaciones de RAG–Solr | No |
| `tests/test_solr_backend.py` | 6 pruebas del módulo Solr (`pytest tests`) | No |
| `reports/` | `RESULTADOS.md`, `informe_evaluacion_rag.pdf`, resultados crudos de la primera evaluación | No |

## Integrarlo (PowerShell, un comando por línea, desde la carpeta que contiene este LEEME)
```
Copy-Item -Recurse -Force .\app\* C:\ruta\al\repo\workshops\taller-rag\proyecto\app\
```
Repite para `data`, `scripts`, `docs`, `tests`, `reports`, y copia `docker-compose.solr.yml` a la carpeta del proyecto.
Antes de reemplazar `app\api.py`, compara con el tuyo: `git diff --no-index app\api.py C:\ruta\al\repo\...\app\api.py`.

## Pendiente de verificar (honestidad)
- **Solr real:** nunca se ejecutó. Pasos y comandos: `docs/SOLR.md`. Hasta entonces no hay resultados de Solr.
- **Compose:** este paquete no reemplaza `docker-compose.yml`; Solr se añade con `-f docker-compose.yml -f docker-compose.solr.yml`.
- **Resultados crudos recientes** (`data/evaluacion_*.json(l)`, `exp_full.jsonl*`, `exp_completo2.jsonl`): cópialos desde tu carpeta `data\` a `reports\crudos\` (ver `reports/README.md`).
- **Demo:** `reports/demo_trazas.md` se genera al correr `scripts/demo_rag.py`; no se incluye una traza falsa.
