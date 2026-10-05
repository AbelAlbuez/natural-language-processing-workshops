FROM news-duque-cli:kelly
USER root
WORKDIR /analysis
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_NO_CACHE_DIR=0 pip install --timeout 180 --retries 10 \
        --progress-bar off -r requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
USER nb