# 🚀 Pipeline Entrega 2: Guía Ejecutable para Replit/Reproducción

## 🎯 Una Línea
**Análisis de sesgo editorial en 6 medios colombianos (708K artículos, Duque 2018-2022) usando textometría, LDA y análisis de eventos polémicos.**

---

## 📊 Dashboard de Resultados

```
┌─────────────────────────────────────────────────────────────┐
│                    ENTREGA 2 - COMPLETA                     │
├─────────────────────────────────────────────────────────────┤
│ ✅ Corpus:           708,768 artículos (6 medios)           │
│ ✅ Período:          2018-08-07 a 2022-08-07 (4 años)       │
│ ✅ Cobertura títulos: 99.83% (deriv. de URLs)               │
│ ✅ Modelos LDA:      5 entrenamientos (K=3,5,7,10,15)       │
│ ✅ Mejor K:          5 → coherencia=0.35955                 │
│ ✅ Notebook:         30 celdas ejecutadas ✓                 │
│ ✅ Informe PDF:      5 páginas compiladas ✓                 │
│ ✅ Presentación PPT: 10 diapositivas ✓                      │
│ ✅ Visualizaciones:  7 PNG + 1 HTML interactivo ✓           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Datos de Entrada

### Corpus Duque
```
Archivo: duque-candidatos.parquet (70 MB)
Ubicación en proyecto: news-retrieval/exports/

Contenido:
  - article_id: ID único del artículo
  - source_id: Medio (el_tiempo, blu_radio, noticias_caracol, 
                      la_republica, noticias_rcn, cambio)
  - title: Título derivado de URL (slug)
  - published_date: Fecha de publicación
  - url: URL original
  - title_source: Método de derivación (slug, sitemap, extracted)
  - government_id: 'duque' para todos los registros
```

### Estadísticas por Medio
| Medio | Artículos | % |
|-------|-----------|-----|
| El Tiempo | 118,925 | 16.8% |
| Noticias Caracol | 116,228 | 16.4% |
| La República | 115,677 | 16.3% |
| Blu Radio | 113,906 | 16.1% |
| Noticias RCN | 112,806 | 15.9% |
| Cambio | 8,203 | 1.2% |
| **TOTAL** | **708,768** | **100%** |

---

## 🔧 El Pipeline: 4 Fases Principales

### ⏱️ FASE 1: Textometría (15 min)

**¿Qué hace?** Análisis cuantitativo del lenguaje en títulos.

```python
# 1. Ley de Zipf
# Hipótesis: frecuencia ∝ rango^(-α)
# Método: Contar palabras, graficar log-log
# Resultado: zipf_law.png (confirma ley de potencia)

# 2. Diversidad Léxica
# TTR = vocabulario_único / total_palabras
# MSTTR = mean segmental TTR (robusto)
# Yule's K = índice de vocabulario diverso
# Resultado: lexical_diversity.png + tabla

# 3. N-gramas Frecuentes
# Bigr: 2 palabras consecutivas más comunes
# Trigr: 3 palabras consecutivas más comunes
# Resultado: ngrams.png + CSVs
```

**Hallazgos**:
- La República: TTR=0.42 (vocabulario más variado)
- Cambio: TTR=0.31 (vocabulario más repetitivo)
- "programa completo" y "radio caracol" son top (artefactos, no sesgo)

**Archivos generados**:
- zipf_law.png
- lexical_diversity.png
- ngrams.png
- bigrams_top30.csv
- trigrams_top20.csv

---

### ⏱️ FASE 2: Análisis de Eventos Polémicos (10 min)

**¿Qué hace?** Mide diferencias de cobertura entre medios en temas controvertidos.

```python
# Seleccionar 3 temas clave del período Duque:
eventos = {
    'Reforma Tributaria': keywords para búsqueda,
    'Conflicto Armado': keywords,
    'Corrupción': keywords
}

# Para cada tema:
# - Buscar artículos que contengan cualquier keyword
# - Contar por medio
# - Calcular proporción: (artículos/total) * 100
```

**Resultados Medidos**:
```
Reforma Tributaria:
  La República:  1.08% ← Mayor cobertura
  El Tiempo:     0.72%
  Noticias RCN:  0.71%
  Blu Radio:     0.65%
  Caracol:       0.58%
  Cambio:        0.43%

Conflicto Armado:
  Blu Radio:     1.97% ┐ Mayor
  Noticias RCN:  1.97% ┤
  Caracol:       1.78%
  El Tiempo:     1.65%
  La República:  1.52%
  Cambio:        0.89%

