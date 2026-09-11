# Análisis del estado y opciones para el corpus real

Fecha del análisis: 2026-09-08.

Este reporte distingue dos cosas que el proyecto nombra de forma relacionada,
pero que hoy están separadas:

- el prototipo multiagente en la raíz de `media-bias-detection`, que trabaja con
  `corpus_ejemplo.json` o con una búsqueda web puntual;
- el servicio histórico `news-retrieval/`, que sí existe y ya tiene un corpus
  persistido en un dump de PostgreSQL, pero todavía no alimenta al prototipo de
  framing.

## Inventario (Paso 1)

### Código del prototipo multiagente

| Agente o componente | Estado y comportamiento exacto |
|---|---|
| `verificar_mismo_evento(articulos)` | Implementado: envía la lista de artículos al LLM y exige un objeto JSON con `mismo_evento`, `resumen_evento`, `medios_confirmados` y `medios_descartados` con una razón por descarte. Decide si las fuentes cubren el mismo hecho puntual, no solo el mismo tema. |
| `analizar_lexico_framing(articulo)` | Implementado: envía un artículo al LLM y exige JSON con `medio`, una lista de `terminos_clave` con término, concepto referido, connotación y justificación, más `resumen_framing`. El prompt exige WCL y prohíbe analizar sentimiento o tono. |
| `analizar_actores_citas(articulo)` | Implementado: envía un artículo al LLM y exige JSON con `medio`, actores, rol atribuido, encuadre, citas directas e indirectas, más `resumen_actores`. Se centra en person-oriented framing y no en tono. |
| `analizar_estilo_enfasis(articulo)` | Implementado como simplificación: envía un artículo al LLM y exige JSON con subtemas y grado de énfasis, además de `extension_relativa`, `titular_alarmista`, `incluye_contexto_antecedentes` y una nota de provisionalidad. No calcula métricas cuantitativas. |
| `sintetizar_reporte(evento_id, verificacion, analisis_lexico, analisis_actores, analisis_estilo)` | Implementado: recibe la verificación y los tres análisis, y exige un JSON comparativo con medios analizados/descartados, diferencias por dimensión y `conclusion_comparativa`. |
| `AgenteBusqueda` | Interfaz abstracta, no una implementación usable por sí sola: `buscar()` lanza `NotImplementedError`. Es un contrato para agentes que devuelven artículos con `medio`, `titulo`, `texto`, `fecha` y `url`. |
| `BusquedaWebAnthropic` / `buscar_noticias_actuales(tema, n)` | Implementado para búsqueda viva: usa `web_search_20250305` de Anthropic, solicita hasta `n` medios distintos y valida el JSON final. Devuelve artículos resumidos por el LLM; no garantiza que sean el mismo evento puntual. |
| `orquestador.py` | Implementa el flujo: carga el corpus curado o la búsqueda viva, agrupa por `evento_id`, verifica el evento, conserva solo los medios confirmados, ejecuta los tres analistas y sintetiza. En búsqueda viva mete inicialmente todos los resultados bajo un único `evento_id` derivado del tema. |

Todos los agentes LLM pasan por `_extraer_json()` y `json.loads()`. El
cliente de Anthropic y el modelo están configurados, pero ejecutar el flujo
requiere credenciales y llamadas externas; el análisis está implementado, no
es un resultado ya almacenado en el repositorio.

### Qué está implementado, qué es stub y qué sigue pendiente

- **Implementado en el prototipo:** verificación de evento, análisis léxico,
  actores/citas, estilo cualitativo, síntesis y búsqueda web viva. La búsqueda
  es una fuente de candidatos, no un constructor histórico reproducible.
- **Stub intencional:** la clase abstracta `AgenteBusqueda` no trae datos; solo
  define la interfaz. La subclase web sí implementa `buscar()` delegando en
  `buscar_noticias_actuales()`.
- **Simplificación documentada:** `analizar_estilo_enfasis()` pide al LLM una
  descripción cualitativa. El propio código deja pendiente reemplazarla por
  `textstat`/`textdescriptives` del Taller 1.
