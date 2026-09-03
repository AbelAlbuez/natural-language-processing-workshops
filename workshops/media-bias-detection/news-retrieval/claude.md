# CLAUDE.md — Historical News Corpus Service

## 1. Contexto del proyecto

Este repositorio contiene un servicio para construir un **corpus histórico de noticias de medios tradicionales colombianos**.

El servicio forma parte de un proyecto académico de **Procesamiento de Lenguaje Natural (NLP)**.

El objetivo final del proyecto es estudiar si existen diferencias sistemáticas en la forma en que distintos medios colombianos presentan, describen y enmarcan acontecimientos políticos dependiendo del gobierno nacional vigente.

Este servicio tiene como responsabilidad exclusiva construir un corpus histórico **limpio, estructurado, trazable y reproducible**.

El análisis de parcialización/bias será una etapa posterior y **NO debe implementarse como parte de este servicio**.

---

# 2. Objetivo general

Construir progresivamente un corpus histórico de noticias colombianas que permita posteriormente estudiar:

- diferencias en la cobertura de acontecimientos entre medios;
- diferencias en el lenguaje utilizado por cada medio;
- diferencias en el framing de acontecimientos;
- diferencias en la importancia que cada medio da a determinados temas;
- cambios en la cobertura de un mismo medio entre diferentes gobiernos;
- diferencias en la descripción de actores políticos;
- diferencias en el tono y posicionamiento utilizado;
- posibles patrones sistemáticos de parcialización.

El corpus debe permitir realizar comparaciones del tipo:

```text
Gobierno
    ↓
Período histórico
    ↓
Tema
    ↓
Acontecimiento
    ↓
Medio
    ↓
Artículo
```

La unidad fundamental de análisis será el **artículo de noticias**.

---

# 3. Qué entendemos por "parcialización"

Una decisión metodológica fundamental de este proyecto es:

> **No asumir que la parcialización de un medio puede medirse simplemente mediante análisis de sentimiento.**

Por ejemplo:

```text
sentimiento negativo = noticia contra el gobierno
sentimiento positivo = noticia a favor del gobierno
```

NO debe utilizarse como definición de bias.

El corpus debe ser diseñado para permitir posteriormente estudiar múltiples dimensiones.

Entre ellas:

### 3.1 Framing

Cómo un medio presenta un acontecimiento.

Por ejemplo:

```text
PROTESTA

Medio A:
"Manifestantes exigen cambios al gobierno"

Medio B:
"Disturbios afectan la movilidad de la ciudad"
```

El acontecimiento puede ser el mismo, pero el framing puede ser diferente.

---

### 3.2 Elección léxica

Analizar qué términos utiliza cada medio para describir:

- gobiernos;
- presidentes;
- partidos;
- opositores;
- manifestantes;
- instituciones;
- grupos armados;
- acontecimientos.

Ejemplo conceptual:

```text
"reforma"
vs.
"controvertida reforma"
vs.
"ambiciosa reforma"
vs.
"polémica reforma"
```

---

### 3.3 Entidades y actores

Analizar:

- qué personas aparecen;
- qué organizaciones aparecen;
- qué partidos aparecen;
- con qué frecuencia aparecen;
- qué actores aparecen asociados a determinados acontecimientos.

---

### 3.4 Omisiones y énfasis

Posteriormente podría estudiarse:

- qué aspectos de un acontecimiento reciben cobertura;
- qué aspectos reciben poco espacio;
- qué temas son enfatizados;
- qué actores son mencionados u omitidos.

El servicio de adquisición debe conservar suficiente metadata para permitir estos análisis posteriormente.

---

### 3.5 Tono

El tono puede estudiarse posteriormente como una dimensión adicional.

El análisis de sentimiento puede utilizarse eventualmente como **una característica más**, pero nunca debe considerarse por sí solo una medida de parcialización.

---

### 3.6 Posicionamiento

Posteriormente se puede estudiar si un medio presenta sistemáticamente:

- apoyo;
- crítica;
- neutralidad;
- cuestionamiento;

hacia determinados actores, gobiernos o políticas.

Esto debe quedar fuera del servicio de adquisición.

---

# 4. Principio metodológico principal

El corpus debe permitir comparar **cobertura comparable entre diferentes medios**.

