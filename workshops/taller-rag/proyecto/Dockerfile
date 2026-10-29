# Imagen de la API y del frontend. No incluye las herramientas de preparación del corpus
# (fasttext, open_corpus_co_es): esas van en Dockerfile.prep.
FROM python:3.11-slim
WORKDIR /work
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# PyTorch solo CPU: evita descargar ~2 GB de librerías CUDA que aquí no se usan.
# El índice de PyTorch CPU tiene versiones para Intel/AMD (x86_64) y para Apple Silicon (arm64).
# Si el índice de PyTorch no responde, se usa la versión normal de PyPI (más pesada, pero funciona).
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.4,<3" \
 || pip install "torch>=2.4,<3"
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt
COPY app/ app/
COPY scripts/ scripts/
COPY tests/ tests/
