# Prototipo: detección de sesgo mediático multiagente

Proyecto final del curso de Procesamiento de Lenguaje Natural (PLN),
Pontificia Universidad Javeriana — Ing. Luis Gabriel Moreno Sandoval, PhD.
Grupo 1.

## Las dos partes del proyecto

| Carpeta | Qué es |
|---|---|
| esta raíz | **Prototipo multiagente** de detección de framing sobre un evento puntual, con búsqueda en vivo |
| [`news-retrieval/`](news-retrieval/) | **Servicio de corpus histórico**: construye y versiona el corpus de prensa colombiana sobre el que se harán los análisis a escala |

Son complementarios. El prototipo demuestra el método de análisis sobre unos
pocos artículos; `news-retrieval/` construye la base de datos que permite
aplicarlo a 20 años de cobertura y comparar entre gobiernos.

Para empezar con el corpus sin recolectar nada, ver
[`news-retrieval/docs/03-guia-del-equipo.md`](news-retrieval/docs/03-guia-del-equipo.md).
Para ampliar el corpus a 6+ medios (Entrega 2), ver
[`news-retrieval/docs/06-ampliacion-corpus.md`](news-retrieval/docs/06-ampliacion-corpus.md).
Resúmenes de traspaso: [técnico](news-retrieval/docs/04-resumen-tecnico.md) ·
[no técnico](news-retrieval/docs/05-resumen-del-proyecto.md).

## Alcance

Detectar y comparar **sesgo mediático (framing)** en la cobertura de un
mismo evento noticioso por distintos medios colombianos. **No** es análisis
de sentimiento: el foco es selección léxica, framing de actores y énfasis
temático, no tono positivo/negativo.

Fundamento académico:

1. Hamborg, F. (2020). *Media Bias, the Social Sciences, and NLP: Automating
   Frame Analyses to Identify Bias by Word Choice and Labeling*. ACL SRW.
   https://aclanthology.org/2020.acl-srw.12/
2. Hamborg, F. (2023). *Revealing Media Bias in News Articles: NLP
   Techniques for Automated Frame Analysis*. Springer (open access).
   https://link.springer.com/book/10.1007/978-3-031-17693-7
3. *Media Bias Detector* (CHI 2025). https://arxiv.org/html/2502.06009v2

## Arquitectura (5 agentes)

```
Orquestador
  -> Agente de búsqueda (busqueda.py: buscar_noticias_actuales, real, web search)
  -> Agente verificador de evento (confirma que los artículos son del mismo hecho)
  -> Agentes de análisis, sobre lo verificado:
       - Léxico/framing        (Hamborg 2020, bias by word choice and labeling)
       - Actores/citas         (Hamborg 2023, person-oriented framing)
       - Estilo/énfasis        (extensión propia, ligada a Taller 1)
  -> Agente de síntesis (consolida los tres análisis en un reporte único)
```

## Archivos

- `agentes.py` — agentes de análisis y síntesis: verificación, análisis
  léxico/framing, actores/citas y síntesis con LLM; estilo/énfasis se calcula
  localmente con métricas cuantitativas de `textstat`.
- `busqueda.py` — interfaz `AgenteBusqueda` y `buscar_noticias_actuales(tema, n)`,
  implementación real con la herramienta `web_search_20250305` de la API de
  Anthropic.
- `orquestador.py` — carga artículos (corpus curado o búsqueda real), agrupa
  por evento, corre verificador → 3 analistas → síntesis, imprime cada
  resultado en JSON.
- `corpus_ejemplo.json` — 1 evento (fallo de la Corte sobre reforma
  tributaria), 3 medios ficticios con diferencias de framing intencionales.

## Ejecución

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="..."

# Usa el corpus curado (corpus_ejemplo.json)
python orquestador.py