- **Limitación de búsqueda:** la búsqueda viva resume artículos y devuelve una
  selección dependiente de la corrida. No conserva en el prototipo una bitácora
  de consultas, candidatos descartados por proveedor ni razones de descarte
  antes de la verificación LLM.
- **No implementado en el prototipo:** RSS por medio, scraping histórico,
  segmentación titular/lead/cuerpo/citas, NER o extracción estructurada de
  entidades, y construcción de un corpus histórico desde este pipeline.

### Lo que dice literalmente el corpus de ejemplo

`corpus_ejemplo.json` es una lista con:

- **1 evento:** `corte-reforma-tributaria-2024`;
- **3 artículos:** uno de `El Diario Nacional`, uno de `La Voz Empresarial` y
  uno de `Contexto Ciudadano`;
- **fuentes ficticias:** los dominios terminan en `.example.co`, y el README
  los describe como medios ficticios con diferencias de framing intencionales;
- **campos por registro:** `evento_id`, `medio`, `titulo`, `fecha`, `url` y
  `texto`;
- **hecho representado:** la decisión de la Corte Constitucional sobre una
  reforma tributaria, con fechas 2024-10-14 y 2024-10-15.

Por tanto, este archivo es una fixture didáctica, no evidencia periodística
real ni una muestra válida de medios colombianos. El ejemplo permite probar que
la arquitectura puede contrastar expresiones como `reforma`, `espaldarazo` e
`impuestazo`, pero no permite inferir patrones generales.

### El estado real de `news-retrieval/`

La carpeta histórica no es solo una mención vacía. Su README documenta fases
completadas de configuración, `SitemapProvider`, bloques mensuales y
checkpoints, normalización, deduplicación, extracción de contenido,
enriquecimiento, etiquetado y exportación. También documenta como pendientes
`GDELTProvider` y Common Crawl/Wayback como respaldo.

El dump `news-retrieval/dumps/news_corpus.dump`, según su manifiesto, contiene:

- `article`: **17.202** artículos;
- `discovery_record`: **17.206** observaciones;
- `collection_chunk`: **12** bloques;
- `source`: **10** fuentes catalogadas, aunque el dump recolectado contiene
  artículos de **3 medios**;
- artículos por medio: Blu Radio **7.214**, El Tiempo **5.048** y Noticias
  Caracol **4.940**;
- con cuerpo: Blu Radio **5.948**, El Tiempo **5.048**, Noticias Caracol
  **4.933**;
- con cuerpo de al menos 500 caracteres: Blu Radio **1.090**, El Tiempo
  **4.996**, Noticias Caracol **1.481**.

Este corpus histórico ya es real en el sentido de que proviene de URLs y
páginas de medios, y tiene persistencia, extracción y trazabilidad. No es, sin
embargo, equivalente al `corpus_ejemplo.json`: no está agrupado todavía por
mismo evento noticioso para el análisis de framing, y su disponibilidad de
cuerpo varía fuertemente por medio y período.

### Qué dice `entrega1.tex`

El informe describe `news-retrieval/` como el corpus histórico de mayor escala
que se construiría por separado y afirma que en la Entrega 1 no se reportan
cifras porque el corpus final aún no estaba completo. Con el estado actual del
repositorio, esa frase quedó desactualizada parcialmente: ya existe un dump
histórico de 17.202 artículos, pero todavía no constituye un corpus anotado o
agrupado por eventos para el análisis multiagente. El informe también declara
como limitación que el corpus curado es pequeño y didáctico, con una sola
noticia-evento y tres fuentes ficticias, y que la búsqueda real recupera temas
sin garantizar el mismo evento.

## Observaciones vs. estado actual (Paso 2)

