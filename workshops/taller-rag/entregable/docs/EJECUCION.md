# Cómo ejecutar la pila con Milvus y Solr (guía para quien reciba el Docker)

Requisitos: Docker Desktop (o Docker en Linux) con **al menos 8 GB de RAM** asignados (12 GB si se indexa el corpus completo en Solr),
el repositorio con los aportes copiados, `.env` creado desde `.env.example`, y `data/documentos_rag.parquet` (no está en GitHub).
Comandos en una terminal, **un comando por línea**, desde `workshops/taller-rag/proyecto`. En Windows use PowerShell; `curl` es `curl.exe`.

## 0. Cambios obligatorios tras copiar los aportes
La imagen de la API **hornea** `app/` y `scripts/`. Si se copian archivos nuevos hay que reconstruirla (si no, `ModuleNotFoundError: app.solr_backend`):
```
docker compose -f docker-compose.yml -f docker-compose.solr.yml build api
```

## 1. Levantar Milvus, Ollama, Solr, API e interfaz
```
docker compose -f docker-compose.yml -f docker-compose.solr.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.solr.yml ps
```
Esperar a que `milvus`, `ollama`, `solr` y `api` digan `healthy` (Milvus tarda hasta ~2 min). Interfaz: http://localhost:8501 · API: http://localhost:8000 · Solr: http://localhost:8983/solr

Descargar los modelos (una vez; ~1 GB cada uno):
```
docker compose exec ollama ollama pull gemma2:2b
docker compose exec ollama ollama pull llama3.2:1b
docker compose exec ollama ollama pull qwen2.5:1.5b
```

## 2. Indexar (elegir A o B)
Para no escribir `-f ... -f ...` cada vez: `$env:COMPOSE_FILE="docker-compose.yml;docker-compose.solr.yml"` (PowerShell) o
`export COMPOSE_FILE=docker-compose.yml:docker-compose.solr.yml` (Linux/macOS).

### A. Piloto con los gold (cualquier máquina; minutos). Necesita `data/documentos_rag.parquet`.
Indexa los ~2.081 documentos de los dos gold más 2.000 distractores, **en Milvus y en Solr, con los mismos chunks y la limpieza del relleno**:
```
docker compose exec -e PYTHONPATH=/work api python data/ingest_gold.py --csv docs/gold_standard.csv --destino ambos --limpiar --coleccion rag_gold_e5s_tok256_limpio --dry-run
docker compose exec -e PYTHONPATH=/work api python data/ingest_gold.py --csv docs/gold_standard.csv --destino ambos --limpiar --coleccion rag_gold_e5s_tok256_limpio
```
Luego apuntar la API a esa colección: en `.env` poner `MILVUS_COLLECTION=rag_gold_e5s_tok256_limpio` y `docker compose up -d --force-recreate api`.
(Si la colección existente tiene el esquema antiguo, usar siempre un nombre nuevo.)

### B. Corpus completo (577.324 chunks; instancia de Abel). Necesita `data/chunks_tok256.parquet` y los embeddings.
Milvus ya está cargado en esa instancia (`rag_e5s_tok256_v1`). Solo falta Solr, **con los mismos chunks**:
```
docker compose exec -e PYTHONPATH=/work api python scripts/ingest_solr.py --chunks data/chunks_tok256.parquet --documents data/documentos_rag.parquet --limite 5000
docker compose exec -e PYTHONPATH=/work api python scripts/ingest_solr.py --chunks data/chunks_tok256.parquet --documents data/documentos_rag.parquet
```
El primero es una prueba (5.000 chunks). El segundo carga todo (idempotente; si se corta, repetir con `--desde N`).
Para el corpus completo conviene `SOLR_HEAP=2g` y `SOLR_MEM=3g` en `.env`. Nota: estos chunks **no** tienen la limpieza del relleno
(igual que el Milvus de Abel); así la comparación Milvus–Solr es sobre la misma población.

## 3. Verificar
```
curl.exe -s "http://localhost:8000/health?deep=true"
```
Debe mostrar `"milvus": {"ok": true, "rows": ...}` y `"solr": {"ok": true, "rows": ...}`. Si `solr.rows` es 0, falta indexar.

## 4. Demo (RAG–Milvus y RAG–Solr, la misma pregunta)
```
python scripts/demo_rag.py --demo-gold --sin-llm
python scripts/demo_rag.py --pregunta "¿En qué ciudad colombiana se realizó la COP16 del Convenio sobre la Diversidad Biológica?" --modelo gemma2:2b
```
Deja la traza real en `reports/demo_trazas.md`. (`demo_rag.py` solo necesita Python 3 en el equipo, no instala nada.)

## 5. Evaluación y comparación
```
python scripts/ejecutar_experimento_robusto.py --gold docs/gold_standard.csv data/gold/gold.jsonl --backend milvus --solo-retrieve --salida reports/crudos/exp_milvus.jsonl
python scripts/ejecutar_experimento_robusto.py --gold docs/gold_standard.csv data/gold/gold.jsonl --backend solr --solo-retrieve --salida reports/crudos/exp_solr.jsonl
python scripts/comparar_backends.py reports/crudos/exp_milvus.jsonl.resumen.json reports/crudos/exp_solr.jsonl.resumen.json
```
Con LLM (lento en CPU; unos 15–40 s por respuesta): quitar `--solo-retrieve`. Se puede cortar y retomar con `--reanudar`,
y reintentar solo lo fallido con `--reanudar --reintentar-errores`. Si hay errores: `python scripts/diagnostico_errores.py reports/crudos/exp_milvus.jsonl`.
Si Ollama tarda o falla, reiniciarlo antes de reintentar: `docker compose restart ollama`.

## 6. Problemas frecuentes
| Síntoma | Causa y arreglo |
|---|---|
| `ModuleNotFoundError: app.solr_backend` | Imagen vieja: `docker compose build api` y recrear. |
| `/health` sin bloque `solr` | Falta `-f docker-compose.solr.yml` (o `COMPOSE_FILE`). |
| `solr.ok: false`, `HTTP 404` | El core no existe: Solr debe arrancar con `solr-precreate` (ya está en el compose); `docker compose logs solr`. |
| Indexación lenta o contenedor reiniciado por memoria | Subir RAM de Docker y `SOLR_MEM`/`API_MEM`; en la API, `docker update --cpus 12 rag-api` (se revierte al recrear). |
| `/ask` con 503 tras ~240 s | Ollama saturado (una petición a la vez) o `OLLAMA_TIMEOUT`; reiniciar Ollama y reintentar con `--reintentar-errores`. |
| Colección con esquema antiguo | Usar un nombre nuevo en `--coleccion` y en `MILVUS_COLLECTION`. |

## Qué NO está verificado
Solr real no se ejecutó nunca (solo simuladores y pruebas unitarias); los comandos de Solr de esta guía son los que hay que correr primero.
