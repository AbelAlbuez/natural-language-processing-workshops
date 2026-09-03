#!/usr/bin/env bash
#
# Carga dumps/news_corpus.dump en el Postgres local.
#
# Es la vía normal para tener el corpus: no hay que ejecutar `collect` ni
# `extract`. Al terminar, `news-corpus profile` debe dar las mismas cifras que
# dumps/MANIFEST.md.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTENEDOR="${DB_CONTAINER:-news-corpus-db}"
USUARIO="${DB_USER:-news_corpus}"
BASE="${DB_NAME:-news_corpus}"
ORIGEN="${1:-$RAIZ/dumps/news_corpus.dump}"

[ -f "$ORIGEN" ] || { echo "No existe el dump: $ORIGEN" >&2; exit 1; }

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
  echo "El contenedor '$CONTENEDOR' no está corriendo. Ejecuta: docker compose up -d" >&2
  exit 1
fi

echo "Esperando a que Postgres acepte conexiones…"
n=0
until docker exec "$CONTENEDOR" pg_isready -U "$USUARIO" -d "$BASE" >/dev/null 2>&1; do
  n=$((n+1)); [ $n -ge 60 ] && { echo "Postgres no respondió en 60 s" >&2; exit 1; }
  sleep 1
done

# --clean --if-exists: deja la base como está en el dump aunque ya hubiera
# tablas. Sin --if-exists, restaurar sobre una base vacía falla al intentar
# borrar tablas que no existen.
echo "Restaurando en ${BASE}…"
docker exec -i "$CONTENEDOR" pg_restore \
  --clean --if-exists --no-owner --no-privileges \
  -U "$USUARIO" -d "$BASE" < "$ORIGEN"

echo
echo "✓ Restaurado. Comprobación:"
docker exec "$CONTENEDOR" psql -U "$USUARIO" -d "$BASE" -c "
  select source_id as medio,
         count(*)  as articulos,
         count(content) as con_cuerpo,
         count(*) filter (where length(content) >= 500) as analizable
  from article group by 1 order by 2 desc;"
echo "Compara con dumps/MANIFEST.md. Si cuadra, ya tienes el corpus."
