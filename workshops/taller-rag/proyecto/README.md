# Taller de RAG con Milvus y LLM locales

## 1. Qué es

Un asistente de generación aumentada por recuperación (RAG) sobre noticias y publicaciones de Bluesky en español e inglés, que recupera fragmentos con E5 y Milvus y responde con citas usando LLM locales servidos por Ollama. El proyecto **compara cuatro modelos locales** (`gemma2:2b`, `qwen2.5:1.5b`, `llama3.2:1b` y `llama3.2:3b`) con la misma recuperación, el mismo prompt y la misma configuración, sobre un gold standard dividido en desarrollo y prueba.

Forma parte del taller de RAG de la Pontificia Universidad Javeriana. Es un proyecto académico, no una solución de producción.

## 2. Requisitos

| Componente | Valor |
|---|---|
| Python | 3.12 (el entorno de referencia usa 3.12.14) |
| Docker Desktop | Con al menos **16 GB** asignados a Docker. En el equipo de referencia se usaron 33 GB. |
| Memoria del equipo | 48 GB de RAM en la máquina de referencia |
| Aceleración | Solo CPU (no hace falta GPU) |
| Milvus | `milvusdb/milvus:v2.6.25`, standalone con etcd embebido y almacenamiento local, sin MinIO |
| Ollama | `ollama/ollama:0.40.13` |

Las versiones de las imágenes están fijadas en `docker-compose.yml` y se pueden cambiar con `MILVUS_VERSION` y `OLLAMA_VERSION` en `.env`.

Milvus necesita al menos 8 GiB de límite (`MILVUS_MEM=8g`) para la colección completa: con 4 GiB se detiene por falta de memoria al recargar 577.324 chunks.

## 3. Instalación

