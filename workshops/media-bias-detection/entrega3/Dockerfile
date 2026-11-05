# La imagen base de la Entrega 2 (news-duque-cli:kelly) ya no existe; esta es
# autocontenida. Versiones fijas para que el LDA sea reproducible.
FROM python:3.12-slim
WORKDIR /analysis
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 180 --retries 10 --progress-bar off -r requirements.txt \
 && python -m nltk.downloader -d /usr/share/nltk_data stopwords
ENV PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
