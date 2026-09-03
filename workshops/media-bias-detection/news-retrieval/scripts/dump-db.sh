#!/usr/bin/env bash
#
# Vuelca la base a dumps/news_corpus.dump para que el equipo pueda cargar el
# corpus sin repetir la adquisición.
#
# El corpus cuesta horas de peticiones a los medios: ~17.000 páginas leídas a
# menos de 1 req/s. Reconstruirlo en cada máquina no sólo es lento, es descortés
# con unos sitios que nos están dando el archivo gratis. El dump existe para que
# se descargue una vez.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTENEDOR="${DB_CONTAINER:-news-corpus-db}"
USUARIO="${DB_USER:-news_corpus}"
BASE="${DB_NAME:-news_corpus}"
DESTINO="$RAIZ/dumps/news_corpus.dump"
MANIFIESTO="$RAIZ/dumps/MANIFEST.md"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
  echo "El contenedor '$CONTENEDOR' no está corriendo. Ejecuta: docker compose up -d" >&2
  exit 1
fi

echo "Volcando $BASE desde ${CONTENEDOR}…"
# -Fc: formato custom, comprimido y restaurable con pg_restore.
# --no-owner: el dump no fija propietario, así se restaura con cualquier rol.
docker exec "$CONTENEDOR" pg_dump -U "$USUARIO" -d "$BASE" -Fc --no-owner > "$DESTINO"

consulta() { docker exec "$CONTENEDOR" psql -U "$USUARIO" -d "$BASE" -t -A -c "$1"; }

{
  echo "# Dump del corpus"
  echo
  echo "Generado: $(date -u +'%Y-%m-%d %H:%M UTC')"
  echo "Tamaño: $(du -h "$DESTINO" | cut -f1)"
  echo "SHA-256: $(shasum -a 256 "$DESTINO" | cut -d' ' -f1)"
  echo "Esquema (alembic): $(consulta 'select version_num from alembic_version;')"
  echo
  echo "## Contenido"
  echo
  echo "| Tabla | Filas |"
  echo "|---|---|"
  for t in article discovery_record article_topic collection_chunk archive_density source government topic; do
    echo "| \`$t\` | $(consulta "select count(*) from $t;") |"
  done
  echo
  echo "## Corpus"
  echo
  echo "| Medio | Artículos | Con cuerpo | Cuerpo ≥500 car. |"
  echo "|---|---|---|---|"
  consulta "select '| '||source_id||' | '||count(*)||' | '||count(content)||' | '||
            count(*) filter (where length(content) >= 500)||' |'
            from article group by source_id order by count(*) desc;"
  echo
  echo "Restaurar: \`./scripts/restore-db.sh\` — ver \`docs/03-guia-del-equipo.md\`."
} > "$MANIFIESTO"

echo "✓ $DESTINO ($(du -h "$DESTINO" | cut -f1))"
echo "✓ $MANIFIESTO"