Todos los comandos se ejecutan desde `workshops/taller-rag/proyecto/`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt        # preparación, embeddings, ingesta, pruebas
pip install -r requirements-dev.txt    # opcional: notebook y figuras (matplotlib, Jupyter)
cp .env.example .env
```

`requirements-api.txt` es el subconjunto que usan los contenedores de la API y la interfaz; no hace falta instalarlo a mano. `fasttext-numpy2` puede compilarse desde código fuente y tardar.

Variables de `.env` (los valores de ejemplo están en `.env.example`; no subas tu `.env` al repositorio):

| Variable | Para qué sirve |
|---|---|
| `MILVUS_URI` | Dirección de Milvus vista desde los contenedores |
| `MILVUS_COLLECTION` | Nombre de la colección (`rag_e5s_tok256_v1`) |
| `EMBEDDING_MODEL` | Encoder de embeddings |
| `OLLAMA_URL` | Dirección de Ollama vista desde los contenedores |
| `LLM_MODEL` | Modelo por defecto de `/ask` |
| `LLM_MODELS` | Lista de modelos que la API acepta y la interfaz ofrece |
| `MAX_CONTEXT_CHARS` | Límite heredado de la versión inicial de la API |
| `RAG_TOP_K` | Fragmentos recuperados por pregunta |
| `RAG_SCORE_THRESHOLD` | Umbral de abstención (ver §8) |
| `RAG_MAX_CONTEXT_TOKENS` | Presupuesto de contexto, en tokens de E5 |
| `RAG_RUN_LOG` | Registro JSONL de cada corrida de `/ask` |
| `MILVUS_VERSION`, `OLLAMA_VERSION` | Versiones de las imágenes |
| `MILVUS_CPUS`, `MILVUS_MEM`, `OLLAMA_CPUS`, `OLLAMA_MEM`, `API_CPUS`, `API_MEM` | Límites de CPU y memoria por contenedor |
| `OLLAMA_KEEP_ALIVE` | Tiempo que Ollama mantiene un modelo cargado |
| `LANGUAGES` | Idiomas que conserva la preparación del corpus |
| `MILVUS_HOST`, `MILVUS_PORT`, `OLLAMA_HOST`, `CORPUS_PATH`, `TOP_K` | Para scripts locales fuera de Docker |

## 4. Datos

El corpus es el conjunto `dragons_rag` del paquete `open_corpus_co_es==0.1.1a4`. **Los datos no se versionan**: `data/` está ignorado por git, igual que `*.parquet`, `models/` y `reports/*.jsonl`.

```bash
python -c "from open_corpus_co_es import download_corpus; download_corpus('dragons_rag', force=False)"
```

El conjunto correcto es `dragons_rag`, no `dragons_rag_2026_10_19`. El SHA-256 esperado es `f4a669f17eaedd357f72b70c2192e685b6d534a94f6ffaeadbced7290b181728`. El descargador lo valida; para comprobarlo a mano, pasa la ruta del Parquet descargado:

```bash
python scripts/inspect_corpus.py <ruta-al-parquet-descargado>   # el JSON debe tener "sha256_ok": true
```

## 5. Reproducción paso a paso

| # | Paso | Comando | Duración observada |
|---|---|---|---|
| 1 | Preparar el corpus (español e inglés; requiere `models/lid.176.bin`) | `python scripts/prepare_corpus.py --languages es en --stats data/prepare_stats.json` | — |
| 1b | Alternativa en Docker: descarga, verifica y prepara | `docker compose --profile prep run --rm prep` | 10–30 min |
| 2 | Chunking por tokens 256/48 → `data/chunks_tok256.parquet` (577.324 chunks) | `python scripts/chunk_corpus.py --write` | — |
| 3 | Embeddings E5 del corpus completo, en bloques reanudables de 20.000 | `python -m scripts.embed_chunks --all` | ≈ 1 h 53 min en CPU |
| 4 | Levantar Milvus y Ollama | `docker compose up -d milvus ollama` | < 1 min |
| 5 | Carga en Milvus por lotes, idempotente | `MILVUS_URI=http://localhost:19530 python -m scripts.ingest_milvus --embeddings data/embeddings_corpus_completo.parquet` | ≈ 2 min |
| 6 | Descargar los cuatro modelos | `docker compose exec ollama ollama pull gemma2:2b` (y `qwen2.5:1.5b`, `llama3.2:1b`, `llama3.2:3b`) | ≈ 1 min cada uno |
| 7 | Pruebas sin servicios | ver §7 | segundos |
| 8 | API e interfaz | `docker compose up -d --build api frontend` | 1–2 min |
| 9 | Prueba de humo de la API | `python -m scripts.smoke_api` | ≈ 2 min |
| 10 | Validar el gold standard | `python -m scripts.validar_gold_standard --gold docs/gold_standard.csv --cuotas docs/cuotas_gold.json` | segundos |
| 11 | Experimento sobre la partición de prueba (4 modelos × 20 preguntas) | **Pendiente:** el script del experimento no está en el repositorio (ver más abajo) | ≈ 34 min |
| 12 | Análisis de resultados | `python -m scripts.analisis_resultados --runs data/experimento_prueba.jsonl --gold docs/gold_standard.csv --salida data/resultados_prueba.json` | segundos |
| 13 | Figuras del informe (opcional) | `python scripts/figuras_informe.py` o, solo la del gold, `python scripts/figuras_informe.py --solo-gold` | — |

Notas:
- El paso 1 escribe sus cifras en `data/` (no versionado). `docs/prepare_stats_es_en.json` es la copia de referencia versionada, con la ruta de entrada expresada como `~/`. No la sobrescribas, porque el script guarda la ruta absoluta de tu equipo.
- En el paso 5, `MILVUS_URI` se fija en la línea de comandos porque el script corre fuera de Docker; dentro de los contenedores se usa el valor de `.env`.
- El paso 3 reanuda desde el último bloque escrito si se interrumpe. Para el piloto de 500 documentos existe `python -m scripts.embed_chunks --documents data/piloto_documentos_500.parquet --output data/embeddings_piloto_500.parquet`, pero el script que generó `data/piloto_documentos_500.parquet` no está en el repositorio.
- **Pendientes de versionar:** el experimento del paso 11, la calibración del umbral con la partición de desarrollo y la construcción de `docs/gold_standard.csv` se ejecutaron con scripts locales que no forman parte del repositorio. El formato que espera el paso 12 está documentado en `scripts/analisis_resultados.py`.

## 6. Servicios

```bash
docker compose up -d --build     # milvus, ollama, api y frontend
docker compose ps                # los cuatro deben aparecer como "healthy"
```

| Servicio | Puerto | Cómo verificarlo |
|---|---|---|
| API (FastAPI) | 8000 | `curl http://localhost:8000/health` y `curl "http://localhost:8000/health?deep=true"` (filas de Milvus con `count(*)` y modelos de Ollama). Documentación en `http://localhost:8000/docs`. |
| Interfaz (Streamlit, `app/ui.py`) | 8501 | `http://localhost:8501` en el navegador. **No se ha verificado en ejecución.** |
| Milvus | 19530 (gRPC) y 9091 (salud) | `curl http://localhost:9091/healthz` |
| Ollama | 11434 | `docker compose exec ollama ollama list` |

Endpoints de la API:
- `GET /health`: la API está viva; con `?deep=true` revisa Milvus y Ollama.
- `POST /retrieve`: `{"question": "...", "k": 5}` → fragmentos con `score`, `document_id`, `source`, `url` y `text`.
- `POST /ask`: `{"question": "...", "model": "gemma2:2b", "k": 5}` → respuesta, citas, abstención, tiempos y parámetros. Responde 400 si el modelo no está permitido, 503 si Milvus u Ollama no responden, y 502 si Ollama corta la generación por repetición.

Para equipos con GPU NVIDIA existe `docker-compose.gpu.yml`; en Mac no aplica. `GUIA_EJECUCION.md` tiene una guía paso a paso para principiantes.

## 7. Pruebas

`pytest.ini` añade la carpeta del proyecto al `pythonpath`, así que basta con `.venv/bin/pytest`.

| Suite | Comando | Resultado esperado |
|---|---|---|
| Contrato (RAG, API, esquema, `repeat_penalty`) | `.venv/bin/pytest tests/test_rag_contract.py` | 21 passed |
| Ingesta por lotes | `.venv/bin/pytest tests/test_ingesta_lotes.py` | 3 passed |
| Validador del gold standard | `.venv/bin/pytest tests/test_validar_gold.py` | 14 passed |
| Métricas | `.venv/bin/pytest tests/test_metricas_rag.py` | 5 passed |
| Análisis de resultados | `.venv/bin/pytest tests/test_analisis_resultados.py` | 5 passed |
| Chunking inicial por caracteres (legado) | `.venv/bin/pytest tests/test_chunking.py` | 1 passed |
| En vivo (necesita API, Milvus y Ollama) | `RAG_LIVE=1 .venv/bin/pytest tests/test_api_live.py -v` | sin `RAG_LIVE`, 10 skipped |

En la última corrida en vivo con la colección completa, el resultado fue 6 passed, 3 skipped y 1 xfailed. Las 3 omitidas leen preguntas de `docs/gold_standard_plantilla.csv`, que está vacía. La marcada como xfail es la abstención ante texto sin sentido, pendiente de calibración del umbral.

## 8. Configuración congelada

Resumen de la sección 9 de `docs/protocolo_evaluacion.md`, que es la referencia:

- Los cuatro modelos en Ollama 0.40.13, con su ID local registrado.
- `prompt_v1` versión 1.0.0, identificado por su sha256.
- Temperatura 0 y `repeat_penalty` 1,1, iguales para todos los modelos.
- `top-k` 5 y presupuesto de contexto de 2.048 tokens de E5, por fragmento completo.
- Chunks de 256 tokens con solapamiento de 48.
- Encoder `intfloat/multilingual-e5-small` en una revisión fija, con prefijos `query:` y `passage:` y normalización L2.
- Índice HNSW (M 16, efConstruction 200, ef 64) con métrica IP en Milvus v2.6.25.
- Umbral de abstención 0,80, mantenido por decisión del autor y pendiente de calibración con anotaciones humanas.
- Partición 20/20 con semilla 42.

## 9. Resultados preliminares

Las tablas de recuperación y generación, el análisis de la calibración y las conclusiones están en `../latex/informe.pdf` (sección "Resultados preliminares"). Las métricas en bruto, con solo conteos, quedan en `data/resultados_prueba.json`, que se genera con el paso 12 y no se versiona.

## 10. Limitaciones

- El gold standard es **sintético** (34 respondibles basadas en un único chunk cada una y 6 no respondibles) y **no tiene validación humana**.
- Hay **una sola repetición** por modelo, sin intervalos de confianza.
- El umbral de abstención de **0,80 no está calibrado con anotaciones humanas**. Con él, el sistema no se abstiene en las preguntas fuera del corpus, y la calibración con desarrollo no encontró un valor que cumpla los dos criterios.
- `gemma2:2b` tuvo **un error en G34**: el proceso `llama-server` de Ollama recibió SIGKILL. No se reintentó y cuenta como fallo.
- `qwen2.5:1.5b` **casi no cita**: incluye citas válidas en pocas respuestas.
- El tema (`collection_keyword_label`) solo existe en Bluesky.
- "Cita válida" solo comprueba que la cita apunta a un fragmento entregado al modelo, no que lo respalde. La corrección de las respuestas no se evaluó.
- **No publiques documentos ni datos personales**: el corpus incluye publicaciones sociales y noticias. Distingue alegaciones, atribuciones y evidencia, y no confundas cobertura con veracidad.

## 11. Estructura

| Carpeta o archivo | Contenido |
|---|---|
| `app/` | API FastAPI (`api.py`), orquestación RAG (`rag.py`), esquema de Milvus (`milvus_schema.py`), interfaz Streamlit (`ui.py`) y código de la versión inicial (`core.py`, `frontend.py`) |
| `scripts/` | Preparación, chunking, embeddings, ingesta, validación del gold, métricas, análisis, prueba de humo y figuras |
| `tests/` | Pruebas de contrato, ingesta, validador, métricas, análisis y pruebas en vivo |
| `docs/` | Protocolo de evaluación, gold standard (`gold_standard.csv`, `cuotas_gold.json`, `temas_gold.json`), diagnóstico del corpus, diseño de chunking y propuestas de investigación |
| `config/` | Configuración de Milvus (etcd embebido) |
| `notebooks/` | Análisis exploratorio del corpus (se versiona sin salidas; ejecutar `nbstripout` antes de cada commit) |
| `data/`, `models/`, `reports/` | Datos, modelos y registros locales (no se versionan) |
| `rag_docker_corregido/` | Copia histórica de la configuración Docker corregida |
| `docker-compose.yml`, `Dockerfile`, `Dockerfile.prep` | Servicios y contenedores |
| `../latex/` | Informe (`informe.tex`, `informe.pdf`) y figuras |

## 12. Hardware de referencia y tiempos observados

Equipo de referencia: Apple M5 Pro (arm64) con 18 núcleos y 48 GB de RAM, Docker Desktop con 33 GB y 18 CPU, todo en CPU.

| Etapa | Tiempo observado |
|---|---|
| Embeddings del piloto (1.904 chunks) | 22,4 s |
| Embeddings del corpus completo (577.324 chunks) | ≈ 1 h 53 min, compartiendo CPU con los contenedores |
| Carga completa en Milvus por lotes | 115 s (2,41 GB de memoria máxima del proceso) |
| Experimento de 80 corridas (4 modelos × 20 preguntas de prueba) | ≈ 34 min |

## Documentos de diseño

- `docs/protocolo_evaluacion.md`: gold standard, partición, métricas y configuración congelada.
- `docs/diagnostico_corpus.md`: integridad, esquema y preparación del corpus.
- `docs/diseno_chunking.md`: tokenizador, estrategias de chunking, offsets e ID estable.
- `docs/propuestas_investigacion.md`: preguntas de investigación y estado del arte (referencias por verificar).
- `docs/EVALUACION.md`: requisitos de evaluación del taller.

## Contacto

- **Luis Gabriel Moreno Sandoval**
- Pontificia Universidad Javeriana
- Correo institucional: [morenoluis@javeriana.edu.co](mailto:morenoluis@javeriana.edu.co)
