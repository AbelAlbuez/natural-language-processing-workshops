# Fase 1 — Research & Architecture

**Estado:** ✅ COMPLETADO (investigación empírica)
**Fecha de ejecución:** 2026-08-31
**Alcance:** requisito obligatorio de `CLAUDE.md` §12, §33 y §34 (Fase 1).
**Regla aplicada:** todos los datos de cobertura de este documento fueron **verificados empíricamente** contra las APIs y los sitios reales, no asumidos. Cada afirmación indica cómo se comprobó.

> ⚠️ Ninguna cifra de este documento proviene de documentación de proveedores ni de memoria. Donde no se pudo verificar, se dice explícitamente.

---

## A. Análisis de FinSage

Repositorio inspeccionado: `jctp94/FinSage` (vía `gh api`, rama por defecto).

El módulo relevante es **`ETL/etl_news`**, no los agentes. Estructura observada:

```text
ETL/etl_news/app/
├── providers/        base.py, gdelt.py, alpha_vantage.py, eodhd.py, finnhub.py, edgar.py, bulk_datasets.py
├── repositories/     checkpoint.py, news.py, connection.py, create_tables.py, migrations.py
├── utils/            rate_limiter.py, url.py, validator.py, text_extractor.py, logging_config.py
├── config/           settings.py, providers_config.py, finance_sources.py, company_aliases.py
├── service/          etl_news_service.py
└── handlers/         base_handler.py, etl_news_handler.py
```

### A.1 Qué se reutiliza conceptualmente

| Componente FinSage | Reutilizable | Justificación |
|---|---|---|
| `providers/base.py` — `BaseNewsProvider` (ABC) + DTO unificado | ✅ Alto | Es exactamente el patrón de adapters que pide `CLAUDE.md` §11. El DTO `NewsArticle` ya separa campos obligatorios de campos de enriquecimiento opcional. |
| `providers/base.py` — `CircuitBreaker` | ✅ Alto | Máquina de estados `healthy → degraded → unavailable → recovery probes`. Directamente aplicable a §19. |
| `utils/rate_limiter.py` — `AdaptiveRateLimiter` | ✅ Alto | Rate limiting adaptativo con backoff/recovery, requisito §19. |
| `repositories/checkpoint.py` | ✅ Alto | `get_completed_chunk_keys(provider) -> set[tuple]` es precisamente el modelo de reanudación de §10. Solo cambia la clave del chunk. |
| `utils/url.py` — `normalize_url`, `hash_url` | ✅ Alto | Base de la deduplicación de §17. |
| `providers/gdelt.py` — manejo de respuestas no-JSON | ✅ Alto | Ver §B.2: distingue `empty` / `throttled` / `rejected`, y **no marca el chunk como completado** si la petición fue rechazada. Es la lección más valiosa del repo. |
| `utils/validator.py`, `utils/text_extractor.py` | 🟡 Medio | Útiles como referencia; la lógica es específica de finanzas. |
| Kafka + arquitectura de agentes | ❌ No | Infraestructura distribuida innecesaria aquí (`CLAUDE.md` §23: "No introducir infraestructura distribuida innecesaria"). |
| `config/finance_sources.py` (filtro por dominio) | 🟡 Patrón sí, contenido no | El patrón "filtrar por conjunto de dominios permitidos antes de crear la fila" se reutiliza con los 10 medios colombianos. |

### A.2 Qué NO se debe copiar

- El acoplamiento a `ticker`/`company` atraviesa todo el DTO y las firmas (`fetch(ticker, company, start_dt, end_dt)`). Nuestra unidad es `(source, topic, date_range, government)`.
- El filtrado temprano por dominio en `_parse()` **descarta el artículo sin registrar nada**. Para un corpus académico esto destruye trazabilidad: necesitamos saber qué se descartó y por qué (§18, §26).
- `raw_json` se serializa a `str` antes de construir el DTO — mezcla capas. Conservar `dict` y serializar solo en la capa de persistencia.

### A.3 Bug latente heredable (importante)

`gdelt.py` clasifica correctamente los cuerpos **no-JSON**, pero asume que un cuerpo **JSON válido es siempre correcto**. La sección B.2 demuestra empíricamente que GDELT devuelve `HTTP 200` + JSON válido con artículos **fuera de la ventana solicitada** cuando está siendo throttleado. FinSage aceptaría esos datos y marcaría el chunk como completado.

**Nuestro provider debe validar que `seendate ∈ [start, end]` antes de aceptar la respuesta.**

---

## B. Comparación de providers (verificado empíricamente)

