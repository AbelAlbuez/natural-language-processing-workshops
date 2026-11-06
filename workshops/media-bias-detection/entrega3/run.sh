#!/usr/bin/env bash
# Corre una etapa del análisis de tópicos dentro de Docker.
#   ./run.sh <etapa> [args de topics.py]        etapa: prepare | train | ensemble | stability | infer |
#                                                      examples | robustness | compare | all
#   SCRIPT=bertopic_topics.py IMAGEN=duque-petro-bertopic:local ./run.sh - --output resultados_publico
# Antes: docker build -t duque-petro-lda:local . (y -f Dockerfile.bertopic para BERTopic) y el export:
#   news-corpus export -o exports/duque-petro.parquet --from 2018-08-01 --to 2026-08-31 --no-content
set -euo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$AQUI/.." && pwd)"
CORPUS="${CORPUS:-$ROOT/news-retrieval/exports/duque-petro.parquet}"
IMAGEN="${IMAGEN:-duque-petro-lda:local}"
SCRIPT="${SCRIPT:-topics.py}"
ETAPA="${1:-all}"; shift || true
ARGS=("$@")
[ "$SCRIPT" = "topics.py" ] && ARGS=(--input /data/duque-petro.parquet --stage "$ETAPA" "${ARGS[@]}")
docker run --rm --network none --user "$(id -u):$(id -g)" --shm-size=2g \
  -v "$ROOT:/workspace" -v "$CORPUS:/data/duque-petro.parquet:ro" \
  -w /workspace/entrega3 -e PYTHONPATH=/workspace/entrega3:/workspace/entrega2 \
  "$IMAGEN" python "$SCRIPT" "${ARGS[@]}"
