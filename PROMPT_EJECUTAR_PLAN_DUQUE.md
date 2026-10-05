# PROMPT: Implementar Plan Duque (Basado en Análisis de Kelly)

## CONTEXTO
Tengo un análisis completo de Kelly que propone un plan para enriquecer el período Duque (2018-2022) reutilizando su pipeline. El plan está documentado en 8 pasos con comandos bash exactos.

## SITUACIÓN ACTUAL
- **Dump unificado**: 1.7M artículos (2013-2026), 8 medios
- **Período Duque**: 708.768 artículos (2018-08-07 a 2022-08-07 semiabierto)
- **Títulos Duque**: Solo 110 (todos de Cambio, tipo SLUG)
- **Problema**: Faltan títulos derivados + extracción HTML

## PLAN DE KELLY (Sección 7)

### 7.1 Preparar herramientas sin cambiar la conexión original

```bash
set -euo pipefail
KELLY="/Users/abelalbuez/Documents/Maestria/Cuarto Semestre/PLN/natural-language-processing-workshops/workshops/media-bias-detection/news-retrieval/dumps/kelly/natural-language-processing-workshops-corpus-v2/workshops/media-bias-detection/news-retrieval"
PG=news-corpus-unificado
WORK_DB=news_duque_work
cd "$KELLY"
docker exec "$PG" pg_isready -h 127.0.0.1 -U postgres -d news_corpus
docker build -t news-duque-cli:kelly -f Dockerfile.jupyter .

printf 'Clave PostgreSQL local (no se mostrará): '
IFS= read -r -s DB_PASSWORD
printf '\n'
export DB_PASSWORD

kelly() {
  docker run --rm --network "container:$PG" \
    --user "$(id -u):$(id -g)" \
    -v "$KELLY:/workspace" -w /workspace \
    -e DB_HOST=127.0.0.1 -e DB_PORT=5432 \
    -e DB_USER=postgres -e DB_PASSWORD -e DB_NAME="$WORK_DB" \
    -e LOG_FORMAT=json \
    news-duque-cli:kelly "$@"
}

kelly news-corpus catalog check
kelly news-corpus collect --help
kelly news-corpus extract --help
kelly news-corpus export --help
kelly pytest -q tests/test_dates.py tests/test_enrich_and_tagging.py tests/test_extraction.py tests/test_export_columns.py
```

**¿Qué hace?**
- Construye imagen Docker con todas las dependencias
- Verifica conexión a PostgreSQL
- Ejecuta tests básicos
- NO modifica nada, solo setup

---

### 7.2 Crear DB aislada y copiar esquema/catálogos

```bash
docker exec "$PG" createdb -U postgres "$WORK_DB"
docker exec "$PG" pg_dump -U postgres -d news_corpus \
  --schema-only --no-owner --no-privileges |
  docker exec -i "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$WORK_DB"

docker exec "$PG" pg_dump -U postgres -d news_corpus \
  --data-only --no-owner --no-privileges \
  -t public.source -t public.source_domain -t public.government \
  -t public.topic -t public.alembic_version |
  docker exec -i "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$WORK_DB"
```

**¿Qué hace?**
- Crea DB nueva: `news_duque_work`
- Copia esquema (tablas, índices)
- Copia catálogos (medios, gobiernos, temas)
- **NO toca el original** (`news_corpus`)

---

### 7.3 Sembrar candidatos Duque sin peticiones HTTP