No queremos simplemente:

```text
muchas noticias de El Tiempo
+
muchas noticias de Semana
+
muchas noticias de El Espectador
```

Queremos poder aproximarnos a:

```text
                    MISMO ACONTECIMIENTO
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
      El Tiempo         Semana        El Espectador
          │                │                │
          ↓                ↓                ↓
       framing          framing          framing
          │                │                │
          └────────────────┼────────────────┘
                           ↓
                    comparación NLP
```

Por lo tanto, el diseño debe conservar:

- fecha;
- medio;
- tema;
- URL;
- título;
- descripción;
- metadata;
- provenance;
- gobierno vigente;
- información suficiente para identificar posteriormente acontecimientos.

La identificación definitiva de acontecimientos puede realizarse en una etapa posterior.

---

# 5. Alcance temporal

El objetivo es construir aproximadamente **20 años de cobertura histórica**:

```text
2006 → 2026
```

La fecha exacta de inicio y finalización del corpus debe ser configurable.

El servicio debe permitir adquirir:

```text
2006
2007
2008
...
2025
2026
```

sin modificar la lógica del sistema.

---

# 6. Gobiernos

El corpus debe estar organizado por gobierno.

Inicialmente se estudiarán aproximadamente **cinco gobiernos consecutivos**, cubriendo aproximadamente 20 años.

Las fechas exactas deben validarse utilizando fuentes confiables y almacenarse como configuración/datos.

No hardcodear las fechas de los gobiernos dentro de la lógica del servicio.

Modelo conceptual:

```text
Government
├── id
├── president
├── start_date
├── end_date
└── metadata
```

Ejemplo:

```json
{
  "id": "government_x",
  "president": "President Name",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD"
}
```

Debe ser posible modificar los gobiernos sin modificar el código principal.

---

# 7. Medios

Inicialmente se trabajará con medios tradicionales colombianos.

Conjunto inicial:

- El Tiempo
- El Espectador
- Semana
- La República
- Noticias Caracol
- Noticias RCN
- W Radio
- Blu Radio
- Cambio
- RTVC

El listado debe ser configurable.

No asumir que todos los medios tienen la misma disponibilidad histórica.

Modelo conceptual:

```text
NewsSource
├── id
├── name
├── domain
├── country
├── language
├── source_type
└── active
```

---

# 8. Jerarquía temática

El corpus debe utilizar una jerarquía temática configurable.

Propuesta inicial:

```text
Política
├── Gobierno
├── Elecciones
├── Congreso
├── Partidos políticos
├── Oposición
└── Reformas

Economía
├── Inflación
├── Empleo
├── Impuestos
├── Presupuesto
├── Comercio
└── Economía nacional

Seguridad
├── Conflicto armado
├── Guerrillas
├── Grupos paramilitares
├── Narcotráfico
├── Seguridad ciudadana
└── Fuerzas militares

Sociedad
├── Protestas
├── Educación
├── Salud
├── Pobreza
└── Derechos humanos

Justicia
├── Corrupción
├── Procesos judiciales
├── Escándalos
└── Fiscalía

Relaciones internacionales
├── Venezuela
├── Estados Unidos
├── Relaciones diplomáticas
└── Política exterior

Medio ambiente
├── Cambio climático
├── Minería
├── Deforestación
└── Recursos naturales
```

Esta estructura es inicial y debe ser fácilmente modificable.

Cada tema debería poder tener:

```text
id
name
parent
keywords
aliases
active
```

Los términos utilizados para búsqueda deben poder modificarse mediante configuración.

---

# 9. Estrategia de adquisición

La adquisición debe ser **incremental y progresiva**.

No se debe diseñar el sistema alrededor de una ejecución gigante como:

```text
2006–2026
×
10 medios
×
todos los temas
```

en una sola operación.

En cambio, el corpus debe construirse mediante unidades pequeñas:

```text
government
+
source
+
topic
+
date_range
```

Por ejemplo:

```text
2008
El Tiempo
Política
enero-marzo
```

Después:

```text
2008
El Tiempo
Política
abril-junio
```

y así sucesivamente.

La granularidad exacta debe determinarse después de estudiar las capacidades y límites del proveedor seleccionado.

---

# 10. Reanudación y checkpoints