Corrupción:
  La República:  0.62%
  El Tiempo:     0.53%
  Caracol:       0.51%
  RCN:           0.55%
  Blu Radio:     0.48%
  Cambio:        0.34%
```

**Interpretación**: La República cubre más reforma tributaria; Blu+RCN cubren más conflicto armado. **Pero**: esto no prueba sesgo editorial, solo diferencia de cobertura.

**Archivos generados**:
- eventos_framing.png
- eventos_polemicos.csv

---

### ⏱️ FASE 3: Topic Modeling (30 min)

**¿Qué hace?** Descubre temas latentes usando LDA (Latent Dirichlet Allocation).

```python
# LDA: Modelo probabilístico que asume:
# - Cada documento = mezcla de tópicos
# - Cada tópico = distribución sobre palabras

# Entrenar 5 modelos con distinto K (número de tópicos)
for K in [3, 5, 7, 10, 15]:
    modelo = LdaModel(corpus, num_topics=K, passes=10)
    coherence_score = calcular_coherencia(modelo)
    
# Seleccionar K con máxima coherencia
# → K=5 ganador: c_v = 0.35955
```

**Los 5 Tópicos Descubiertos (K=5)**:
```
Tópico 1: ECONOMÍA / NEGOCIOS
  → Palabras clave: reforma, impuesto, tributaria, gobierno
  → Interpretación: Política fiscal, recaudos

Tópico 2: POLÍTICA / GOBIERNO
  → Palabras clave: gobierno, presidente, nacional, reforma
  → Interpretación: Instituciones, decisiones de ejecutivo

Tópico 3: SEGURIDAD / CONFLICTO
  → Palabras clave: guerrilla, farc, eln, bombardeo
  → Interpretación: Conflicto armado, operaciones

Tópico 4: SALUD / PANDEMIA
  → Palabras clave: covid, vacuna, hospital, salud
  → Interpretación: COVID-19, servicios de salud

Tópico 5: EDUCACIÓN / SOCIAL
  → Palabras clave: educación, estudiantes, programa, escuela
  → Interpretación: Acceso educativo, programas sociales
```

**Distribución por Medio** (¿Qué % de cada tópico cubre cada medio?):
| Medio | Tema 1 | Tema 2 | Tema 3 | Tema 4 | Tema 5 |
|-------|--------|--------|--------|--------|--------|
| El Tiempo | 22% | 18% | 20% | 19% | 21% |
| Caracol | 21% | 19% | 21% | 20% | 19% |
| La República | 23% | 17% | 19% | 21% | 20% |
| Blu Radio | 21% | 18% | 21% | 20% | 20% |
| Noticias RCN | 21% | 19% | 20% | 20% | 20% |
| Cambio | 20% | 17% | 22% | 21% | 20% |

**Interpretación**: Distribuciones muy similares → **No hay sesgo selectivo obvio por tema**

**Archivos generados**:
- lda_k3.model, lda_k5.model, ..., lda_k15.model (modelos entrenados)
- lda_optimization.png (gráfico coherencia vs K)
- topics_by_medium.png (gráfico de distribuciones)
- topics_heatmap.png (mapa de calor)
- lda_visualization.html (explorador interactivo)
- lda_optimization.csv (tabla de coherencias)
- topics_by_medium.csv (tabla de conteos)
- document_topics.parquet (asignación topic a cada artículo)

---

### ⏱️ FASE 4: Integración y Entregables (20 min)

**¿Qué hace?** Compila resultados en informe académico, presentación y notebook.

```
Entregable 1: Notebook Jupyter (entrega2.ipynb)
├── 30 celdas ejecutadas
├── Código reproducible
├── Gráficos embebidos
└── Tablas de resultados

Entregable 2: Informe LaTeX (entrega2.pdf)
├── Portada
├── Resumen ejecutivo
├── Metodología (Zipf, TTR, LDA)
├── Resultados por sección
├── Conclusiones y limitaciones
└── 5 páginas total

Entregable 3: Presentación (entrega2.pptx)
├── 10 diapositivas
├── Gráficos principales
├── Tablas de hallazgos
├── Conclusiones
└── Formato profesional