```bash
copy_rows() {
  local table_name="$1" query="$2"
  docker exec "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d news_corpus \
    -c "\copy ($query) TO STDOUT WITH (FORMAT csv)" |
    docker exec -i "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$WORK_DB" \
      -c "\copy $table_name FROM STDIN WITH (FORMAT csv)"
}

WINDOW="published_date >= DATE '2018-08-01' AND published_date < DATE '2022-09-01'"
CHUNKS="period_start >= DATE '2018-08-01' AND period_start < DATE '2022-09-01'"

copy_rows collection_chunk "SELECT * FROM collection_chunk WHERE $CHUNKS"
copy_rows archive_density "SELECT * FROM archive_density WHERE $CHUNKS"
copy_rows article "SELECT * FROM article WHERE $WINDOW"
copy_rows discovery_record "SELECT d.* FROM discovery_record d JOIN collection_chunk c ON c.id=d.chunk_id WHERE c.period_start >= DATE '2018-08-01' AND c.period_start < DATE '2022-09-01' AND (d.article_id IS NULL OR EXISTS (SELECT 1 FROM article a WHERE a.id=d.article_id AND a.published_date >= DATE '2018-08-01' AND a.published_date < DATE '2022-09-01'))"
copy_rows article_topic "SELECT t.* FROM article_topic t JOIN article a ON a.id=t.article_id WHERE a.published_date >= DATE '2018-08-01' AND a.published_date < DATE '2022-09-01'"

docker exec "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$WORK_DB" \
  -c "SELECT setval(pg_get_serial_sequence('article','id'), COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM article;" \
  -c "SELECT setval(pg_get_serial_sequence('collection_chunk','id'), COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM collection_chunk;" \
  -c "SELECT setval(pg_get_serial_sequence('discovery_record','id'), COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM discovery_record;"

kelly news-corpus status
kelly news-corpus profile
```

**¿Qué hace?**
- Copia artículos Duque: 708k+
- Copia metadatos relacionados
- Ajusta secuencias de ID
- **Período: agosto 2018 - agosto 2022 (semiabierto)**

---

### 7.4 Enriquecer sin red y medir ganancia

```bash
kelly news-corpus enrich
kelly news-corpus profile
docker exec "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$WORK_DB" -c "
SELECT source_id, count(*) AS candidatos,
       count(*) FILTER (WHERE title IS NULL) AS sin_titulo,
       count(*) FILTER (WHERE title_source='slug') AS slug,
       count(*) FILTER (WHERE title_source='sitemap') AS sitemap,
       count(*) FILTER (WHERE title_source='extracted') AS extracted
FROM article GROUP BY source_id ORDER BY candidatos DESC;"
```

**¿Qué hace?**
- Ejecuta `enrich` → Deriva títulos de URLs (sin red)
- Mide ganancia: ¿Cuántos NULL→SLUG?
- Reporta por medio
- **Si falla**: Revisar URLs no derivables antes de modificar

---

### 7.5 Discovery adicional solo si hay huecos (OPCIONAL)

```bash
kelly news-corpus collect \
  -s el_tiempo -s noticias_caracol -s blu_radio \
  -s la_republica -s noticias_rcn \
  --from 2018-08 --to 2022-08 --dry-run

kelly news-corpus probe -s cambio -s el_espectador -s semana -s w_radio \
  --from 2018-08

# Solo si auditoria muestra meses faltantes:
# kelly news-corpus collect -s el_tiempo -s noticias_caracol -s blu_radio -s la_republica -s noticias_rcn --from 2018-08 --to 2022-08
# kelly news-corpus retry-failed --limit 100
```

**¿Qué hace?**
- Comprueba cobertura actual (DRY-RUN, sin red)
- Prueba medios alternativos (Arc)
- **SOLO ejecutar si hay meses faltantes medidos**

---

### 7.6 Piloto de extracción antes de crawling amplio

```bash
for medium in el_tiempo noticias_caracol blu_radio la_republica noticias_rcn; do
  kelly news-corpus extract --source "$medium" --all --limit 25
done

kelly news-corpus profile

docker exec "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$WORK_DB" -c "
SELECT source_id, extraction_status, count(*) AS filas,
       count(*) FILTER (WHERE length(content)>=500) AS cuerpo_analizable
FROM article GROUP BY source_id, extraction_status ORDER BY source_id, extraction_status;"

# Si hay fallos de red:
# kelly news-corpus extract --retry --limit 100
```

**¿Qué hace?**
- Extrae 25 artículos POR MEDIO (prueba de conectividad)
- Parsea HTML, obtiene títulos reales
- Mide cuerpos >= 500 caracteres
- **Benchmark estratificado DESPUÉS, si vale la pena**

---

### 7.7 Reetiquetar, exportar y separar candidatos

