# Dump del corpus procesado — 2026-11-05

Archivo: `news_corpus_procesado_2026-11-05.dump` (Git LFS)
Tamaño:  435 MB
SHA-256: 13428cb588e59ba770eb7a8fc4a49328f87ef14f64be7171bbada160922ce5ce
Esquema (alembic): 7b3f9c1d2e40

Es el corpus unificado del 2026-10-04 después del tratamiento del slug
(`news-corpus enrich --all` y `tag --retag`): titulares y secciones derivados
de la URL y la marca `non_news_reason`. Contiene todo lo del dump del
2026-10-04, así que no hace falta cargar ese antes. Proceso completo en
[`docs/07-tratamiento-del-slug.md`](../docs/07-tratamiento-del-slug.md).

Se verificó restaurándolo en una base vacía: mismos conteos que la base de
origen.

## Contenido

| Tabla | Filas |
|---|---:|
| `article` | 1.733.421 |
| `discovery_record` | 1.733.854 |
| `article_topic` | 645.730 |
| `collection_chunk` | 549 |
| `topic` | 42 |
| `source` | 10 |
| `government` | 5 |

## Corpus

| Medio | URLs | Con titular | No-noticia | Analizables* |
|---|---:|---:|---:|---:|
| El Tiempo | 683.173 | 682.535 | 16.130 | 666.406 |
| Blu Radio | 382.333 | 381.386 | 38.848 | 342.538 |
| Noticias RCN | 211.309 | 211.301 | 12.300 | 199.001 |
| Noticias Caracol | 210.606 | 210.184 | 9.475 | 200.709 |
| La República | 200.589 | 200.310 | 1.774 | 198.536 |
| Cambio | 44.575 | 44.473 | 321 | 44.152 |
| El Espectador | 835 | 814 | 11 | 803 |
| Semana | 1 | 0 | 0 | 0 |
| **Total** | **1.733.421** | **1.731.003** | **78.859** | **1.652.145** |

\* Con titular y `non_news_reason IS NULL`.

## Restaurar

```bash
git lfs pull --include "workshops/media-bias-detection/news-retrieval/dumps/news_corpus_procesado_2026-11-05.dump"
./scripts/restore-db.sh dumps/news_corpus_procesado_2026-11-05.dump
```

El restore usa `--clean --if-exists`: reemplaza la base local entera.
