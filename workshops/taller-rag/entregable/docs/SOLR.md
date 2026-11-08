# RAG–Solr (recuperación léxica BM25) junto a RAG–Milvus (denso)

> **Estado:** el código está probado con pruebas unitarias (`pytest tests`) y contra simuladores de Solr, Milvus
> y Ollama (indexación, esquema, búsqueda, API y demo). **No se ha ejecutado contra un Solr real.** Los resultados
> de Solr de este repositorio están por generar con los comandos de abajo; no hay cifras de Solr en `reports/`.

## Qué agrega
| Pieza | Archivo |
|---|---|
| Servicio Solr 9.7 (core `rag_chunks`, `solr-precreate`) | `docker-compose.solr.yml` |
| Cliente: esquema, indexación, búsqueda BM25, estado | `app/solr_backend.py` |
| `backend: "milvus" \| "solr"` en `/retrieve` y `/ask`; bloque `solr` en `/health?deep=true` | `app/api.py` |
| Indexación de los **mismos chunks** (mismo `chunk_id`, misma limpieza) | `data/ingest_gold.py --destino solr` |
| Evaluación por motor | `data/evaluar_gold.py --backend solr`, `scripts/ejecutar_experimento_robusto.py --backend solr` |
| Demo lado a lado | `scripts/demo_rag.py` |
| Pruebas | `tests/test_solr_backend.py` |

## Diseño
- Cada chunk se guarda con `id = chunk_id`. El texto va en `text_es` (si `lang` empieza por `es`) o `text_en`,
  cada uno con su analizador (minúsculas, stopwords, stemming). La consulta usa `edismax` sobre ambos campos y el BM25
  por defecto de Solr. La consulta se limpia de caracteres especiales de Solr.
- Los fragmentos devueltos tienen la misma forma que los de Milvus, así que `/ask` reutiliza el prompt, el
  presupuesto de contexto, las citas y el registro sin cambios.
- **Abstención:** el umbral de coseno (0,80) no aplica a BM25 (puntuaciones no comparables entre consultas). Con
  Solr, `SOLR_SCORE_THRESHOLD=0` por defecto (solo se abstiene si no hay resultados). Es una limitación declarada.

## Cómo levantarlo y probarlo
```bash
# 1. Pila con Solr (un comando por línea)
docker compose -f docker-compose.yml -f docker-compose.solr.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.solr.yml ps

# 2. Indexar en Solr los mismos documentos que en Milvus (con la limpieza de relleno)
docker compose -f docker-compose.yml -f docker-compose.solr.yml exec -e PYTHONPATH=/work api \
  python data/ingest_gold.py --csv docs/gold_standard.csv --destino solr --limpiar

# 3. Verificar
curl.exe -s "http://localhost:8000/health?deep=true"        # debe traer "solr": {"ok": true, "rows": ...}

# 4. Demo: la misma pregunta con los dos motores
python scripts/demo_rag.py --demo-gold --sin-llm
python scripts/demo_rag.py --pregunta "¿En qué ciudad colombiana se realizó la COP16?" --modelo gemma2:2b

# 5. Evaluación (recuperación) de cada motor con los dos gold
python scripts/ejecutar_experimento_robusto.py --gold docs/gold_standard.csv data/gold/gold.jsonl --backend milvus --solo-retrieve --salida reports/crudos/exp_milvus.jsonl
python scripts/ejecutar_experimento_robusto.py --gold docs/gold_standard.csv data/gold/gold.jsonl --backend solr   --solo-retrieve --salida reports/crudos/exp_solr.jsonl
```
Para que la comparación sea justa, Milvus y Solr deben indexar los mismos documentos con la misma limpieza
(`ingest_gold.py --destino ambos --limpiar` lo hace en una sola pasada).

## Qué esperar (hipótesis, no resultados)
BM25 suele ser fuerte cuando la pregunta comparte palabras exactas con el texto (cifras, nombres propios) y débil con
paráfrasis o entre idiomas; el denso E5 es lo contrario. Se espera diferencia por tipo de pregunta y una complementariedad
que justificaría un híbrido (por ejemplo, fusión RRF). Esto debe confirmarse con la corrida del paso 5.
