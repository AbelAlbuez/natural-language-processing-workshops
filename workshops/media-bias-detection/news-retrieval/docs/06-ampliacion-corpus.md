# Ampliación del corpus — Entrega 2

Objetivo: pasar del piloto (3 medios, 6 meses) a un corpus **comparable entre al
menos 6 medios**, con **todos los titulares disponibles** de la ventana elegida.

## 1. Decisiones

**Unidad comparable: el titular.** El cuerpo del artículo no está disponible por
igual en todos los medios (en el piloto, 15 % de Blu Radio y 30 % de Caracol
tienen un cuerpo de ≥500 caracteres, frente a 99 % de El Tiempo). En cambio, el
titular sí es comparable: se obtiene de `news:title` en el sitemap o se
reconstruye desde la URL. Así se cubre prácticamente el 100 % de las URLs sin
descargar ninguna página. Los cuerpos se extraen después, solo para la
submuestra que lo necesite (eventos seleccionados para el análisis multiagente).

**Ventana: gobierno Petro, 2022-08 → 2026-07 (48 meses).** Es la única ventana
en la que pueden coincidir 6 o más medios:

| Medio | Estrategia | ¿Cubre 2022-08 → 2026-07? |
|---|---|---|
| El Tiempo | sitemap mensual | Sí (denso desde 2016-03) |
| Noticias Caracol | sitemap mensual | Sí |
| Blu Radio | sitemap mensual | Sí |
| La República | sitemap mensual .gz | Sí |
| Noticias RCN | sitemap mensual .gz | Sí |
| Cambio | índice de sitemap (**nuevo proveedor**) | Sí en principio (existe desde 2021); confirmar con `probe` |
| El Espectador | feed Arc (**nuevo proveedor**) | Desconocido: medir con `probe` |
| Semana | feed Arc (**nuevo proveedor**) | Desconocido: medir con `probe` |
| W Radio | feed Arc (**nuevo proveedor**) | Desconocido: medir con `probe` |
| RTVC | sin mecanismo de discovery | No (inactivo) |

Con los cinco sitemaps mensuales más Cambio se aseguran **6 medios**. Los tres
medios Arc se suman en la medida en que su feed alcance la ventana. En 2013, en
cambio, solo llegan 5 medios, por lo que el piloto queda como antecedente y no
como corpus comparable.

Una ventana de un solo gobierno controla además una variable de confusión: si se
comparan medios a lo largo de gobiernos distintos, una diferencia de framing
puede ser simplemente una diferencia de agenda.

**Criterio de comparabilidad.** Un medio entra al corpus comparable si tiene al
menos el 90 % de los meses de la ventana con bloque `completed` y cobertura
`completa`. Si no lo cumple, se reporta aparte (o se recorta la ventana común) y
nunca se mezcla en silencio.

## 2. Qué cambió en el código

- `providers/indexed.py`: `ArcFeedProvider` (El Espectador, Semana, W Radio) y
  `SitemapIndexProvider` (Cambio). Ambos descargan el feed una vez por corrida
  y lo reparten por mes. Si el feed no alcanza un mes, el bloque **falla** con
  `FueraDeAlcance`. Si lo alcanza solo en parte, cada URL queda marcada
  `cobertura = parcial` en `discovery_record.raw_payload`.
- `providers/__init__.py`: `ProviderPool` elige el proveedor según la
  estrategia de `sources.yaml`. `collect` y `retry-failed` ya cubren los 9
  medios activos.
- `providers/sitemap.py`: el parseo pasó a ser compartido. Si el sitemap trae
  `news:publication_date`, se usa esa fecha (es de publicación) en vez de
  `lastmod` (que es de modificación), y `date_source` deja constancia de cuál
  se usó.
- `pipeline/collector.py`: los titulares que vienen de `news:title` ahora se
  guardan con `title_source = 'sitemap'`. Antes quedaba vacío y no se
  distinguía de un título faltante.