El sistema debe ser capaz de reanudar una adquisición interrumpida.

Debe poder responder:

```text
¿Qué períodos ya descargué?
¿Qué medios?
¿Qué temas?
¿Qué proveedor?
¿Cuántos artículos?
¿Cuántos errores?
```

Estados posibles:

```text
PENDING
RUNNING
COMPLETED
FAILED
PARTIAL
```

Una operación completada exitosamente no debe ejecutarse nuevamente innecesariamente.

---

# 11. Arquitectura general

La arquitectura debe separar claramente:

```text
                  NEWS PROVIDERS
                       │
          ┌────────────┼────────────┐
          │            │            │
        GDELT       NewsAPI        RSS
          │            │            │
          └────────────┼────────────┘
                       ↓
                   DISCOVERY
                       ↓
                  NORMALIZATION
                       ↓
                ARTICLE EXTRACTION
                       ↓
                   VALIDATION
                       ↓
                 DEDUPLICATION
                       ↓
                    STORAGE
                       ↓
                      API
                       ↓
                    CORPUS
```

La implementación concreta queda a criterio de Claude.

Debe utilizar una arquitectura basada en adapters/interfaces para que los providers puedan reemplazarse.

---

# 12. Research previo obligatorio

**Antes de realizar una implementación significativa, Claude debe investigar y presentar una propuesta técnica.**

Esto es especialmente importante debido al requisito de aproximadamente 20 años de datos históricos.

La primera tarea de Claude debe ser:

### 12.1 Inspeccionar el repositorio

Analizar:

```text
https://github.com/jctp94/FinSage
```

Identificar:

- lenguaje utilizado;
- estructura;
- patrones reutilizables;
- manejo de configuración;
- persistencia;
- APIs;
- testing;
- logging;
- patrones que puedan ser útiles.

FinSage es una referencia, no una restricción.

---

### 12.2 Investigar proveedores

Evaluar como mínimo:

- GDELT;
- NewsAPI;
- RSS;
- otras fuentes que resulten relevantes.

Para cada provider evaluar:

```text
Cobertura temporal
Cobertura de medios colombianos
Metadata disponible
Texto completo disponible
API pública
Necesidad de API key
Límites
Rate limits
Paginación
Costo
Licenciamiento
Términos de uso
Estabilidad
Reproducibilidad
```

**No asumir que una API que ofrece noticias actualmente permite recuperar 20 años de historia.**

La cobertura histórica debe ser verificada explícitamente.

---

### 12.3 Evaluar los medios

Para cada medio objetivo investigar:

```text
¿Existe en el provider?
¿Cuál es su dominio?
¿Qué cobertura histórica existe?
¿Desde qué año aproximadamente?
¿La metadata es suficiente?
¿Se puede recuperar el artículo?
```

El resultado debe permitir detectar temprano medios o períodos con poca cobertura.

---

# 13. Provider histórico

GDELT debe ser evaluado seriamente como candidato a proveedor histórico principal.

NewsAPI puede utilizarse como complemento si resulta útil para discovery o validación.

RSS puede utilizarse para fuentes que proporcionen feeds adecuados.

Sin embargo:

**No implementar la arquitectura suponiendo que un único provider tendrá toda la cobertura.**

La arquitectura debe permitir combinar providers.

Por ejemplo:

```text
GDELT
   ↓
histórico

NewsAPI
   ↓
complemento

RSS
   ↓
fuentes específicas
```

---

# 14. Modelo común de Article

Todos los providers deben producir un modelo común.

Como mínimo:

```text
Article
├── id
├── title
├── description
├── author
├── url
├── source
├── published_at
├── language
├── topic
├── government
├── discovered_at
└── provider
```

Campos opcionales:

```text
subtitle
section
image_url
canonical_url
retrieved_at
content
content_hash
raw_data
```

La primera versión debe priorizar:

```text
metadata + URL + provenance
```

sobre garantizar inmediatamente texto completo perfecto.

---

# 15. Discovery vs Content Extraction

Separar explícitamente:

```text
ARTICLE DISCOVERY
```

de:

```text
ARTICLE CONTENT EXTRACTION
```

Un provider puede proporcionar:

```text
title
url
description
published_at
```

sin proporcionar el artículo completo.