Entregable 4: Explorador Interactivo (lda_visualization.html)
├── Visualización pyLDAvis
├── Todos los tópicos explorables
└── Exportable a HTML/standalone
```

---

## 📂 Estructura de Carpetas

```
media-bias-detection/
│
├── ENTREGA2_PIPELINE_README.md     ← Este archivo
├── REPLIT_GUIDE_PIPELINE.md        ← Guía ejecutable
│
├── entrega2/
│   ├── entrega2.ipynb              ✅ Notebook (30 celdas)
│   ├── analysis.py                 ✅ Script principal
│   ├── requirements.txt             ✅ Dependencias
│   │
│   ├── resultados/                 📊 Datos generados
│   │   ├── resumen.json
│   │   ├── config.json
│   │   ├── lda_optimization.csv
│   │   ├── topics_by_medium.csv
│   │   ├── topics_by_medium_norm.csv
│   │   ├── document_topics.parquet
│   │   ├── modelos/
│   │   │   ├── lda_k3.model
│   │   │   ├── lda_k5.model
│   │   │   ├── lda_k7.model
│   │   │   ├── lda_k10.model
│   │   │   └── lda_k15.model
│   │   └── figuras/
│   │       ├── zipf_law.png
│   │       ├── lexical_diversity.png
│   │       ├── ngrams.png
│   │       ├── eventos_framing.png
│   │       ├── lda_optimization.png
│   │       ├── topics_by_medium.png
│   │       └── topics_heatmap.png
│   │
│   └── tests/
│       └── test_core.py             ✅ 9 tests (todos pasan)
│
├── informe/
│   ├── entrega2.pdf                📄 Informe compilado
│   ├── entrega2.tex                📝 Fuente LaTeX
│   ├── entrega2.pptx               🎤 Presentación
│   ├── lda_visualization.html      🌐 Explorador LDA
│   └── entrega2.log                📋 Log compilación
│
└── news-retrieval/
    └── exports/
        └── duque-candidatos.parquet 📦 Datos de entrada (70 MB)
```

---

## 🎬 Cómo Ejecutar

### Opción A: En Replit (Recomendado para Demo)

```bash
# 1. Clonar repo
git clone https://github.com/AbelAlbuez/natural-language-processing-workshops.git
cd natural-language-processing-workshops

# 2. Instalar dependencias
pip install pandas gensim nltk pyLDAvis python-pptx nbformat nbclient scikit-learn

# 3. Descargar recursos NLTK
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# 4. Verificar que duque-candidatos.parquet existe
ls -lh workshops/media-bias-detection/news-retrieval/exports/duque-candidatos.parquet

# 5. Ejecutar análisis
cd workshops/media-bias-detection/entrega2
python analysis.py \
  --input ../news-retrieval/exports/duque-candidatos.parquet \
  --output resultados \
  --report-dir ../informe \
  --topics 3 5 7 10 15 \
  --passes 10

# 6. Abrir resultados
# - Notebook: entrega2.ipynb
# - PDF: ../informe/entrega2.pdf
# - PPT: ../informe/entrega2.pptx
# - HTML: ../informe/lda_visualization.html
```

**Tiempo**: ~45 min (incluye 10 pasadas de LDA)

---

### Opción B: Jupyter Notebook (Interactivo)

```bash
cd workshops/media-bias-detection/entrega2
jupyter notebook entrega2.ipynb
```

Luego:
1. Celda 1: Carga corpus
2. Celda 2-5: Textometría
3. Celda 6-7: Eventos polémicos
4. Celda 8-12: LDA
5. Celda 13-30: Visualizaciones

---

### Opción C: Docker (Aislado)

```bash
cd workshops/media-bias-detection/entrega2

# Build image
docker build -t duque-entrega2 .

# Run analysis
docker run --rm \
  -v $(pwd)/resultados:/analysis/resultados \
  -v $(pwd)/../news-retrieval/exports:/data \
  duque-entrega2:local \
  python analysis.py \
    --input /data/duque-candidatos.parquet \
    --output /analysis/resultados \
    --report-dir /analysis/../informe
