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

- `agentes.py` — los 4 agentes de análisis/síntesis, cada uno con system
  prompt que exige JSON estricto: `verificar_mismo_evento`,
  `analizar_lexico_framing`, `analizar_actores_citas`,
  `analizar_estilo_enfasis`, `sintetizar_reporte`.
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

- El agente de estilo/énfasis (`analizar_estilo_enfasis`) hoy pide una
  estimación **cualitativa** al modelo. Es una simplificación temporal: la
  versión correcta debe reemplazarla por métricas cuantitativas reales
  (`textstat`, `textdescriptives`) reutilizadas del Taller 1, no preguntarle
  al LLM.
- Sin framework de orquestación (LangGraph/CrewAI): con 4-5 agentes
  secuenciales no se justifica la complejidad adicional.
- El verificador puede descartar medios explícitamente
  (`medios_descartados`); el orquestador respeta ese descarte en vez de
  forzar el análisis con fuentes no verificadas.

## Pendientes

- Reemplazar la estimación cualitativa de estilo/énfasis por métricas
  cuantitativas (textstat/textdescriptives).
- Probar `buscar_noticias_actuales` con varios temas reales y evaluar la
  consistencia del JSON devuelto por el modelo.
- Evaluar si conviene subir `N_MEDIOS_BUSQUEDA` (hoy 2) a 3-4 para tener más
  robustez frente a medios descartados por el verificador.
