#!/usr/bin/env bash
# Lista los article_id del subcorpus de asuntos públicos: noticias de los 5 medios
# comparables, gobiernos Duque y Petro, con al menos una etiqueta del tesauro
# (config/topics.yaml) de política, economía, seguridad, justicia o relaciones
# internacionales encontrada EN EL TITULAR. No se usan las coincidencias en la
# URL ni en la sección: las taxonomías de sección no son comparables entre medios
# (RCN no tiene sección de política ni de justicia) y meterían ese sesgo al filtro.
set -euo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESTINO="${1:-$AQUI/../news-retrieval/exports/subcorpus_publico_ids.csv}"
docker exec news-corpus-db psql -U news_corpus -d news_corpus -c "\copy (
  select distinct a.id as article_id
  from article a
  join article_topic at on at.article_id = a.id and at.matched_on = 'title'
  join topic tp on tp.id = at.topic_id
  where a.non_news_reason is null and a.title is not null
    and a.government_id in ('duque', 'petro')
    and a.source_id in ('el_tiempo', 'blu_radio', 'noticias_rcn', 'noticias_caracol', 'la_republica')
    and coalesce(tp.parent_id, tp.id) in ('politica', 'economia', 'seguridad', 'justicia', 'relaciones_internacionales')
  order by 1
) to stdout with csv header" > "$DESTINO"
echo "$(($(wc -l < "$DESTINO") - 1)) artículos → $DESTINO"