La arquitectura debe permitir posteriormente:

```text
discovered article
        ↓
article URL
        ↓
content extractor
        ↓
full text
```

Conceptualmente:

```python
class ArticleExtractor:
    def extract(url)
```

La implementación concreta queda a criterio de Claude.

---

# 16. Normalización

Todos los providers deben transformarse a un modelo común.

Pipeline:

```text
Provider Result
      ↓
Raw Model
      ↓
Normalization
      ↓
NewsArticle
```

Normalizar:

- fechas;
- URLs;
- nombres de medios;
- idioma;
- whitespace;
- Unicode;
- campos opcionales.

No eliminar información original innecesariamente.

Cuando sea viable conservar:

```text
raw_data
+
normalized_data
```

---

# 17. Deduplicación

La deduplicación es obligatoria.

Un artículo puede aparecer:

- en múltiples queries;
- en múltiples páginas;
- en múltiples providers;
- con diferentes variantes de URL;
- mediante syndication.

Utilizar como mínimo:

```text
canonical URL
```

y, cuando sea necesario:

```text
source
+
normalized title
+
published date
```

También puede utilizarse un hash del contenido disponible.

No eliminar automáticamente artículos solamente porque tengan títulos similares.

---

# 18. Provenance

Cada artículo debe conservar información suficiente para reconstruir su origen.

Debe ser posible responder:

```text
¿De dónde salió?
¿Qué provider lo encontró?
¿Cuándo?
¿Qué query produjo el resultado?
¿Qué medio?
¿Qué fecha?
¿Qué tema?
¿Qué gobierno?
```

Ejemplo conceptual:

```json
{
  "provider": "gdelt",
  "query": "...",
  "retrieved_at": "...",
  "source_domain": "...",
  "source_url": "..."
}
```

La provenance no debe perderse durante la normalización.

---

# 19. Rate limiting y resiliencia

Implementar:

- rate limiting;
- retries;
- exponential backoff;
- timeouts;
- manejo de errores HTTP;
- logging;
- mecanismos de recuperación.

Respetar:

- límites de APIs;
- robots.txt cuando corresponda;
- términos de servicio;
- políticas de cada fuente.

No implementar scraping agresivo.

---

# 20. Configuración

No hardcodear:

- API keys;
- medios;
- fechas;
- gobiernos;
- temas;
- keywords;
- límites;
- URLs de providers.

Utilizar configuración externa.

Ejemplo conceptual:

```text
.env
config/
    sources.yaml
    governments.yaml
    topics.yaml
```

Agregar:

```text
.env.example
```

Nunca almacenar credenciales en Git.

---

# 21. API

La implementación debe exponer una API que permita consultar el corpus y controlar jobs.

Conceptualmente:

```text
GET /articles
GET /articles/{id}

GET /sources
GET /governments
GET /topics

GET /corpus/status

POST /jobs
GET /jobs/{id}
```

Debe ser posible filtrar por:

```text
source
government
topic
date range
provider
```

Ejemplo conceptual:

```text
GET /articles?
    source=el_tiempo
    &government=...
    &topic=politics
    &from=2010-01-01
    &to=2010-12-31
```

Los endpoints y framework quedan a criterio de Claude.

---

# 22. CLI

Se recomienda proporcionar una CLI para ejecutar adquisiciones.

Ejemplo:

```bash
news-corpus collect \
  --source el_tiempo \
  --topic politics \
  --from 2008-01-01 \
  --to 2008-03-31
```

También debería ser posible consultar:

```bash
news-corpus status
```

y reintentar:

```bash
news-corpus retry-failed
```

Los nombres exactos quedan a criterio de Claude.

---

# 23. Storage

Seleccionar una solución de persistencia adecuada para:

- miles/millones de artículos;
- consultas por fecha;
- consultas por medio;
- consultas por gobierno;
- consultas por tema;
- deduplicación;
- checkpoints.

La decisión técnica queda a criterio de Claude.

Priorizar:

```text
simplicidad
+
reproducibilidad
+
costo
+
escalabilidad suficiente
+
facilidad de análisis NLP
```

No introducir infraestructura distribuida innecesaria.

---

# 24. Exportación

Debe existir una forma sencilla de exportar el corpus para análisis NLP.