### B.1 Tabla comparativa

| Provider | Cobertura histórica | Medios CO | Metadata | Texto completo | API key | Rate limits | Costo | Fiabilidad |
|---|---|---|---|---|---|---|---|---|
| **GDELT DOC 2.0** | **2017-01 → hoy** (verificado; 2016 rechazado) | Sí, por `domain:` | url, title, seendate, domain, language, socialimage | ❌ No | No | Agresivos, no documentados; **38% de éxito a 25 s de espaciado** | Gratis | 🔴 Baja — ver B.2 |
| **Sitemaps nativos** | **Varía por medio: 1990 → hoy** (ver sección C) | Nativo | url, lastmod, a veces `news:title` | ❌ (requiere fetch) | No | robots.txt | Gratis | ✅ Alta |
| **Wayback CDX** | 1996 → hoy | Cualquiera | timestamp, url, statuscode, mimetype | ✅ vía snapshot | No | Estrictos | Gratis | 🔴 Baja para bulk — ver B.3 |
| **NewsAPI** | ~1 mes (plan gratuito) | Limitada | Buena | Parcial | ✅ Sí | 100 req/día | Gratis/pago | No evaluado a fondo |
| **RSS** | Solo actualidad | Sí | Buena | Parcial | No | — | Gratis | ✅ Alta |

> **NewsAPI**: no se ejecutaron pruebas porque su ventana histórica (~1 mes en plan gratuito) lo descarta como proveedor histórico para 2006–2026. Queda como posible complemento de *discovery* en tiempo real (§13). Esto es una **decisión basada en el alcance del proyecto, no una verificación empírica** — si el equipo consigue un plan de pago, debe re-evaluarse.

### B.2 GDELT — hallazgos críticos

**Hallazgo 1 — La cobertura empieza en 2017, no en 2006.**

```text
consulta: domain:eltiempo.com, ventana de 1 mes
2006-01 → cuerpo vacío
2010-01 → cuerpo vacío
2014-01 → cuerpo vacío
2016-01 → "Invalid query start date."     ← rechazo explícito
2017-01 → 20 artículos, seendate 20170102..20170103  ← correcto
```

**Hallazgo 1b — Tasa de éxito del 38% dentro del rango soportado.**

El sondeo completo de 12 ventanas (espaciado de 25 s) permite separar *cobertura* de *fiabilidad*:

```text
FUERA DE RANGO (pre-2017)
  2006-01  cuerpo vacío
  2010-01  cuerpo vacío
  2014-01  cuerpo vacío
  2016-01  "Invalid query start date."          ← rechazo explícito

DENTRO DE RANGO (2017+)
  2017-01  ✅ 20 arts · seendate 20170102..20170103
  2017-06  ❌ cuerpo vacío
  2020-01  ❌ cuerpo vacío
  2023-01  ✅ 20 arts · seendate 20230101..20230102
  2025-01  ❌ cuerpo vacío
  2026-01  ❌ cuerpo vacío
  2026-06  ❌ cuerpo vacío
  2026-08  ✅ 20 arts · seendate 20260801
```

**Solo 3 de 8 ventanas dentro del rango soportado devolvieron datos (37,5%)**, y eso con 25 s entre peticiones. Los fallos son cuerpos vacíos con `HTTP 200`, indistinguibles de "este mes no tuvo noticias" si no se comprueban.

**Matiz importante y favorable:** las 3 respuestas exitosas trajeron **fechas correctas dentro de la ventana pedida** (3/3). Combinado con el hallazgo 2, el patrón es: *cuando GDELT responde bien espaciado, los datos son correctos; cuando está saturado, devuelve o bien vacío, o bien datos de otra época.* Ambos modos de fallo son silenciosos.

**Consecuencia operativa:** un bloque GDELT necesita **dos** controles, no uno — validación de ventana (hallazgo 2) *y* distinguir "vacío por throttling" de "vacío legítimo". Un mes sin artículos debe reintentarse, no marcarse completado. A ~38% de éxito, cubrir 10 medios × 120 meses (2017–2026) exige del orden de 3.000 peticiones efectivas para 1.200 bloques.

**GDELT cubre ~45% del horizonte objetivo (2017–2026 de 2006–2026). Los primeros 11 años NO están disponibles vía GDELT.** Esto invalida por sí solo la estrategia de "un único provider" y confirma la advertencia de `CLAUDE.md` §12.2.

**Hallazgo 2 — Corrupción silenciosa bajo throttling. ⚠️ CRÍTICO**