| Observación metodológica | Estado actual | Qué necesitaría el corpus real para aplicarla con sentido |
|---|---|---|
| **1. Puntos calientes de divergencia:** distinguir desacuerdo fáctico real de una diferencia de tono o framing. | **Esquema parcial.** El verificador LLM compara artículos del mismo evento y el analista léxico identifica términos con carga de encuadre. No hay una anotación explícita de afirmaciones fácticas, evidencia, contradicciones o puntos de desacuerdo. Con un solo evento didáctico no se puede evaluar si un patrón se repite. | Definir eventos comparables y una unidad de hecho común: quién hizo qué, cuándo y dónde. Como mínimo práctico para un proyecto de curso: **8--12 eventos**, con **3--4 medios por evento** y al menos dos anotadores o una revisión manual de afirmaciones en una muestra. Menos de 6 eventos serviría como piloto, no como comparación creíble entre medios. |
| **2. Segmentación fina:** titular, lead, cuerpo y citas, no solo artículo completo. | **Esquema parcial.** El corpus histórico conserva título y cuerpo cuando se pueden extraer, y `parse_article()` recupera autor, fecha, sección y contenido. El prototipo multiagente entrega el artículo completo a cada analista; no hay `lead`, spans de citas, separación de voz propia/voz citada ni alineación por segmento. | Cada artículo debe conservar, como mínimo, titular, bajada/lead si existe, párrafos del cuerpo, citas directas, atribuciones indirectas y offsets o identificadores de párrafo. Debe marcarse si una parte fue extraída, reconstruida o quedó ausente. Para comparar framing, conviene exigir cuerpo disponible y reportar por separado artículos de audio/video o solo metadata. |
| **3. Entidades con valor analítico:** topónimos, organizaciones y actores. | **Parcial bajo.** Hay texto, campos de medio y sección, y un etiquetado temático en `news-retrieval`; el analista LLM puede devolver actores en `analizar_actores_citas()`. No hay NER persistente, tipos de entidad, normalización de alias, topónimos ni vínculo sistemático entre entidad, cita y encuadre. | Mantener anotaciones o extracción reproducible de personas, organizaciones, lugares e instituciones, con tipo, forma superficial, entidad normalizada y artículo/párrafo donde aparece. Para este proyecto, una revisión manual de una muestra de entidades importantes sería preferible a afirmar que el LLM produce una lista exhaustiva. |
| **4. Trazabilidad del corpus:** qué se buscó, qué se descartó y por qué. | **Implementado en `news-retrieval`; ausente en el prototipo web.** El servicio histórico separa `discovery_record` de `article`, conserva descartes con `rejected_reason`, guarda bloques, proveedor, URL solicitada, conteos y estados, y no borra observaciones. En cambio, `busqueda.py` solo retorna la lista final resumida por el LLM; no persiste consulta, resultados candidatos ni historial de corridas. | El corpus real debe guardar consulta o ventana temporal, proveedor, medio esperado, URL observada, fecha de discovery, resultado HTTP, motivo de rechazo, duplicado, falta de cuerpo y versión de reglas. La tabla de trazabilidad debe permitir reconstruir por qué un artículo entró o no entró sin depender de la memoria del equipo o del LLM. |

La primera observación depende especialmente de la unidad de análisis. Un
conjunto grande de artículos del mismo tema no reemplaza varios eventos bien
identificados: si se mezclan decisiones, protestas o anuncios distintos, una
diferencia aparente puede ser una diferencia factual legítima y no framing.

## Opciones para el corpus real (Paso 3)

### Fuentes verificadas como opciones

**Sitemaps propios: opción ya construida en `news-retrieval`.**

El repositorio local documenta y configura sitemaps mensuales para El Tiempo,
Noticias Caracol, Blu Radio, La República y Noticias RCN. También identifica
sitemaps Arc de El Espectador, Semana y W Radio, pero marca varios como
superficiales, no cuantificados o necesitados de respaldo. Cambio tiene un
sitemap index; RTVC está desactivado porque no se encontró un mecanismo de
`discovery` utilizable. Esta es la evidencia local más completa para el corpus
histórico y explica por qué el diseño eligió `SitemapProvider` sobre GDELT.

**RSS público: cobertura parcial y debe verificarse por medio.**

En una comprobación rápida del 2026-09-08, estas URLs devolvieron XML RSS
legible:

- El Tiempo: `https://www.eltiempo.com/rss/colombia.xml`, con título, fecha,
  enlace, categoría y descripción;
- La República: `https://www.larepublica.co/rss`, con título, fecha, enlace,
  categoría y descripción.

La URL probada `https://www.bluradio.com/rss.xml` devolvió 404. La URL probada
de Noticias Caracol (`https://www.noticiascaracol.com/rss.xml`) redirigió a un
endpoint de publicidad y no se pudo validar como feed. Eso no demuestra que
esos medios no tengan ningún feed alternativo; significa que su disponibilidad
no quedó verificada en esta exploración rápida. Para los feeds confirmados, el
contenido observado es de actualidad y no ofrece por sí solo un archivo
histórico completo.

**APIs de agregación: cobertura condicionada.**

La documentación oficial de NewsAPI confirma que `/v2/everything` permite
filtrar por `domains`, `language=es`, fechas, campos de búsqueda y páginas, y
que requiere una API key. También advierte que el campo `content` puede venir
truncado, hasta 200 caracteres en la documentación mostrada. Eso lo hace útil
para discovery y candidatos, pero insuficiente como fuente primaria del cuerpo
completo para segmentación y framing.

La documentación oficial consultada no permite afirmar sin una prueba con API
key que NewsAPI tenga cobertura estable de El Tiempo, Caracol, Blu Radio, La
República, RCN, El Espectador y Semana. Antes de adoptarlo habría que consultar
`/sources` y ejecutar búsquedas por dominio, idioma y ventanas de fecha,
registrando cuántos resultados son colombianos, cuántos son duplicados y si
apuntan al artículo original.

GDELT aparece en la configuración histórica como proveedor transversal futuro,
pero el código documenta que `GDELTProvider` sigue pendiente. Además, las
mediciones locales reportan dos riesgos: respuestas HTTP 200 con artículos
fuera de la ventana solicitada y solo 38% de consultas dentro del rango con
datos. Por eso no debe asumirse que GDELT resuelve el histórico sin validación
por fecha y sin reintentos explícitos.

### Rutas de recolección y trade-offs

| Ruta | Qué aporta | Qué se pierde o qué riesgo introduce | Encaje actual |
|---|---|---|---|
| **Búsqueda viva `web_search_20250305`** sobre varios temas y ampliando `n` | Ya funciona en `busqueda.py`; encuentra candidatos actuales sin construir conectores por medio; sirve para un piloto rápido de eventos recientes. | La selección puede cambiar entre corridas; no garantiza un mismo evento; el LLM resume y puede omitir estructura, citas o texto literal; `n` pequeño favorece descarte por verificación; no hay bitácora histórica de candidatos en el prototipo. | Buena para exploración y selección manual de eventos, no para un corpus histórico reproducible. |
| **RSS por medio, consultado periódicamente** | Feed estructurado con título, fecha, URL, categoría y a veces descripción; permite consistencia por fuente y frecuencia de captura; reduce dependencia de resultados cambiantes de un buscador. | Cobertura desigual: en la comprobación rápida solo quedaron confirmados El Tiempo y La República; el feed suele ser reciente y no resuelve el histórico; requiere implementar y mantener un proveedor por medio y descargar cada página para el cuerpo; un feed puede cambiar o desaparecer. | Viable como colector incremental de actualidad, no como sustituto directo del corpus histórico ya recolectado. |
| **API de agregación, como NewsAPI** | Consulta centralizada, filtros por dominio/idioma/fecha y paginación; puede acelerar discovery entre varios medios. | Requiere API key y verificar cobertura real; el contenido puede ser truncado; puede devolver republicaciones, snippets o fuentes no colombianas; añade dependencia de límites, planes y cambios del proveedor. | Útil como fuente auxiliar de candidatos si una prueba de cobertura confirma los dominios; no conviene tratarla como fuente del texto completo sin extracción desde la URL original. |
| **Sitemaps propios + extracción, ya usado por `news-retrieval`** | Discovery determinista por medio y mes; permite archivo histórico; guarda `discovery_record`, checkpoints, deduplicación, densidad de archivo y razones de descarte; extracción obtiene titular, fecha y cuerpo cuando la página aún lo ofrece. | Requiere peticiones por medio, rate limiting, mantenimiento de patrones de sitemap y extracción; disponibilidad histórica desigual; Blu Radio y Caracol tienen muchos artículos sin cuerpo largo en los períodos antiguos; todavía falta agrupar por evento y segmentar citas. | Es la base más reproducible para el histórico. Ya produjo el dump, pero necesita una etapa posterior de selección de eventos, segmentación y conexión con el análisis de framing. |
| **GDELT / Common Crawl / Wayback como respaldo** | Pueden cubrir huecos de medios Arc o períodos sin sitemap; Common Crawl puede recuperar HTML según la configuración local. | GDELT tiene fallos silenciosos medidos localmente; Common Crawl exige recuperar y limpiar WARC; Wayback es lento e inestable en consultas wildcard; la disponibilidad no equivale a comparabilidad. | Respaldo para huecos documentados, no ruta primaria sin validación por artículo. |