Preferentemente:

```text
JSONL
CSV
Parquet
```

El dataset debe conservar:

```text
article_id
title
description
author
url
source
published_at
government
topic
provider
```

además de los campos disponibles.

---

# 25. Corpus inicial

El objetivo final es:

```text
~2006–2026
×
5 gobiernos
×
10 medios
×
múltiples temas
```

Pero la primera entrega académica solamente necesita un corpus pequeño.

Por ejemplo:

```text
3–5 medios
×
2–3 gobiernos
×
2–3 temas
×
período limitado
```

Debe demostrar:

```text
Discovery
    ↓
Normalization
    ↓
Validation
    ↓
Deduplication
    ↓
Storage
    ↓
Export
```

El mismo pipeline deberá poder ejecutarse posteriormente para completar progresivamente los 20 años.

---

# 26. Reproducibilidad

Cada adquisición debe registrar:

```text
provider
query
date range
source
topic
execution timestamp
number of results
number of new articles
number of duplicates
number of failures
```

Esto es especialmente importante porque el proyecto es académico.

El equipo debe poder explicar posteriormente cómo se construyó cualquier subconjunto del corpus.

---

# 27. Testing

Crear tests para:

### Providers

```text
search
pagination
mapping
error handling
```

### Normalization

```text
dates
URLs
sources
missing fields
```

### Deduplication

```text
same URL
canonical URL
same article from different providers
```

### Jobs

```text
checkpoint
resume
failure
retry
```

### Configuration

```text
sources
topics
governments
```

---

# 28. Docker

Si resulta conveniente, proporcionar:

```text
Dockerfile
docker-compose.yml
```

La implementación debe evitar dependencias innecesarias.

---

# 29. Relación con FinSage

Existe un proyecto previo:

```text
https://github.com/jctp94/FinSage
```

Debe utilizarse como referencia para identificar:

- patrones útiles;
- experiencia previa;
- soluciones conocidas;
- convenciones que puedan reutilizarse.

Sin embargo:

> **No copiar la arquitectura de FinSage automáticamente.**

Este proyecto tiene requerimientos diferentes:

- 20 años de datos;
- múltiples medios;
- múltiples providers;
- adquisición incremental;
- provenance;
- deduplicación;
- gobiernos;
- temas;
- corpus NLP.

FinSage es una referencia, no una restricción.

---

# 30. Decisiones de negocio que Claude NO debe cambiar

Las siguientes decisiones pertenecen al equipo:

### País

```text
Colombia
```

### Horizonte

```text
aproximadamente 2006–2026
```

### Gobiernos

```text
cinco gobiernos consecutivos aproximadamente
```

### Medios iniciales

```text
El Tiempo
El Espectador
Semana
La República
Noticias Caracol
Noticias RCN
W Radio
Blu Radio
Cambio
RTVC
```

### Adquisición

```text
incremental / progresiva
```

### Organización

```text
gobierno
+
medio
+
tema
+
fecha
```

### Objetivo

```text
construir un corpus que permita posteriormente
estudiar diferencias de cobertura, framing y
posible parcialización
```

### Separación

```text
adquisición ≠ análisis de bias
```

---

# 31. Decisiones técnicas que Claude SÍ puede tomar

Claude puede decidir:

- framework;
- ORM;
- database;
- estructura de módulos;
- nombres de clases;
- nombres de endpoints;
- estrategia de caching;
- retries;
- librerías de extracción;
- sistema de migrations;
- formato interno;
- Docker;
- testing framework;
- estrategia de paginación;
- implementación de adapters.

Siempre que respete las decisiones metodológicas de este documento.

---

# 32. Lo que NO se debe implementar todavía

No implementar en este servicio:

```text
❌ clasificación automática de bias
❌ clasificación izquierda/derecha de medios
❌ análisis de sentimiento como indicador de bias
❌ embeddings
❌ clustering definitivo de acontecimientos
❌ modelos LLM para detectar parcialización
❌ análisis causal
❌ conclusiones sobre qué medio es más parcializado
```

Estas funcionalidades pertenecen a etapas posteriores.

---

# 33. Primera fase obligatoria: Research & Architecture

Antes de implementar una cantidad significativa de código, Claude debe producir un documento/propuesta que contenga:

## A. Análisis de FinSage

Qué componentes pueden reutilizarse conceptualmente.

## B. Comparación de providers

Tabla comparando:

```text
Provider
Historical coverage
Colombian media coverage
Metadata
Full text
API key
Rate limits
Cost
Reliability
```

## C. Cobertura de medios

Determinar qué tan bien puede cubrirse cada uno de los diez medios.

## D. Arquitectura propuesta

Presentar:

```text
providers
domain model
database
jobs
API
CLI
configuration
storage
```

## E. Estrategia histórica

Explicar cómo se descargarán aproximadamente 20 años de información sin depender de una sola ejecución.

## F. Riesgos

Identificar:

- gaps históricos;
- artículos eliminados;
- cambios de dominio;
- paywalls;
- cambios de estructura web;
- límites de APIs;
- duplicados;
- cambios en nombres de medios;
- problemas de disponibilidad histórica.

## G. Plan de implementación

Dividir el trabajo en fases pequeñas.

**No comenzar una implementación masiva hasta haber completado este análisis.**

---

# 34. Prioridad de implementación

## Fase 1 — Research

```text
provider research
FinSage analysis
media coverage analysis
architecture proposal
```

## Fase 2 — Foundation

```text
project
configuration
models
database
logging
```

## Fase 3 — Historical Provider

```text
provider
search
pagination
rate limits
retries
```

## Fase 4 — Normalization

```text
common model
dates
URLs
source mapping
```

## Fase 5 — Deduplication

```text
canonical URL
hash
normalized title
```

## Fase 6 — Incremental Jobs

```text
collection
checkpoints
resume
retry
```

## Fase 7 — API / CLI

```text
queries
jobs
status
export
```

## Fase 8 — Additional Providers

```text
NewsAPI
RSS
other providers if necessary
```

## Fase 9 — Content Extraction

```text
article extraction
full text
content validation
```

No implementar todas las fases simultáneamente.

---

# 35. Definition of Done — MVP

La primera versión se considera terminada cuando sea posible:

1. Configurar un medio.
2. Configurar un gobierno.
3. Configurar un tema.
4. Definir un rango de fechas.
5. Ejecutar una búsqueda histórica.
6. Obtener artículos.
7. Normalizar metadata.
8. Validar resultados.
9. Deduplicar.
10. Persistir artículos.
11. Registrar provenance.
12. Reanudar una descarga.
13. Consultar el estado del corpus.
14. Exportar los artículos.
15. Ejecutar tests básicos.
16. Documentar la ejecución end-to-end.

Debe existir un ejemplo reproducible:

```text
configuration
      ↓
provider
      ↓
discovery
      ↓
normalization
      ↓
validation
      ↓
deduplication
      ↓
storage
      ↓
export
```

---

# 36. Principio de calidad

Priorizar:

```text
REPRODUCIBILIDAD
        >
TRAZABILIDAD
        >
COMPARABILIDAD
        >
COMPLETITUD
        >
VELOCIDAD
```

Es preferible tener:

```text
10.000 artículos
```

correctamente identificados, estructurados y trazables que:

```text
100.000 artículos
```

con duplicados, metadata inconsistente y poca información sobre su origen.

---

# 37. Principio final

Este proyecto **no es simplemente un scraper de noticias**.

Es una infraestructura reproducible para construir un **corpus histórico de noticias colombianas** que permita posteriormente realizar análisis de NLP comparables entre:

```text
                 MEDIOS
                    ×
                GOBIERNOS
                    ×
                  TEMAS
                    ×
              ACONTECIMIENTOS
                    ×
                  TIEMPO
```

El servicio debe concentrarse en producir datos de alta calidad.

La interpretación de esos datos y la definición operacional de parcialización serán responsabilidades de una etapa posterior del proyecto.

En particular:

> **No debemos construir el dataset suponiendo de antemano cómo se mide el bias.**

Debemos construirlo de manera que permita evaluar distintas hipótesis sobre parcialización mediante:

```text
framing
+
elección léxica
+
entidades
+
énfasis temático
+
omisión
+
tono
+
posicionamiento
+
otras características NLP
```

El corpus debe ser lo suficientemente rico y estructurado para que esas decisiones metodológicas puedan tomarse posteriormente con evidencia.
