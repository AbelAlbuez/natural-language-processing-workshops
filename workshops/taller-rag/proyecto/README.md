# Taller de RAG con Milvus: repositorio demostrativo

Este repositorio forma parte del taller de generación aumentada por recuperación (RAG) de la Pontificia Universidad Javeriana. Es el punto de partida para las actividades prácticas de ingesta, recuperación, generación y evaluación del taller.

**Proyecto base académico (scaffold), no solución terminada ni rendimiento certificado.** Únicamente Milvus; frontend Streamlit; FastAPI; Ollama local; Python y Docker Compose. Se deben descargar imágenes y pesos de modelos gratuitos, sin API de pago. Por compatibilidad, verificar imágenes disponibles y licencias de cada modelo antes de la clase.

## Requisitos

Python 3.11 o superior y Docker Desktop. Se recomiendan al menos 16 GB de RAM para la pila completa; el requisito puede ser mayor según el hardware, los modelos y la escala. Docker Compose incluye Milvus, etcd, MinIO, Ollama, API y frontend.

Ollama no requiere instalación local si se usa el servicio `ollama` de Compose. Para una instancia externa, la aplicación lee `OLLAMA_URL`.

## Instalación local

Este entorno sirve para instalar dependencias y preparar o inspeccionar datos. La ejecución completa del taller se realiza con Docker Compose.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`fasttext-numpy2` puede compilarse desde código fuente durante la instalación y ese paso puede tardar.

## Corpus

Descarga el conjunto `dragons_rag` con el comando Python de `open_corpus_co_es`:

```bash
python -c "from open_corpus_co_es import download_corpus; download_corpus('dragons_rag', force=False)"
```

El conjunto requerido es `dragons_rag`, no `dragons_rag_2026_10_19`. Verifica el SHA-256 esperado: `f4a669f17eaedd357f72b70c2192e685b6d534a94f6ffaeadbced7290b181728`. El descargador valida el archivo; para una inspección explícita, pasa la ruta como primer argumento posicional:

```bash
python scripts/inspect_corpus.py <ruta-relativa-al-parquet>
```

El JSON incluye `sha256_ok`; debe ser `true`. Si el hash no coincide, el script termina con código 2.

Prepara español e inglés con:

```bash
python scripts/prepare_corpus.py --languages es en
```

La salida es `data/documentos_rag.parquet`. Con el corpus verificado se esperan 146.923 filas. El script usa por defecto la copia de `dragons_rag` gestionada por `open_corpus_co_es`.

Si hay registros sin idioma informado, se requiere el modelo `models/lid.176.bin`. Este archivo no se versiona.

## Ejecución completa

1. `cp .env.example .env`.
2. `docker compose up -d --build`.
3. `docker compose exec ollama ollama pull qwen2.5:1.5b`.
4. `docker compose exec api python -m scripts.ingest --input data/documentos_rag.parquet --limit 500`.
5. Abre http://localhost:8501; la documentación de la API está en http://localhost:8000/docs.
6. Comparadores opcionales: `llama3.2:1b`, `llama3.2:3b` y `gemma2:2b` mediante el servicio Ollama.

**Importante:** los ejemplos son candidatos sujetos a licencias/recursos disponibles. El prefijo `query:` / `passage:` se usa porque el modelo de embeddings predeterminado es E5. Al cambiar encoder se debe cambiar nombre de colección, rehacer embeddings y validar dimensión/política de prefijos.

## Colecciones

La colección activa es `rag_e5s_tok256_v1`. `rag_e5s_sent256_v1` es una alternativa pendiente, no activa.

## Endpoints

- `GET /health`: disponibilidad de API (no prueba dependencia).
- `POST /retrieve`: chunks recuperados.
- `POST /ask`: respuesta, modelo, evidencia y latencia. JSON `{"query":"¿Qué señalan los documentos?","model":"qwen2.5:1.5b","k":5}`.

## Diseño y limitaciones deliberadas

- Esqueleto funcional en condiciones compatibles, **no ejecutado end-to-end en este entorno**.
- Chunking inicial por caracteres con solapamiento; estudiantes deben investigar tokenizer, límites, distribución y compararlo con chunking semántico.
- Indexación piloto idempotente por `chunk_id` con `upsert`; falta checkpoint robusto de procesamiento, reintentos y control de lotes grandes.
- Modelo de embedding fijo para comparar generadores sin sesgo de recuperación. Para ablations de embedding, colecciones separadas.
- Metadatos base y offsets; estudiantes ampliarán filtros, control de calidad, deduplicación, reranking, instrumentación y seguridad.
- Se guarda texto en Milvus por simplicidad educativa; evaluar limites y almacenamiento alterno para producción.
- **No publicar documentos ni datos personales** en GitHub: publicar código, instrucciones, muestras autorizadas y artefactos no sensibles.
- El corpus incluye publicaciones sociales y noticias: distinguir alegaciones, atribuciones y evidencia; no equiparar cobertura con veracidad.

## Entregas

Entregar instrucciones desde cero, matriz de experimentos, benchmark, informe, demo y registro de equipo/hardware.

## Reproducibilidad

Fijar versiones y digests de imágenes finales; registrar SHA-256 del Parquet, semilla, nombres/versiones/hashes de modelos, hardware, cuantización, parámetros de inferencia, tamaños de chunk, k, tiempos por etapa, subconjunto y selección aleatoria estratificada. La aplicación no descarga el Parquet automáticamente ni provee gold estándar.

## Archivos no versionados

No se versionan `data/` ni `*.parquet` porque son datos locales voluminosos y pueden contener texto sujeto a restricciones de uso. `models/` y `*.bin` son modelos binarios descargables. `.env` puede contener configuración local o secretos; `.venv/`, `__pycache__/` y `.pytest_cache/` son artefactos generados. Los volúmenes y reportes generados permanecen locales. `.env.example` contiene valores de ejemplo y sí se versiona.

## Contacto

- **Luis Gabriel Moreno Sandoval**
- Pontificia Universidad Javeriana
- Correo institucional: [morenoluis@javeriana.edu.co](mailto:morenoluis@javeriana.edu.co)