Al lanzar consultas en ráfaga (sin espaciado), GDELT devolvió `HTTP 200` con **JSON estructuralmente válido**, pero conteniendo **los mismos 5 artículos recientes (`seendate=20260609`) para tres ventanas distintas (2015, 2017, 2018)**:

```text
requested 20150601..20150608  → seendate 20260609T170000Z  "asesinan en Barranquilla a pareja de alias Castor"
requested 20170101..20170108  → seendate 20260609T170000Z  (idénticos)
requested 20180301..20180308  → seendate 20260609T170000Z  (idénticos)
```

Al repetir las mismas consultas **con 25 s de espaciado**, la ventana 2017-01 devolvió correctamente `seendate 20170102..20170103`.

**Conclusión:** bajo presión, GDELT no falla — *miente*. Un cliente ingenuo insertaría artículos de 2026 etiquetados como 2015 y marcaría el chunk como completado. Para un corpus académico donde el eje temporal *es* la variable de análisis (gobierno × tiempo), esto es catastrófico.

**Mitigación obligatoria:**
1. Validar `seendate ∈ [start_dt, end_dt]` para **cada** artículo.
2. Si algún artículo cae fuera de la ventana → descartar la respuesta completa, tratar como throttle, backoff exponencial, **no** marcar el chunk completado.
3. Espaciado mínimo ≥ 5 s entre peticiones (25 s fue estable en las pruebas; el valor exacto debe calibrarse).

### B.3 Wayback CDX — viable pero no para bulk

```text
showNumPages(eltiempo.com*, 2008) → 3434 páginas   ← el archivo existe y es grande
```

Pero las consultas con wildcard sobre dominios grandes son inestables:

```text
url=eltiempo.com/*&from=20080601&to=20080630&limit=12   → 504 Gateway Time-out
url=eltiempo.com*&...&collapse=urlkey&page=0            → 1 sola fila
url=eltiempo.com*&...&page=500                          → 0 filas
```

**Veredicto:** Wayback es el **último recurso** para medios sin sitemap histórico (Semana, El Espectador pre-Arc). Requiere paginación cuidadosa, reintentos y tolerancia a 504. No debe estar en el camino crítico del MVP.

---

## C. Cobertura de medios (verificado medio por medio)

Se inspeccionaron `robots.txt` y los índices de sitemap de los 10 medios. **8 de 10 exponen índices de sitemap.**

| Medio | Mecanismo | Cobertura verificada | Estado |
|---|---|---|---|
| **El Tiempo** | `sitemap-articles-YYYY-MM.xml` | **1990-01 → 2026** mensual | ✅ Excelente (con reserva, ver C.1) |
| **Noticias Caracol** | `sitemap-YYYYMM.xml` | **2008-11 → 2026-08** (214 meses) | ✅ Excelente |
| **Blu Radio** | `sitemap-YYYYMM.xml` | **2012-09 → 2026-08** (166 meses) | ✅ Completo para su vida útil (fundada 2012) |
| **La República** | `sitemaps/articles_<Month>_<Year>.xml.gz` | **2012 → 2026** (175 meses) | ✅ Muy bueno |
| **Noticias RCN** | `sitemaps/articles_<Month>_<Year>.xml.gz` | **2013 → 2026** | ✅ Bueno |
| **El Espectador** | Arc `outboundfeeds` + `archivo/<sección>/` | Paginado; `from=1000` → `lastmod 2026-08-25` | 🟡 Superficial |
| **Semana** | Arc `outboundfeeds`, `from=0..300` | Solo ~300 páginas | 🟡 Superficial |
| **W Radio** | Arc `outboundfeeds` (no en robots.txt, pero responde 200) | No cuantificada | 🟡 Requiere verificación |
| **Cambio** | `cambiocolombia.com` (sin `www`) | Medio refundado en 2021 | 🟡 Horizonte corto por naturaleza |
| **RTVC** | `rtvc.gov.co` → **redirige a `inravision.gov.co`** | — | 🔴 Cambio de dominio |

### C.1 Reserva importante — El Tiempo: el archivo está *adelgazado*

El sitemap llega a 1990, pero el **volumen mensual** revela que el archivo antiguo está muy incompleto:

| Mes | URLs |
|---|---|
| 2006-06 | 23 |
| 2008-06 | 225 |
| 2010-06 | 411 |
| 2012-06 | 332 |
| 2014-06 | 129 |
| **2016-06** | **4.670** |
| 2018-06 | 5.480 |
| 2020-06 | 5.013 |
| 2022-06 | 6.883 |
| 2024-06 | 9.033 |

