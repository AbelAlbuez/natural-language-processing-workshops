# Propuestas de investigación

Fecha: 2026-10-26. Base empírica: `docs/analisis_corpus.md` (hallazgos H1–H7) y `docs/analisis_corpus.json`. Las secciones del enunciado se refieren a los puntos 1–8 de `docs/EVALUACION.md`.

Los umbrales de cada hipótesis son propuestas. Hay que fijarlos con el conjunto de desarrollo **antes** de medir en test (punto 1 del enunciado) y reportarlos con intervalos y al menos 3 repeticiones (punto 5).

## Resumen

| # | Pregunta | Hallazgo de origen | Puntos del enunciado |
|---|---|---|---|
| PI1 | ¿e5-small recupera evidencia en inglés para consultas en español con la misma calidad? | H1 | 1, 4, 6 |
| PI2 | ¿La mezcla de posts cortos y fragmentos de artículos sesga la recuperación por plataforma, y la recuperación híbrida o el reranking lo corrigen? | H2, H3 | 3, 4, 6 |
| PI3 | ¿Cómo definir la propagación noticia → red: similitud de texto o URL compartida? | H4, H5 | 6, 8 |
| PI4 | ¿Una compuerta de abstención basada en la recuperación mejora las respuestas a preguntas sin evidencia y temporales? | H3, H4 | 1, 4 |
| PI5 | Con la recuperación fija, ¿qué modelo pequeño da la mejor relación entre fidelidad y costo en un corpus bilingüe? | H1 | 3, 4, 5, 8 |

## PI1. Recuperación cruzada español → inglés

**Contexto.** El 55,99 % del corpus está en inglés, y el 90,05 % de Bluesky también (H1). Un usuario que pregunta en español necesita evidencia que muchas veces está en inglés.

| Elemento | Propuesta |
|---|---|
| Hipótesis refutable | Con `multilingual-e5-small`, para preguntas cuya evidencia relevante está en inglés, Recall@10 de la versión en español de la pregunta es al menos 10 puntos menor que el de la versión en inglés. Se refuta si el IC 95 % de la diferencia incluye 0 o queda por debajo de 10 puntos. |
| Medición | Subconjunto del gold con cada pregunta escrita en `es` y en `en`, con los mismos documentos relevantes anotados. Recall@k, MRR y nDCG@10 por par (idioma de la pregunta × idioma de la evidencia). IC por bootstrap pareado sobre las preguntas. |
| Puntos del enunciado | 1 (diversidad de idiomas), 4 (métricas de recuperación), 6 (sesgos) |
| Riesgo principal | Pocas preguntas cruzadas. Las cuotas de la celda 7 dan solo 1 pregunta `bluesky/es`, y el IC sería muy ancho. |
| Mitigación | Construir el subconjunto pareado aparte de las 40 preguntas (por ejemplo, 15 pares traducidos y revisados por un segundo anotador) y declarar el tamaño. Esto no consume preguntas de test. |

## PI2. Sesgo por plataforma: posts cortos frente a fragmentos de artículos

**Contexto.** Bluesky no pasa de 67 palabras. *Hipótesis (pendiente de medir con el tokenizador de e5-small):* con un máximo de 67 palabras, se espera que cada post quepa en un chunk de 256 tokens. Un artículo de `media_cloud` tiene una mediana de 636 palabras, así que se espera que ocupe varios chunks (H2). Prensa y Bluesky solo coinciden en el tiempo en 2025–2026 (H3).