```bash
kelly news-corpus clean-content
kelly news-corpus tag --retag
kelly news-corpus profile

kelly news-corpus export --from 2018-08-07 --to 2022-08-06 \
  -o exports/duque-candidatos.csv -F csv --no-content

kelly news-corpus export --from 2018-08-07 --to 2022-08-06 \
  -o exports/duque-candidatos.parquet -F parquet
```

**¿Qué hace?**
- Relimpia contenido
- Reetiquet con nuevos títulos
- Exporta CSV + Parquet para análisis

---

### 7.8 Publicar dump nuevo solo tras restaurarlo

```bash
RUN_ID=$(date +%Y%m%d_%H%M%S)
OUT="$KELLY/dumps/news_corpus_duque_rebuild_$RUN_ID.dump"
TEST_DB="duque_restore_$RUN_ID"

docker exec "$PG" pg_dump -U postgres -d "$WORK_DB" \
  -Fc --no-owner --no-privileges > "$OUT.partial"

mv "$OUT.partial" "$OUT"
shasum -a 256 "$OUT"

docker exec "$PG" createdb -U postgres "$TEST_DB"
docker exec -i "$PG" pg_restore -U postgres --no-owner --no-privileges \
  --exit-on-error -d "$TEST_DB" < "$OUT"

docker exec "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$WORK_DB" \
  -c 'SELECT source_id,count(*) FROM article GROUP BY source_id ORDER BY source_id;'

docker exec "$PG" psql -X -v ON_ERROR_STOP=1 -U postgres -d "$TEST_DB" \
  -c 'SELECT source_id,count(*) FROM article GROUP BY source_id ORDER BY source_id;'

# Solo si los conteos coinciden:
# docker exec "$PG" dropdb -U postgres "$TEST_DB"
```

**¿Qué hace?**
- Genera dump con fecha
- **Valida restaurando en DB temporal**
- Solo publica si validación pasa
- **NO sobrescribe pilot de Kelly**

---

## EJECUCIÓN RECOMENDADA

**Orden:**
1. ✅ 7.1 Setup herramientas (1 hora, sin riesgos)
2. ✅ 7.2 DB aislada (5 min)
3. ✅ 7.3 Sembrar datos (10 min)
4. ✅ 7.4 Enriquecer (5 min, SIN RED)
5. ⚠️ 7.5 Discovery (SOLO si hay gaps medidos)
6. ⚠️ 7.6 Extracción piloto (2-3 horas, CON RED)
7. ✅ 7.7 Export (10 min)
8. ✅ 7.8 Dump + Validación (30 min)

**Pausa crítica después de 7.4:**
- ¿Cuántos títulos ganaste con enrich?
- ¿Slug derivado es útil o tiene ruido?
- ¿Vale la pena extracción HTML?

---

## VARIABLES IMPORTANTES

| Variable | Valor | Nota |
|---|---|---|
| `KELLY` | `/Users/...kelly/...` | Tu ruta local |
| `PG` | `news-corpus-unificado` | Contenedor actual |
| `WORK_DB` | `news_duque_work` | **NUEVA DB, no modificar original** |
| `DB_PASSWORD` | Introducir interactivo | Nunca en scripts |
| `RUN_ID` | `$(date +%Y%m%d_%H%M%S)` | Timestamp para dumps |

---

## RIESGOS Y CUIDADOS

⚠️ **CRÍTICOS:**
- No ejecutar 7.5/7.6 sin antes revisar resultados 7.4
- DB original `news_corpus` **nunca se modifica**
- Dump validado en DB temporal ANTES de publicar
- PASSWORD introducido interactivo, no hardcodeado

✅ **SEGUROS:**
- 7.1-7.4 son de solo lectura + una DB aislada nueva
- Puedes repetir 7.2-7.3 si algo falla
- Cambio/Arc/W_Radio son opcionales (solo 5 medios principales son críticos)

---

## PRÓXIMO PASO

Ejecuta 7.1 y reporta:
- ✅ Docker build exitoso
- ✅ Tests pasan
- ✅ CLI comandos disponibles

Luego continuamos con 7.2-7.3 (seeding de datos).