```

---

## 🔍 Cómo Entender los Resultados

### `zipf_law.png`
- **Eje X**: log(rango) = log(posición de palabra por frecuencia)
- **Eje Y**: log(frecuencia) = log(veces que aparece)
- **Línea recta**: Ley de Zipf confirmada
- **Interpretación**: Si r ≈ -1, lenguaje natural típico

### `lexical_diversity.png`
- **TTR**: Cuán variado es el vocabulario (0-1)
  - TTR alto = vocabulario diverso
  - TTR bajo = vocabulario repetitivo
- **MSTTR**: TTR robusto (no sesgado por largo)
- **Yule's K**: Índice de diversidad (> 0)

### `ngrams.png`
- Top 30 bigramas (2 palabras juntas)
- Top 20 trigramas (3 palabras juntas)
- Muestra qué combinaciones son más frecuentes

### `lda_optimization.png`
- **Eje X**: K (número de tópicos 3-15)
- **Eje Y**: Coherence score (0-1)
- **Punto más alto**: K óptimo (aquí K=5)
- **Interpretación**: Máxima coherencia = tópicos más interpretables

### `topics_by_medium.png`
- **Eje X**: Medios
- **Eje Y**: Proporción (%)
- **Barras apiladas**: Distribución de 5 tópicos
- **Interpretación**: Si barras son similares → agenda común

### `topics_heatmap.png`
- **Filas**: Medios
- **Columnas**: Tópicos
- **Color**: Intensidad de proporción
- **Interpretación**: Patrones visuales de cobertura

### `lda_visualization.html`
- Abre en navegador
- Click en tópicos para explorar
- Panel derecho: palabras principales por tópico
- Panel izquierdo: distancia entre tópicos

---

## ⚠️ Limitaciones Importantes

### 1. Títulos Slug (No Verificados Manualmente)
- Derivados automáticamente de URLs
- NO extracción HTML del cuerpo
- Pueden contener artefactos ("programa completo", "radio caracol")

### 2. Análisis Exploratorio, No Concluyente
- Búsquedas por palabras ≠ análisis cualitativo de framing
- LDA detecta tópicos temáticos, no sesgo político
- Necesita validación manual de casos clave

### 3. Cambio es Pequeña Muestra
- Cambio: 8,203 artículos (1.2%)
- No comparar 1:1 con medios de 100K+
- Usarlo como submuestra, no en análisis de desviaciones

### 4. Períodos Incompletos Posibles
- Algunos meses podrían tener gaps
- Verificar con DB original (collection_chunk)

---

## 📊 Tabla de Referencia: Hallazgos Clave

| Aspecto | Resultado | Evidencia |
|---------|-----------|-----------|
| **Ley de Zipf** | ✅ Confirmada | r > 0.8 en gráfico log-log |
| **Vocabulario más diverso** | La República | TTR = 0.42 |
| **Vocabulario más repetitivo** | Cambio | TTR = 0.31 |
| **Cobertura Reforma Tributaria** | La República (1.08%) | 50% más que Cambio (0.43%) |
| **Cobertura Conflicto Armado** | Blu Radio, RCN (1.97%) | Más que Cambio (0.89%) |
| **Tópicos óptimos** | K=5 | Coherencia=0.35955 |
| **Sesgo selectivo por tema** | ❌ No evidente | Distribuciones similares (19-23% por tópico) |
| **Agenda común** | ✅ Probable | Todos cubren 5 temas similares |

---

## 🎓 Para Presentación/Defensa

**Narrativa recomendada**:

> *"Analicé 708 mil artículos de 6 medios colombianos del período Duque (2018-2022) usando tres métodos:*
> 
> 1. **Textometría**: Confirmé ley de Zipf en títulos; encontré que La República usa vocabulario más diverso (TTR=0.42) vs Cambio (0.31).
>
> 2. **Eventos polémicos**: Medí cobertura de reforma tributaria, conflicto armado y corrupción. La República da 50% más cobertura a reforma tributaria que el promedio; Blu Radio y RCN cubren más conflicto armado (1.97% vs promedio 1.5%).
>
> 3. **Topic Modeling (LDA)**: Descubrí 5 temas principales (economía, política, seguridad, salud, educación). La distribución es similar entre medios (~20% cada uno), sugiriendo agenda editorial común más que sesgo selectivo.
>
> **Conclusión**: Análisis exploratorio que detecta diferencias de énfasis, pero no sesgo selectivo obvio en esta muestra de títulos. Necesita validación cualitativa."*

---

## 🔗 Enlaces Útiles

- **Repo GitHub**: https://github.com/AbelAlbuez/natural-language-processing-workshops
- **Rama**: `feature/fase3-architecture-documentation`
- **Commit final**: `960a678` (Entrega 2 completa)

---

## ✅ Checklist de Validación

- [x] Corpus cargado: 708,768 artículos
- [x] Período verificado: 2018-08-07 a 2022-08-07
- [x] Textometría: Zipf, TTR, n-gramas calculados
- [x] Eventos: Búsqueda de 3 temas completada
- [x] LDA: 5 modelos entrenados, K=5 óptimo
- [x] Notebook: 30 celdas ejecutadas sin errores
- [x] PDF: Compilado, 5 páginas
- [x] PPT: 10 diapositivas, geometría OK
- [x] HTML: pyLDAvis generado
- [x] Documentación: Completa

---

**Estado**: ✅ ENTREGA 2 COMPLETADA  
**Fecha**: 2026-10-05  
**Próximos pasos**: Presentación / Defensa / Publicación

