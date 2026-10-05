#!/usr/bin/env bash
#
# Amplía el corpus a la ventana comparable (gobierno Petro, 2022-08 → 2026-07).
# Requisitos: Postgres arriba (docker compose up -d), dump restaurado y el
# entorno virtual activado con el paquete instalado. Ver INICIO_RAPIDO.md.
#
# Es reanudable: si se corta, volver a ejecutarlo no repite los meses ya hechos.
set -euo pipefail

DESDE="${1:-2022-08}"
HASTA="${2:-2026-07}"

echo "== 1/6 Alcance de los feeds nuevos (no escribe en la base)"
news-corpus probe --from "$DESDE"

echo
read -r -p "¿Continuar con la recolección $DESDE → $HASTA? [s/N] " ok
[[ "$ok" =~ ^[sS]$ ]] || { echo "Cancelado."; exit 0; }

echo "== 2/6 Recolección (discovery de URLs y titulares)"
news-corpus collect --from "$DESDE" --to "$HASTA"

echo "== 3/6 Reintento de bloques fallidos"
news-corpus retry-failed || true

echo "== 4/6 Titulares desde la URL para lo que no trajo news:title"
news-corpus enrich

echo "== 5/6 Etiquetado temático"
news-corpus tag

echo "== 6/6 Perfil del corpus"
news-corpus status
news-corpus profile

echo
echo "Listo. Para guardar el corpus ampliado: ./scripts/dump-db.sh"
