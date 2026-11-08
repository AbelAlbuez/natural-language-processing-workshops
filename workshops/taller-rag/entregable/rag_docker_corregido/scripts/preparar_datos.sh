#!/usr/bin/env bash
# Descarga dragons_rag, verifica su integridad y genera data/documentos_rag.parquet.
# Uso: docker compose --profile prep run --rm prep
set -euo pipefail
LANGUAGES="${LANGUAGES:-es en}"
RAW=/root/.open_corpus_co_es/data/dragons_rag/dragons_rag.parquet
mkdir -p data models

echo "1/4 Descargando el corpus (si ya está descargado, se reutiliza)..."
python -c "from open_corpus_co_es.downloader import download_corpus; download_corpus('dragons_rag', force=False)"

echo "2/4 Verificando hash, filas y esquema..."
if ! python scripts/inspect_corpus.py "$RAW" > data/inspeccion_corpus.json; then
  echo "ERROR: el hash del corpus no coincide. Revise data/inspeccion_corpus.json" >&2
  exit 2
fi
python -c "import json; d=json.load(open('data/inspeccion_corpus.json')); print('   sha256_ok =', d['sha256_ok'], '| filas =', d['rows'], '| columnas =', d['cols'])"

echo "3/4 Modelo de detección de idioma (fastText lid.176.bin)..."
if [ ! -s models/lid.176.bin ]; then
  curl -fL --retry 3 -o models/lid.176.bin https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
else
  echo "   ya existe, se reutiliza"
fi

echo "4/4 Preparando el corpus (idiomas: $LANGUAGES)..."
# shellcheck disable=SC2086
python scripts/prepare_corpus.py --input "$RAW" --languages $LANGUAGES \
  --output data/documentos_rag.parquet --stats data/prepare_stats.json > /dev/null
python -c "import json; d=json.load(open('data/prepare_stats.json')); print('   filas de salida =', d['rows_output'], '| por fuente =', d['by_source'])"
echo "Listo: data/documentos_rag.parquet"