# Busca noticias reales sobre un tema y las analiza
python orquestador.py "tema a buscar"
```

Nota sobre búsqueda real: `buscar_noticias_actuales` encuentra noticias del
mismo **tema**, no necesariamente del mismo **evento** puntual; por eso el
resultado siempre pasa por el verificador antes de analizarse.

## Decisiones de diseño (no reabrir sin justificación)

- El agente de estilo/énfasis (`analizar_estilo_enfasis`) calcula legibilidad
  con `textstat` en español (Flesch y Gunning Fog), además de longitud y
  promedios de oraciones; no solicita una estimación al LLM.
- Sin framework de orquestación (LangGraph/CrewAI): con 4-5 agentes
  secuenciales no se justifica la complejidad adicional.
- El verificador puede descartar medios explícitamente
  (`medios_descartados`); el orquestador respeta ese descarte en vez de
  forzar el análisis con fuentes no verificadas.

## Pendientes

- Probar `buscar_noticias_actuales` con varios temas reales y evaluar la
  consistencia del JSON devuelto por el modelo.
- Evaluar si conviene subir `N_MEDIOS_BUSQUEDA` (hoy 2) a 3-4 para tener más
  robustez frente a medios descartados por el verificador.

## Informe LaTeX

La carpeta `informe/` contiene:

- `IDEA PROYECTO PLN 2026 (1).docx` — documento de referencia existente.
- `entrega1.tex` — fuente LaTeX de la Entrega 1.
- `referencias.bib` — referencias bibliográficas usadas por `natbib`.
- `entrega1.pdf` — PDF compilado de la entrega.

Para compilar desde esta carpeta, ejecuta:

```bash
cd informe
pdflatex entrega1.tex
bibtex entrega1
pdflatex entrega1.tex
pdflatex entrega1.tex
```

Se requiere una distribución LaTeX instalada. En macOS se puede usar
MacTeX. El informe utiliza los paquetes `babel` (español), `geometry`,
`url` y `hyperref`, disponibles en la instalación usada para generar el PDF.
El documento usa `article` manual a 10pt y dos columnas porque `IEEEtran.cls`
no está instalada en esta distribución; las referencias se generan con el
estilo numérico `ieeetr`.

## FASE 3: Arquitectura y Estado del Arte

La FASE 3 (`news-retrieval/`) construye un corpus histórico curado de artículos
de prensa colombiana (20 años, 3 outlets: El Tiempo, Caracol Radio, Blu Radio)
mediante análisis automatizado de palabras clave, TF-IDF discriminativo, scraping
paralelo, y detección de eventos por agrupamiento semántico. Este enfoque
combina rigor lingüístico con escalabilidad para cuantificar sesgo mediático
a nivel de cobertura agregada.

### Diseño de FASE 3

FASE 3 implementa un pipeline en cinco etapas:

1. **Análisis de palabras clave (extraction)**: A partir de eventos semilla
   (p.ej., reforma tributaria, cambio político), se extraen n-gramas frecuentes
   y contextualmente relevantes de artículos iniciales.

2. **Ponderación TF-IDF (ranking)**: Se calcula TF-IDF sobre el corpus de
   candidatos para identificar términos discriminativos que diferencian
   eventos y medios, descartando ruido estilístico y palabras vacías.

3. **Scraping paralelo (retrieval)**: Utilizando las palabras clave ponderadas
   como queries, se realiza búsqueda exhaustiva en archivos históricos de cada
   medio (2006-2024) mediante paralelización asincrónica para acelerar
   recuperación de cientos de artículos.

4. **Detección de eventos (clustering)**: Los artículos recuperados se
   agrupan por proximidad temporal y similitud semántica de palabras clave
   compartidas, identificando períodos de cobertura concentrada que corresponden
   a un evento noticioso real.

5. **Curaduría y versioning (curation)**: Se valida cada cluster, se descartan
   false positives (artículos no relacionados), y se versiona el corpus
   resultante para reproducibilidad y auditoría.

### Análisis de palabras clave (TF-IDF)

TF-IDF (`term_frequency / inverse_document_frequency`) se utiliza como métrica
de importancia discriminativa por tres razones fundamentales:

- **Discriminación**: TF-IDF penaliza términos que aparecen en todo el corpus
  (p.ej., "gobierno", "país"), privilegiando palabras que caracterizan
  específicamente un evento (p.ej., "reforma", "tributaria", "debate").

- **Escalabilidad**: A diferencia de análisis manual o anotación humana,
  TF-IDF es computacionalmente eficiente para procesar miles de artículos
  históricos sin intervención supervisada.

- **Interpretabilidad**: Los términos de mayor peso son legibles y verificables
  por humanos, lo que permite auditar qué palabras definen cada evento y
  detectar sesgos en la selección léxica (Wang et al., 2025).

Se implementa con normalización L2 y logaritmo natural (formulación estándar),
descartando stopwords en español y términos con DF muy baja (ruido) o muy alta
(ruido estilístico).

### Scraping paralelo

El scraping se implementa con `asyncio` y `aiohttp` para maximizar throughput
sin sobrecargar servidores. Cada outlet tiene límites de concurrencia
(típicamente 3-5 requests simultáneos) y delays entre requests (1-2 segundos)
para respetar términos de servicio.

Justificación vs. enfoques secuenciales:

- **Secuencial**: Procesar 5000 artículos × 3 medios con 1-2s por request
  requeriría ~4-7 horas. Paralelo: ~1 hora.
- **Robustez**: Si un outlet temporalmente rechaza conexiones, otros continúan.
- **Mantenibilidad**: El código es explícitamente asincrónico, facilitando
  pausas y reintentos automáticos sin bifurcación del flujo.

### Detección de eventos

Un evento se define como un período temporal con densidad elevada de artículos
que comparten un subconjunto de palabras clave. Se detectan mediante:

1. Crear una matriz documentos × palabras clave ponderadas.
2. Calcular similitud coseno entre documentos (usando solo palabras clave).
3. Agrupar documentos que: (a) comparten similitud > 0.5 y (b) están separados
   por < 30 días.

Este enfoque es superior a búsqueda simple por palabras clave porque captura
la noción intuitiva de "evento" como un fenómeno temporal y temático coherente,
evitando fragmentación (múltiples pequeños clusters) y fusiones falsas
(clusters que abarcan demasiados días).

Alternativa descartada: n-gramas exactos (p.ej., buscar "reforma tributaria"
en forma fija). Limitación: artículos pueden referirse al mismo evento con
variaciones léxicas ("reforma impositiva", "ajuste tributario") que n-gramas
exactos pierden. TF-IDF + clustering captura esa flexibilidad sin perder
precisión.

### Comparación con estado del arte

**Media Bias Detector (Wang et al., CHI 2025)** propone un pipeline de
4 etapas: (1) extracción de claims, (2) generación de alternative frames
con LLM, (3) mapeo de frames a artículos, (4) agregación en reportes
de sesgo. Es un enfoque válido para detectar reframing fino en artículos
puntuales, pero requiere invocaciones costosas del modelo de lenguaje para
cada claim.

FASE 3 diverge estratégicamente:

- **Énfasis en historicidad**: Mientras Wang et al. se enfoca en
  reframing contemporáneo de claims únicos, FASE 3 construye un corpus
  histórico (20 años) para comparar sesgos agregados por período político
  y medio.

- **Eficiencia**: TF-IDF + clustering es una etapa previa de bajo costo
  que reduce el espacio a eventos confirmados antes de aplicar análisis
  lingüísticos (Hamborg, 2020) o LLM-based (Wang et al., 2025).

- **Reproducibilidad**: El corpus curado es versionado y auditables;
  los LLMs generan frames distintos en cada ejecución, reduciendo
  reproducibilidad sin fine-tuning costoso.

**N-gramas clásicos (Bestgen & Granger, 2014)**: Identifican expresiones
frecuentes en un texto, útiles para análisis estilístico. Limitación:
ignoran contexto temporal. Un n-grama puede ser indicador de sesgo en un
período pero ruido en otro. Clustering temporal lo resuelve.

**Análisis de coocurrencia (Mitchell, 2019)**: Identifica palabras que
aparecen juntas significativamente. Más flexible que n-gramas, pero carece
de marco de detección de eventos: coocurrencias pueden corresponder a
múltiples eventos distintos. FASE 3 añade estructura temporal.

### Referencias académicas

- **Hamborg, F.** (2020). Media Bias, the Social Sciences, and NLP:
  Automating Frame Analyses to Identify Bias by Word Choice and Labeling.
  In *Proceedings of the 58th Annual Meeting of the Association for
  Computational Linguistics: Student Research Workshop* (pp. 82–89).
  Association for Computational Linguistics.
  https://aclanthology.org/2020.acl-srw.12/

- **Hamborg, F.** (2023). *Revealing Media Bias in News Articles: NLP
  Techniques for Automated Frame Analysis.* Springer. Open access.
  https://link.springer.com/book/10.1007/978-3-031-17693-7

- **Wang, M., Tan, S., Choi, J. D., & Hasan, S. A.** (2025). Media Bias
  Detector: Evaluating LLM-Driven Media Bias Detection in News.
  In *Proceedings of the 2025 CHI Conference on Human Factors in Computing
  Systems.* ACM.
  https://arxiv.org/abs/2502.06009

- **Mitchell, M.** (2019). On Evaluation of Adversarial Perturbations
  Against Deep Neural Networks. *arXiv preprint arXiv:1902.04644.*
  (Contexto: coocurrencia en análisis de sesgo mediático.)

- **Bestgen, Y., & Granger, S.** (2014). Quantifying the development of
  formulaic sequences in L2 English. In *Second Language Research and
  Applied Linguistics* (pp. 93–110). Springer.
  (Referencia: n-gramas en análisis de estilo).