**Hay un salto de ~35× entre 2014 y 2016.** El sitemap de 2006–2015 no es un archivo completo: es una muestra residual. 23 artículos en un mes es implausible para un diario nacional.

**Implicación metodológica seria:** comparar volumen de cobertura entre el gobierno de Uribe (2006–2010) y el de Petro (2022–2026) usando estos datos produciría un artefacto puro del archivado, no un hallazgo. **El corpus debe registrar la densidad de archivo por medio-mes y el análisis debe normalizar por ella o restringirse a ventanas comparables.**

Además, las URLs de 2008 tienen forma `/archivo/documento/MAM-2880084` — sin slug, por lo que **el título no puede derivarse de la URL** y requiere fetch de la página. Las URLs modernas sí son slugificadas.

### C.2 Riesgos de identidad de medio

- **RTVC** redirige a `inravision.gov.co` — el dominio institucional cambió. Cualquier mapeo `domain → source_id` debe ser *many-to-one* y versionado.
- **Cambio** solo responde sin `www`.
- **Semana / El Espectador / W Radio** usan Arc XP (CMS de Washington Post), migración que rompió sus archivos anteriores.

---

## D. Arquitectura propuesta

### D.1 Decisión central: **sitemap-first, GDELT como complemento**

La investigación invierte la hipótesis inicial de `CLAUDE.md` §13 ("GDELT como proveedor histórico principal"):

```text
                    2006 ─────────── 2016 ─┼─ 2017 ─────────── 2026
GDELT DOC 2.0                              │████████████████████████
Sitemaps nativos    ███████████████████████████████████████████████
  (El Tiempo 1990+, Caracol 2008-11+, Blu 2012-09+, LR 2012+, RCN 2013+)
Wayback CDX         ███████████████████████████████████████████████  (frágil)
```

**Los sitemaps nativos son el único mecanismo que cubre el horizonte completo 2006–2026.** GDELT aporta valor real como fuente **cross-source** para 2017+ (búsqueda por tema en todos los medios a la vez) y como validación cruzada. Wayback cubre huecos.

> Esto no cambia ninguna decisión de negocio de §30 (país, horizonte, medios, gobiernos, organización). Cambia solo el medio técnico, que §31 deja explícitamente a criterio de la implementación.

### D.2 Componentes

```text
config/  sources.yaml · governments.yaml · topics.yaml
                    ↓
        ┌───────── DISCOVERY (adapters) ─────────┐
        │  SitemapProvider   (histórico, 1º)     │
        │  GDELTProvider     (2017+, cross-src)  │
        │  WaybackProvider   (relleno de huecos) │
        │  RSSProvider       (actualidad)        │
        └────────────────────┬───────────────────┘
                             ↓  RawDiscoveryRecord (+ provenance)
                      NORMALIZATION      fechas · URLs · unicode · source mapping
                             ↓
                      VALIDATION         ⚠ incluye window-check anti-throttle
                             ↓
                      DEDUPLICATION      canonical URL → url_hash → (source,title,date)
                             ↓
                      STORAGE            SQLite/Postgres + tabla de checkpoints
                             ↓
                      EXTRACTION (dif.)  fetch de artículo → texto completo
                             ↓
                      API · CLI · EXPORT (JSONL/Parquet)
```

### D.3 Modelo de datos

Además de lo exigido por §14, la investigación obliga a añadir:

- `archive_density` por `(source, year_month)` — indispensable dado C.1.
- `window_validated: bool` — si la respuesta pasó el control anti-throttle de B.2.
- `discovery_provider` ≠ `source` — un artículo de El Tiempo puede descubrirse por sitemap **y** por GDELT; ambos linajes deben conservarse (§18).

### D.4 Storage

**SQLite** para el MVP, esquema compatible con Postgres. Justificación (§23: simplicidad + reproducibilidad + costo): el corpus objetivo (~10⁵–10⁶ artículos de metadata) cabe holgadamente; es un único archivo versionable y compartible con el equipo, sin infraestructura. Export a Parquet para el análisis NLP posterior.

---

## E. Estrategia histórica (cómo bajar 20 años sin una sola ejecución)

Unidad atómica de trabajo — **el chunk**:

```text
(source, provider, year_month)
```

Elegida porque coincide con la granularidad nativa de los sitemaps de El Tiempo, Caracol, Blu, La República y RCN. El chunk es idempotente y reanudable.

```text
volumen ≈ 10 medios × 240 meses = 2.400 chunks
```