| Elemento | Propuesta |
|---|---|
| Hipótesis refutable | Con recuperación densa (e5-small, `rag_e5s_tok256_v1`), la proporción de chunks de Bluesky en el top-10 difiere en más de 15 puntos de su proporción entre los relevantes anotados. La recuperación híbrida (BM25 + densa con RRF), con o sin un reranker, reduce esa diferencia a la mitad sin bajar nDCG@10. Se refuta si la diferencia inicial no supera los 15 puntos, o si la híbrida no la reduce. |
| Medición | Por pregunta: proporción por fuente en el top-k frente a la proporción por fuente de los relevantes. nDCG@10 y Recall@10 por fuente. Tres condiciones: densa, híbrida y híbrida + reranker, con el mismo índice, chunking y k (punto 3). |
| Puntos del enunciado | 3 (no confundir cambios de recuperación con cambios del LLM), 4, 6 (sesgos por plataforma) |
| Riesgo principal | Confundir el sesgo de plataforma con el de periodo: casi todo Bluesky es de 2025–2026. |
| Mitigación | Estratificar el análisis por periodo y restringir las preguntas comparativas a 2025–2026. Además, verificar en la documentación de `pymilvus` 2.6 que Milvus permite BM25 en la misma colección; si no, hacer la fusión en la aplicación. |

## PI3. Definición de propagación noticia → red

**Contexto.** Con texto idéntico (`text_sha256`) hay **0** grupos `media_cloud + bluesky`. Los únicos 14 grupos mixtos son `gdelt + media_cloud` (H5). El 94,90 % de las fechas de `media_cloud` tiene solo día, y hay 290 posts de Bluesky fechados antes de que la plataforma existiera (H4).

La pregunta es metodológica: **¿conviene medir la propagación con similitud de texto o con URLs compartidas?** Cada opción define una medida distinta.

| Definición | Qué mide | Ventaja | Limitación |
|---|---|---|---|
| A. Similitud de texto (MinHash o SimHash sobre n-gramas, o coseno de embeddings por encima de un umbral) | Que un post reproduce o resume el contenido de una noticia | No depende de enlaces | Depende de un umbral. Un post y un artículo comparten poco texto, así que habría que medir *contención* (qué parte del post está en el artículo) en lugar de semejanza simétrica. Puede capturar coincidencias temáticas que no son propagación. |
| B. URL compartida (un post enlaza la URL, normalizada, de un artículo del corpus) | Que un post cita explícitamente una noticia | Definición precisa y auditable | Solo cuenta la propagación explícita. Hay que extraer los enlaces de los posts, y la columna `url` de Bluesky es la del post, no la del enlace. |

| Elemento | Propuesta |
|---|---|
| Hipótesis refutable | Con la definición B hay al menos 30 pares artículo–post en 2025–2026, y la mediana del desfase (post − artículo, en días) es ≥ 0. Con la definición A, con contención ≥ 0,5, la mayoría de los pares de B también aparecen (cobertura ≥ 50 %). Se refuta si B da menos de 30 pares o si A recupera menos de la mitad de los pares de B. |
| Medición | Número de pares por definición, desfase en **días** (la resolución real), y concordancia A–B (pares en común / pares de B). Precisión de A en una muestra de 50 pares anotada por dos anotadores, con acuerdo kappa. |
| Puntos del enunciado | 6 (duplicados, fechas, sesgos por plataforma), 8 (compromisos verificables de trazabilidad) |
| Riesgo principal | Las dos definiciones requieren leer `text` para extraer enlaces o calcular similitud, y eso queda fuera de las reglas de este análisis exploratorio. Además, las fechas dudosas de Bluesky contaminan los desfases. |
| Mitigación | Hacerlo en un script aparte, aprobado explícitamente, que solo guarde salidas agregadas o hashes. Excluir los posts fechados antes de 2023 y reportar cuántos se excluyen. |

## PI4. Abstención y corrección de la recuperación

**Contexto.** El punto 1 del enunciado exige preguntas sin evidencia y adversariales. Las fechas incompletas o dudosas (H4) y la cobertura desigual por periodo (H3) aumentan el riesgo de que el modelo responda con evidencia de otra época.

