#!/usr/bin/env bash
# Corre una etapa del LDA Duque + Petro dentro de la imagen duque-petro-lda:local.
#   ./run.sh prepare | train | stability | infer | examples | compare | all  [más args de topics.py]
# Antes: docker build -t duque-petro-lda:local . y el export de news-retrieval:
#   news-corpus export -o exports/duque-petro.parquet --from 2018-08-01 --to 2026-08-31 --no-content
set -euo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$AQUI/.." && pwd)"
CORPUS="${CORPUS:-$ROOT/news-retrieval/exports/duque-petro.parquet}"
ETAPA="${1:-all}"; shift || true
docker run --rm --network none --user "$(id -u):$(id -g)" --shm-size=2g \
  -v "$ROOT:/workspace" -v "$CORPUS:/data/duque-petro.parquet:ro" \
  -w /workspace/entrega3 -e PYTHONPATH=/workspace/entrega3:/workspace/entrega2 \
  duque-petro-lda:local python topics.py --input /data/duque-petro.parquet --stage "$ETAPA" "$@"