Cada chunk registra: `status ∈ {PENDING, RUNNING, COMPLETED, FAILED, PARTIAL}`, `n_found`, `n_new`, `n_duplicates`, `n_failures`, `executed_at`, `query`. Reanudar = consultar los chunks no completados (patrón `checkpoint.py` de FinSage).

El filtrado temático (§8) se aplica **después** del discovery, sobre título + URL + sección — no como parámetro de búsqueda. Razón: los sitemaps no aceptan queries, y filtrar en discovery haría irreproducible el corpus si luego cambian las keywords. Se descubre todo el mes y se etiqueta después.

---

## F. Riesgos identificados

| # | Riesgo | Severidad | Evidencia | Mitigación |
|---|---|---|---|---|
| 1 | **GDELT devuelve datos fuera de ventana bajo throttling** | 🔴 Crítica | B.2, reproducido | Validación de ventana obligatoria + rechazo de la respuesta completa |
| 1b | **GDELT: 38% de éxito; los fallos son cuerpos vacíos con HTTP 200** | 🔴 Crítica | B.2, 12 ventanas sondeadas | Distinguir "vacío por throttle" de "vacío legítimo"; nunca completar un bloque vacío sin reintentos |
| 2 | **Sesgo de archivo: densidad 35× mayor post-2016** | 🔴 Crítica | C.1, medido | Registrar `archive_density`; normalizar o restringir ventanas en el análisis |
| 3 | GDELT no cubre 2006–2016 | 🟠 Alta | B.2, "Invalid query start date" | Sitemaps nativos como fuente primaria |
| 4 | Semana / El Espectador / W Radio con archivo superficial (Arc) | 🟠 Alta | Sección C | Wayback CDX + `archivo/<sección>/` de El Espectador |
| 5 | Cambio de dominio (RTVC → inravision.gov.co) | 🟡 Media | Sección C.2 | Mapeo `domain → source_id` many-to-one y versionado |
| 6 | URLs 2008 sin slug (`MAM-XXXXXXX`) — sin título en discovery | 🟡 Media | C.1 | Fase de extracción obligatoria para chunks antiguos |
| 7 | Wayback CDX inestable (504) en consultas wildcard | 🟡 Media | B.3 | Fuera del camino crítico; reintentos + paginación estrecha |
| 8 | Paywalls y artículos eliminados | 🟡 Media | No medido aún | Registrar `http_status` en extracción; nunca borrar la fila de discovery |
| 9 | Cambio de estructura HTML entre épocas | 🟡 Media | Inferido de C.1 | Extractores por época/medio; conservar `raw_html_hash` |

---

## G. Plan de implementación

| Fase | Contenido | Estado |
|---|---|---|
| **1** | Research & Architecture (este documento) | ✅ COMPLETADO |
| **2** | Foundation: proyecto, `config/*.yaml`, modelos, SQLite, logging | 🔴 PENDIENTE |
| **3** | `SitemapProvider` + chunking mensual + checkpoints | 🔴 PENDIENTE |
| **4** | Normalización (fechas, URLs, source mapping) | 🔴 PENDIENTE |
| **5** | Deduplicación (canonical URL, hash) | 🔴 PENDIENTE |
| **6** | `GDELTProvider` **con validación de ventana** (riesgo #1) | 🔴 PENDIENTE |
| **7** | CLI + API + export JSONL/Parquet | 🔴 PENDIENTE |
| **8** | Métricas de `archive_density` (riesgo #2) | 🔴 PENDIENTE |
| **9** | Wayback + extracción de contenido | 🔴 PENDIENTE |

**Corpus de demostración sugerido** (§25 — "la primera entrega solo necesita un corpus pequeño"):
El Tiempo + Noticias Caracol + Blu Radio, 2013–2024, temas Política y Seguridad. Elegido porque los tres tienen sitemaps mensuales verificados y densidad de archivo comparable en ese rango — evita el riesgo #2 en la primera entrega.

---

## Verificación pendiente ⚠️

- Profundidad exacta de W Radio (Arc responde 200; no se cuantificó).
- Profundidad de `El Espectador/archivo/<sección>/`.
- NewsAPI: descartado por alcance, **no** por prueba empírica.
- La tasa de éxito del 38% de GDELT se midió sobre 8 ventanas dentro de rango, con un solo dominio (`eltiempo.com`) y un solo espaciado (25 s). Es suficiente para descartarlo como fuente primaria, pero **no** es una calibración: antes de la Fase 6 hay que barrer el espaciado (25 / 60 / 120 s) para encontrar el punto de operación real.
- No se comprobó si el 38% depende del dominio consultado o de la hora del día.