| Elemento | Propuesta |
|---|---|
| Hipótesis refutable | Una compuerta tipo CRAG reduce las respuestas sin evidencia en al menos 30 % (relativo) en el subconjunto *sin evidencia*, y baja la corrección en el subconjunto *con evidencia* en menos de 5 puntos. La compuerta abstiene si el mejor score de recuperación o un evaluador ligero de relevancia queda por debajo de un umbral fijado en desarrollo. Se refuta si alguna de las dos condiciones falla en test. |
| Medición | Tasa de abstención correcta, falsa abstención, corrección y citas válidas, por subconjunto (con evidencia, sin evidencia, temporal). El umbral se fija solo en desarrollo. |
| Puntos del enunciado | 1 (preguntas sin evidencia y adversariales; dev/test), 4 (abstención, citas válidas) |
| Riesgo principal | El umbral se sobreajusta al conjunto de desarrollo. Los scores de e5 no están calibrados entre idiomas, así que un mismo umbral puede abstener de más en español. |
| Mitigación | Fijar el umbral por idioma en desarrollo y reportar la curva de abstención frente a corrección, no un solo punto. |

## PI5. Modelos pequeños en un corpus bilingüe

**Contexto.** El scaffold usa `qwen2.5:1.5b`, y como comparadores `llama3.2:1b`, `llama3.2:3b` y `gemma2:2b`. Con evidencia mayoritariamente en inglés (H1) y preguntas en español, el modelo además tiene que responder en el idioma de la pregunta.

| Elemento | Propuesta |
|---|---|
| Hipótesis refutable | Con la recuperación fija (mismo índice, k, prompt y temperatura), la fidelidad según la rúbrica humana de `llama3.2:3b` supera a la de `qwen2.5:1.5b` en al menos 10 puntos, con una latencia p95 a lo sumo 2 veces mayor. Además, al menos 1 de cada 10 respuestas de los modelos de 1–1,5B a preguntas en español con evidencia en inglés sale en inglés. Se refuta si no se cumple alguna de las dos partes. |
| Medición | Fidelidad y corrección (rúbrica humana y un juez LLM, con su acuerdo), idioma de la respuesta, tokens/s, p50/p95 de latencia, RAM. Al menos 3 repeticiones, arranque en frío y en caliente. |
| Puntos del enunciado | 3 (comparación controlada de LLM), 4, 5 (repeticiones, intervalos), 8 (compromisos de calidad y recursos) |
| Riesgo principal | Un juez LLM sesgado (por longitud, por idioma o por preferir su propia familia de modelos) puede invertir la conclusión. |
| Mitigación | Rúbrica humana en una submuestra con dos anotadores y kappa (punto 2). Usar el juez solo cuando su acuerdo con los humanos sea aceptable, y reportar ese acuerdo. |

## Estado del arte

Todas las referencias son **candidatas, por verificar**: autor, año, título e identificador deben confirmarse contra la fuente original antes de citarlas. No deben citarse como definitivas.

### Recuperación léxica, densa e híbrida

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Robertson, S.; Zaragoza, H. | 2009 | The Probabilistic Relevance Framework: BM25 and Beyond | doi:10.1561/1500000019 | por verificar |
| Cormack, G. V.; Clarke, C. L. A.; Büttcher, S. | 2009 | Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods | doi:10.1145/1571941.1572114 | por verificar |
| Karpukhin, V. et al. | 2020 | Dense Passage Retrieval for Open-Domain Question Answering | arXiv:2004.04906 | por verificar |
| Formal, T.; Piwowarski, B.; Clinchant, S. | 2021 | SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking | arXiv:2107.05720 | por verificar |
| Thakur, N. et al. | 2021 | BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models | arXiv:2104.08663 | por verificar |

### Embeddings multilingües

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Wang, L. et al. | 2022 | Text Embeddings by Weakly-Supervised Contrastive Pre-training | arXiv:2212.03533 | por verificar |
| Wang, L. et al. | 2024 | Multilingual E5 Text Embeddings: A Technical Report | arXiv:2402.05672 | por verificar |
| Chen, J. et al. | 2024 | BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation | arXiv:2402.03216 | por verificar |
| Muennighoff, N. et al. | 2022 | MTEB: Massive Text Embedding Benchmark | arXiv:2210.07316 | por verificar |
| Zhang, X. et al. | 2023 | MIRACL: A Multilingual Retrieval Dataset Covering 18 Diverse Languages | arXiv:2210.09984 | por verificar |