### Volumen realista para el curso

El dump demuestra que recolectar miles de artículos técnicos es posible, pero la
unidad de trabajo para framing es mucho más costosa: hay que asegurar que los
artículos cubren el mismo evento, revisar el cuerpo, segmentar y comprobar que
las diferencias no son hechos distintos.

Un rango conservador para el tiempo restante es:

- **8--12 eventos**;
- **3 medios por evento como mínimo**, idealmente **3--4** cuando el evento lo
  permita;
- aproximadamente **24--48 artículos principales**, más candidatos y descartes
  conservados en la bitácora;
- una muestra manual de calidad de cada evento antes de lanzar el análisis LLM.

Un piloto aún más pequeño de 6 eventos puede servir para probar el flujo y las
anotaciones, pero no debería presentarse como evidencia robusta de diferencias
entre medios. Intentar cubrir 20 años completos para todos los medios del
catálogo probablemente convierte la verificación y la segmentación en el cuello
de botella, aunque el discovery histórico ya tenga 17.202 filas.

### Pérdidas que deben quedar explícitas

- La búsqueda web pierde estabilidad de selección y trazabilidad de candidatos.
- RSS pierde archivo histórico, cuerpo completo y, según el medio, disponibilidad
  de citas o descripción más allá del feed.
- NewsAPI puede perder texto completo, medios locales no indexados y control
  sobre republicaciones; además introduce una clave y límites externos.
- Sitemaps pierden artículos que ya no existen, páginas de audio/video sin texto
  y períodos con archivo escaso; a cambio, dejan una observación reproducible de
  lo que el sitemap ofreció.
- GDELT puede perder confiabilidad temporal si no se valida `seendate`; Common
  Crawl y Wayback pueden perder cobertura uniforme o exigir recuperación y
  limpieza costosas.

### Preguntas que deben resolverse antes de implementar

1. ¿El objetivo inmediato es una demostración de framing sobre 8--12 eventos o
   ampliar el corpus histórico para análisis estadístico? Son productos distintos.
2. ¿Qué tres o cuatro medios se mantendrán constantes en la comparación? La
   consistencia entre medios importa más que agregar fuentes con cobertura
   incompleta.
3. ¿Se analizarán solo artículos con cuerpo de al menos 500 caracteres, y cómo
   se reportarán los artículos de audio/video excluidos?
4. ¿Qué unidad se anotará como evento: un identificador manual por equipo, una
   ventana temporal más tema, o una combinación de hecho, actores y lugar?
5. ¿Qué muestra manual se usará para evaluar los puntos calientes de divergencia,
   entidades y segmentación antes de confiar en los resultados del LLM?

La evidencia disponible favorece usar el corpus `news-retrieval` como base de
adquisición y trazabilidad, y limitar el siguiente experimento a un subconjunto
curado de eventos. Esto es una recomendación operativa para el diagnóstico, no
una decisión irreversible sobre la arquitectura del proyecto; RSS, una API o
GDELT pueden complementar huecos después de medir su cobertura real.