- Nuevo comando `news-corpus probe`: mide hasta qué fecha llega cada feed
  **sin escribir en la base**.
- `config/sources.yaml`: Semana con `page_size: 100` y `max_offset: 30000`. El
  valor anterior (300) cortaba el feed en 400 URLs.
- `tests/test_indexed_providers.py`: 9 pruebas nuevas, 103 en total.

⚠️ Los proveedores nuevos se probaron con XML que imita los formatos, **no**
contra los sitios reales (el entorno donde se escribieron no tiene acceso a esos
dominios). Por eso el paso 1 de la sección siguiente es obligatorio.

## 3. Procedimiento

Desde `news-retrieval/`, con Postgres arriba y el dump actual restaurado (ver
`03-guia-del-equipo.md`):

```bash
uv pip install -e ".[dev,export]"
pytest -q                                     # 103 passed

# 1. Medir el alcance real de los feeds nuevos (no escribe en la base)
news-corpus probe --from 2022-08

# 2. Ver el plan y luego probar con UN mes
news-corpus collect --from 2022-08 --to 2026-07 --dry-run
news-corpus collect --from 2024-03 --to 2024-03
news-corpus status

# 3. Ventana completa (los meses ya completados no se repiten)
news-corpus collect --from 2022-08 --to 2026-07
news-corpus retry-failed

# 4. Titulares desde la URL para lo que no trajo news:title (sin red)
news-corpus enrich
news-corpus tag

# 5. Revisar y publicar
news-corpus profile
./scripts/dump-db.sh                          # nuevo dump + MANIFEST
```

**Qué revisar en el paso 1:** para cada medio Arc o índice, la columna «¿cubre
el piso?». Si un medio dice `no`, no entra en la ventana completa. Se puede
recolectar igual (sus meses fuera de alcance quedarán `failed` con
`FueraDeAlcance`), pero se excluye del análisis comparable.

**Costo.** Los sitemaps mensuales hacen una petición por medio y mes: 5 × 48 =
240 peticiones, unos 4 minutos a 1 req/s. Los feeds Arc hacen una petición por
cada 100 URLs. `enrich` y `tag` no tocan la red. La extracción de cuerpos
(`news-corpus extract`) cuesta una petición por artículo, así que se reserva para
la submuestra de eventos y no se corre sobre todo el corpus.

**Bloques del piloto.** Los bloques de 2013 y 2016 permanecen en la base; para
el análisis comparable se filtra por `government_id = 'petro'`.

## 4. Consultas de verificación

```sql
-- Meses completos por medio en la ventana
SELECT source_id, count(*) FILTER (WHERE status='completed') AS ok,
       count(*) FILTER (WHERE status='failed') AS fallidos
FROM collection_chunk
WHERE period_start BETWEEN '2022-08-01' AND '2026-07-01'
GROUP BY 1 ORDER BY 1;

-- Procedencia del titular por medio
SELECT source_id, title_source, count(*)
FROM article WHERE government_id = 'petro'
GROUP BY 1, 2 ORDER BY 1, 2;

-- Meses con cobertura parcial (feeds Arc o índices)
SELECT a.source_id, to_char(a.published_date,'YYYY-MM') mes, count(*)
FROM discovery_record d JOIN article a ON a.id = d.article_id
WHERE d.raw_payload->>'cobertura' = 'parcial'
GROUP BY 1, 2 ORDER BY 1, 2;
```

## 5. Impacto en el análisis (puntos 2 y 3)

Los titulares `slug` pierden tildes, mayúsculas y puntuación; los de `sitemap` y
`extracted`, no. Para comparar medios en igualdad de condiciones, el
preprocesamiento del EDA normaliza todos los titulares a minúsculas y sin
tildes, y reporta las métricas desglosadas por `title_source`. Así se puede
comprobar que una diferencia entre medios no es un artefacto de la procedencia
del titular.