### Reranking

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Nogueira, R.; Cho, K. | 2019 | Passage Re-ranking with BERT | arXiv:1901.04085 | por verificar |
| Khattab, O.; Zaharia, M. | 2020 | ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT | arXiv:2004.12832 | por verificar |
| Sun, W. et al. | 2023 | Is ChatGPT Good at Search? Investigating Large Language Models as Re-Ranking Agents | arXiv:2304.09542 | por verificar |

### Contextual retrieval y chunking con contexto

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Anthropic | 2024 | Introducing Contextual Retrieval | https://www.anthropic.com/news/contextual-retrieval | por verificar |
| Günther, M. et al. | 2024 | Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models | arXiv:2409.04701 | por verificar |
| Sarthi, P. et al. | 2024 | RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval | arXiv:2401.18059 | por verificar |
| Liu, N. F. et al. | 2023 | Lost in the Middle: How Language Models Use Long Contexts | arXiv:2307.03172 | por verificar |

### Abstención y corrección de la recuperación

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Yan, S.-Q. et al. | 2024 | Corrective Retrieval Augmented Generation (CRAG) | arXiv:2401.15884 | por verificar |
| Asai, A. et al. | 2023 | Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection | arXiv:2310.11511 | por verificar |
| Rajpurkar, P.; Jia, R.; Liang, P. | 2018 | Know What You Don't Know: Unanswerable Questions for SQuAD | arXiv:1806.03822 | por verificar |
| Wen, B. et al. | 2024 | Know Your Limits: A Survey of Abstention in Large Language Models | arXiv:2407.18418 | por verificar |

### Evaluación de RAG

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Es, S. et al. | 2023 | RAGAS: Automated Evaluation of Retrieval Augmented Generation | arXiv:2309.15217 | por verificar |
| Saad-Falcon, J. et al. | 2023 | ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems | arXiv:2311.09476 | por verificar |
| Zheng, L. et al. | 2023 | Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | arXiv:2306.05685 | por verificar |
| Järvelin, K.; Kekäläinen, J. | 2002 | Cumulated Gain-Based Evaluation of IR Techniques | doi:10.1145/582415.582418 | por verificar |

### Modelos pequeños

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Qwen Team | 2024 | Qwen2.5 Technical Report | arXiv:2412.15115 | por verificar |
| Gemma Team | 2024 | Gemma 2: Improving Open Language Models at a Practical Size | arXiv:2408.00118 | por verificar |
| Grattafiori, A. et al. (Llama Team) | 2024 | The Llama 3 Herd of Models | arXiv:2407.21783 | por verificar |
| Abdin, M. et al. | 2024 | Phi-3 Technical Report: A Highly Capable Language Model Locally on Your Phone | arXiv:2404.14219 | por verificar |

### Complementarias: casi duplicados, propagación y contaminación (PI3 y punto 6)

| Autor(es) | Año | Título | Identificador | Estado |
|---|---|---|---|---|
| Broder, A. Z. | 1997 | On the Resemblance and Containment of Documents | doi:10.1109/SEQUEN.1997.666900 | por verificar |
| Charikar, M. S. | 2002 | Similarity Estimation Techniques from Rounding Algorithms | doi:10.1145/509907.509965 | por verificar |
| Leskovec, J.; Backstrom, L.; Kleinberg, J. | 2009 | Meme-tracking and the Dynamics of the News Cycle | doi:10.1145/1557019.1557077 | por verificar |
| Greshake, K. et al. | 2023 | Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection | arXiv:2302.12173 | por verificar |
| Zou, W. et al. | 2024 | PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models | arXiv:2402.07867 | por verificar |

## Siguientes pasos

1. Revisar con el equipo las cinco preguntas y escoger tres a cinco.
2. Fijar los umbrales de cada hipótesis en desarrollo, antes de mirar test.
3. Verificar cada referencia contra la fuente original y cambiar su estado a "verificada".
4. Si se escoge PI3, aprobar el script que lee `text` y definir qué salidas agregadas puede guardar.
