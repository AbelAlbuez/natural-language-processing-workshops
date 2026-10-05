# PROMPT COMPLETO: Entrega 2 - Media Bias Detection (6 Fases)

## OBJETIVO GENERAL
Analizar sesgo de framing en período Duque (2018-2022) usando corpus enriquecido de 708,768 artículos de 8 medios colombianos.

**Entregables:**
1. ✅ Análisis textométrico (Ley de Zipf, diversidad léxica, n-gramas)
2. ✅ Comparación de eventos polémicos por medio
3. ✅ Topic modeling automático (LDA)
4. ✅ Notebook integrado con todos resultados
5. ✅ Informe LaTeX (entrega2.tex)
6. ✅ Presentación PPT (9-10 slides)

---

## FASE 1: PREPARAR DATOS Y ENTORNO

### 1.1 Verificar corpus Duque

```python
import pandas as pd
import numpy as np
from pathlib import Path

# Cargar corpus Duque
csv_path = Path("duque-candidatos.csv")  # 708,768 artículos
parquet_path = Path("duque-candidatos.parquet")

# Opción A: CSV (más lento)
# df = pd.read_csv(csv_path)

# Opción B: Parquet (más rápido) ← RECOMENDADO
df = pd.read_parquet(parquet_path)

print(f"✅ Corpus cargado: {len(df):,} artículos")
print(f"Período: {df['published_date'].min()} a {df['published_date'].max()}")
print(f"Medios: {df['source_id'].unique().tolist()}")
print(f"Cobertura títulos: {df['title'].notna().sum() / len(df) * 100:.2f}%")
print(f"\nColumnas: {df.columns.tolist()}")

# Info rápida
print(f"\nDistribución por medio:")
print(df['source_id'].value_counts())
```

### 1.2 Instalar librerías requeridas

```bash
pip install nltk scikit-learn gensim pyLDAvis textstat matplotlib seaborn wordcloud scipy
```

### 1.3 Descargar recursos NLTK

```python
import nltk

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
```

---

## FASE 2: TEXTOMETRÍA AVANZADA

### 2.1 Preparar texto (remover stopwords)

```python
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import re

# Stopwords español + custom colombianos
stop_words_es = set(stopwords.words('spanish'))
custom_stops = {
    'dice', 'dijo', 'señaló', 'indicó', 'expresó',  # Verbos de reporte
    'luego', 'posteriormente', 'ayer', 'hoy', 'mañana',  # Temporal
    'colombiano', 'colombia', 'bogotá', 'nacional',  # Geográfico (opcional)
}
stop_words = stop_words_es | custom_stops

def clean_text(text):
    """Limpiar y tokenizar texto"""
    if pd.isna(text):
        return []
    
    # Lowercase
    text = str(text).lower()
    
    # Remover URLs
    text = re.sub(r'http\S+|www\S+', '', text)
    
    # Remover puntuación (excepto guiones dentro de palabras)
    text = re.sub(r'[^\w\s-]', ' ', text)
    
    # Tokenizar
    tokens = word_tokenize(text)
    
    # Remover stopwords y palabras muy cortas
    tokens = [t for t in tokens if t not in stop_words and len(t) > 2]
    
    return tokens

# Aplicar a corpus (puede tomar 2-3 min para 708k artículos)
print("→ Limpiando textos... (esto toma 2-3 minutos)")
df['tokens'] = df['title'].apply(clean_text)
df['num_tokens'] = df['tokens'].apply(len)

print(f"✅ Textos procesados")
print(f"Tokens promedio por título: {df['num_tokens'].mean():.1f}")
print(f"Títulos vacíos: {(df['num_tokens'] == 0).sum()}")
```

### 2.2 Análisis de Ley de Zipf

```python
from collections import Counter
import matplotlib.pyplot as plt

# Contar frecuencia global de palabras
all_tokens = []
for tokens in df['tokens']:
    all_tokens.extend(tokens)

word_freq = Counter(all_tokens)
top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

print(f"Vocabulario único: {len(word_freq):,} palabras")
print(f"Top 20 palabras:")
for word, count in top_words[:20]:
    print(f"  {word}: {count:,}")

# Graficar Ley de Zipf
ranks = list(range(1, len(top_words) + 1))
frequencies = [count for word, count in top_words]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# Gráfico lineal (primeras 100)
ax1.plot(ranks[:100], frequencies[:100], 'b-')
ax1.set_xlabel('Rank (posición)')
ax1.set_ylabel('Frecuencia')
ax1.set_title('Ley de Zipf (primeras 100 palabras)')
ax1.grid(True, alpha=0.3)

# Gráfico log-log
ax2.loglog(ranks, frequencies, 'r.')
ax2.set_xlabel('Rank (log)')
ax2.set_ylabel('Frecuencia (log)')
ax2.set_title('Ley de Zipf (escala log-log)')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('zipf_law.png', dpi=150)
print("\n✅ Gráfico Ley de Zipf guardado: zipf_law.png")
plt.show()

# Verificar si cumple Zipf (correlación log-log)
import scipy.stats as stats
log_ranks = np.log(ranks)
log_freqs = np.log(frequencies)
correlation, pvalue = stats.pearsonr(log_ranks, log_freqs)
print(f"\nCorrelación log-log: {correlation:.4f} (p={pvalue:.2e})")
print("→ Si correlación < -0.95, sigue ley de Zipf")
```

### 2.3 Diversidad léxica

```python
def calculate_ttr(tokens):
    """Type-Token Ratio"""
    if len(tokens) == 0:
        return 0
    return len(set(tokens)) / len(tokens)

def calculate_msttr(tokens, window=50):
    """Mean Segmental Type-Token Ratio"""
    if len(tokens) < window:
        return calculate_ttr(tokens)
    
    segments = [tokens[i:i+window] for i in range(0, len(tokens), window)]
    return np.mean([calculate_ttr(seg) for seg in segments])

def calculate_yules_k(tokens):
    """Yule's K - medida de diversidad vocabulario"""
    if len(tokens) == 0:
        return 0
    
    freq = Counter(tokens)
    n = len(tokens)
    
    sigma = sum(f * (f - 1) for f in freq.values())
    k = 10000 * (sigma / (n * (n - 1)))
    
    return k

# Calcular por título
print("→ Calculando métricas de diversidad léxica...")
df['ttr'] = df['tokens'].apply(calculate_ttr)
df['msttr'] = df['tokens'].apply(calculate_msttr)
df['yules_k'] = df['tokens'].apply(calculate_yules_k)

# Estadísticas globales
print(f"\n📊 DIVERSIDAD LÉXICA - CORPUS DUQUE")
print(f"Type-Token Ratio (TTR):")
print(f"  Media: {df['ttr'].mean():.4f}")
print(f"  Rango: {df['ttr'].min():.4f} - {df['ttr'].max():.4f}")

print(f"\nMean Segmental TTR:")
print(f"  Media: {df['msttr'].mean():.4f}")

print(f"\nYule's K:")
print(f"  Media: {df['yules_k'].mean():.4f}")
print(f"  (Valores altos = menos diversidad)")

# Por medio
print(f"\nDiversidad por MEDIO:")
diversity_by_medium = df.groupby('source_id').agg({
    'ttr': 'mean',
    'msttr': 'mean',
    'yules_k': 'mean'
}).round(4)
print(diversity_by_medium)

# Visualizar
fig, axes = plt.subplots(1, 3, figsize=(15, 4))

df.boxplot(column='ttr', by='source_id', ax=axes[0])
axes[0].set_title('TTR por medio')
axes[0].set_ylabel('TTR')

df.boxplot(column='msttr', by='source_id', ax=axes[1])
axes[1].set_title('MSTTR por medio')
axes[1].set_ylabel('MSTTR')

df.boxplot(column='yules_k', by='source_id', ax=axes[2])
axes[2].set_title('Yule\'s K por medio')
axes[2].set_ylabel('Yule\'s K')

plt.suptitle('')
plt.tight_layout()
plt.savefig('lexical_diversity.png', dpi=150)
print("\n✅ Gráfico diversidad léxica guardado: lexical_diversity.png")
plt.show()
```

### 2.4 Bigramas y trigramas

```python
from sklearn.feature_extraction.text import CountVectorizer

# Bigramas
vectorizer_bi = CountVectorizer(
    ngram_range=(2, 2),
    max_features=100,
    min_df=5,  # Mínimo 5 documentos
    stop_words='spanish'
)

# Crear matriz
titles_text = df['title'].fillna('').tolist()
X_bi = vectorizer_bi.fit_transform(titles_text)
bi_freq = np.asarray(X_bi.sum(axis=0)).flatten()
bigrams = vectorizer_bi.get_feature_names_out()
bi_df = pd.DataFrame({
    'bigram': bigrams,
    'freq': bi_freq
}).sort_values('freq', ascending=False)

print("📊 TOP 30 BIGRAMAS")
print(bi_df.head(30).to_string())

# Trigramas
vectorizer_tri = CountVectorizer(
    ngram_range=(3, 3),
    max_features=50,
    min_df=3,
    stop_words='spanish'
)
X_tri = vectorizer_tri.fit_transform(titles_text)
tri_freq = np.asarray(X_tri.sum(axis=0)).flatten()
trigrams = vectorizer_tri.get_feature_names_out()
tri_df = pd.DataFrame({
    'trigram': trigrams,
    'freq': tri_freq
}).sort_values('freq', ascending=False)

print("\n📊 TOP 20 TRIGRAMAS")
print(tri_df.head(20).to_string())

# Visualizar
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

bi_df.head(20).plot(x='bigram', y='freq', kind='barh', ax=ax1, legend=False)
ax1.set_title('Top 20 Bigramas')
ax1.set_xlabel('Frecuencia')

tri_df.head(15).plot(x='trigram', y='freq', kind='barh', ax=ax2, legend=False)
ax2.set_title('Top 15 Trigramas')
ax2.set_xlabel('Frecuencia')

plt.tight_layout()
plt.savefig('ngrams.png', dpi=150)
print("\n✅ Gráfico n-gramas guardado: ngrams.png")
plt.show()

# Guardar para referencia
bi_df.to_csv('bigrams_top100.csv', index=False)
tri_df.to_csv('trigrams_top50.csv', index=False)
```

---

## FASE 3: ANÁLISIS DE EVENTOS POLÉMICOS

### 3.1 Definir eventos y crear queries

```python
# Temas polémicos Duque (2018-2022)
eventos_polemicos = {
    'Reforma Tributaria': {
        'keywords': ['reforma tributaria', 'impuesto', 'recaudo', 'reforma fiscal'],
        'color': '#FF6B6B'
    },
    'Conflicto Armado': {
        'keywords': ['conflicto armado', 'guerrilla', 'eln', 'farc', 'disidencias', 'violencia'],
        'color': '#4ECDC4'
    },
    'Corrupción': {
        'keywords': ['corrupción', 'fraude', 'peculado', 'soborno', 'odebrecht', 'lavado dinero'],
        'color': '#FFE66D'
    }
}

def find_event_articles(df, keywords, case_sensitive=False):
    """Encontrar artículos por palabras clave"""
    mask = pd.Series([False] * len(df))
    
    for keyword in keywords:
        if case_sensitive:
            mask |= df['title'].str.contains(keyword, na=False, regex=False)
        else:
            mask |= df['title'].str.lower().str.contains(keyword.lower(), na=False, regex=False)
    
    return df[mask]

# Contar artículos por evento y medio
print("📊 COBERTURA DE EVENTOS POLÉMICOS")
print("=" * 80)

evento_stats = {}
for evento, config in eventos_polemicos.items():
    articles = find_event_articles(df, config['keywords'])
    evento_stats[evento] = {
        'total': len(articles),
        'por_medio': articles['source_id'].value_counts().to_dict()
    }
    
    print(f"\n{evento}:")
    print(f"  Total: {len(articles):,} artículos ({len(articles)/len(df)*100:.2f}% del corpus)")
    print(f"  Por medio:")
    for medio, count in articles['source_id'].value_counts().items():
        pct = count / len(articles) * 100
        print(f"    {medio}: {count:,} ({pct:.1f}%)")

# Crear tabla resumen
resumen_eventos = pd.DataFrame({
    evento: {
        'Total': stats['total'],
        **stats['por_medio']
    }
    for evento, stats in evento_stats.items()
}).fillna(0).astype(int)

print("\n📊 TABLA RESUMEN - Eventos por medio")
print(resumen_eventos.T)

# Guardar
resumen_eventos.to_csv('eventos_polemicos.csv')
```

### 3.2 Analizar framing (diferencias entre medios)

```python
def analyze_framing(event_name, keywords, df):
    """Analizar cómo cada medio presenta un evento"""
    
    articles = find_event_articles(df, keywords)
    
    # Palabras más frecuentes por medio
    print(f"\n🎯 FRAMING: {event_name}")
    print("=" * 80)
    
    for medio in df['source_id'].unique():
        medio_articles = articles[articles['source_id'] == medio]
        
        if len(medio_articles) == 0:
            print(f"\n{medio}: (sin cobertura)")
            continue
        
        # Extraer palabras clave
        medio_tokens = []
        for tokens in medio_articles['tokens']:
            medio_tokens.extend(tokens)
        
        top_words = Counter(medio_tokens).most_common(10)
        
        print(f"\n{medio} ({len(medio_articles)} artículos):")
        print(f"  Palabras clave: {', '.join([w for w, c in top_words])}")
        print(f"  Frecuencias: {[c for w, c in top_words]}")

# Analizar cada evento
for evento, config in eventos_polemicos.items():
    analyze_framing(evento, config['keywords'], df)

# Visualizar diferencias por medio
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for idx, (evento, config) in enumerate(eventos_polemicos.items()):
    articles = find_event_articles(df, config['keywords'])
    cobertura = articles['source_id'].value_counts().sort_values(ascending=True)
    
    cobertura.plot(kind='barh', ax=axes[idx], color=config['color'])
    axes[idx].set_title(f'{evento}\n({len(articles):,} artículos)')
    axes[idx].set_xlabel('Número de artículos')

plt.tight_layout()
plt.savefig('eventos_framing.png', dpi=150)
print("\n✅ Gráfico framing guardado: eventos_framing.png")
plt.show()
```

---

## FASE 4: TOPIC MODELING (LDA)

### 4.1 Preparar corpus para LDA

```python
from gensim.corpora import Dictionary
from gensim.models import LdaModel
from gensim.models import CoherenceModel

# Crear diccionario y corpus
print("→ Preparando corpus para LDA...")

# Crear diccionario (vocabulario)
dictionary = Dictionary(df['tokens'])

# Remover palabras muy comunes o muy raras
dictionary.filter_extremes(no_below=10, no_above=0.7, keep_n=10000)

# Crear corpus
corpus = [dictionary.doc2bow(tokens) for tokens in df['tokens']]

print(f"✅ Diccionario: {len(dictionary)} palabras")
print(f"✅ Corpus: {len(corpus)} documentos")

# Guardar
dictionary.save('duque_dictionary.dict')
print("   Guardado: duque_dictionary.dict")
```

### 4.2 Entrenar LDA y encontrar K óptimo

```python
# Probar diferentes números de tópicos
print("→ Entrenando LDA con diferentes K (esto toma 5-10 min)...")

coherence_scores = []
perplexity_scores = []
lda_models = {}

for num_topics in [3, 5, 7, 10, 15]:
    print(f"\n  Entrenando con K={num_topics}...")
    
    lda = LdaModel(
        corpus=corpus,
        id2word=dictionary,
        num_topics=num_topics,
        random_state=42,
        passes=10,  # Iteraciones
        per_word_topics=True,
        minimum_probability=0.0
    )
    
    # Medir coherencia
    coherence_model = CoherenceModel(model=lda, texts=df['tokens'], dictionary=dictionary)
    coherence_score = coherence_model.get_coherence()
    coherence_scores.append(coherence_score)
    
    # Perplexity
    perplexity = lda.log_perplexity(corpus)
    perplexity_scores.append(perplexity)
    
    print(f"    Coherence: {coherence_score:.4f}")
    print(f"    Perplexity: {perplexity:.4f}")
    
    lda_models[num_topics] = lda

# Encontrar K óptimo (máxima coherencia)
optimal_k = [3, 5, 7, 10, 15][np.argmax(coherence_scores)]
print(f"\n✅ K ÓPTIMO: {optimal_k} tópicos (coherence: {max(coherence_scores):.4f})")

# Visualizar
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

ax1.plot([3, 5, 7, 10, 15], coherence_scores, 'o-', linewidth=2, markersize=8)
ax1.set_xlabel('Número de tópicos (K)')
ax1.set_ylabel('Coherence Score')
ax1.set_title('Coherence vs K')
ax1.grid(True, alpha=0.3)
ax1.axvline(optimal_k, color='red', linestyle='--', label=f'Óptimo: K={optimal_k}')
ax1.legend()

ax2.plot([3, 5, 7, 10, 15], perplexity_scores, 'o-', color='orange', linewidth=2, markersize=8)
ax2.set_xlabel('Número de tópicos (K)')
ax2.set_ylabel('Perplexity')
ax2.set_title('Perplexity vs K')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('lda_optimization.png', dpi=150)
print("✅ Gráfico optimización LDA guardado: lda_optimization.png")
plt.show()

# Usar modelo óptimo
lda_final = lda_models[optimal_k]
lda_final.save('duque_lda_final.model')
print(f"✅ Modelo LDA guardado: duque_lda_final.model")
```

### 4.3 Visualizar tópicos

```python
import pyLDAvis.gensim_models as gensimvis
import pyLDAvis

# Visualizar con pyLDAvis
print("→ Generando visualización interactiva...")

vis = gensimvis.prepare(lda_final, corpus, dictionary, mds='mmds', sort_topics=False)
pyLDAvis.save_html(vis, 'lda_visualization.html')

print("✅ Visualización LDA guardada: lda_visualization.html")
print("   Abrir en navegador para explorar interactivamente")

# Mostrar tópicos principales
print(f"\n📊 TOP {optimal_k} TÓPICOS DETECTADOS")
print("=" * 80)

for topic_id in range(optimal_k):
    terms = lda_final.show_topic(topic_id, topn=10)
    print(f"\nTópico {topic_id}:")
    for term, weight in terms:
        print(f"  {term}: {weight:.4f}")
```

### 4.4 Asignar tópicos a documentos

```python
# Obtener distribución de tópicos por documento
print("→ Asignando tópicos a documentos...")

doc_topics = []
for doc_id, bow in enumerate(corpus):
    topic_dist = dict(lda_final.get_document_topics(bow))
    doc_topics.append(topic_dist)

# Agregar a dataframe
df['dominant_topic'] = [max(topics.items(), key=lambda x: x[1])[0] if topics else -1 
                        for topics in doc_topics]
df['topic_confidence'] = [max(topics.values()) if topics else 0 
                          for topics in doc_topics]

# Análisis por medio
print("\n📊 DISTRIBUCIÓN DE TÓPICOS POR MEDIO")
print(df.groupby(['source_id', 'dominant_topic']).size().unstack(fill_value=0))

# Visualizar
topic_by_medium = df.groupby(['source_id', 'dominant_topic']).size().unstack(fill_value=0)

fig, ax = plt.subplots(figsize=(12, 6))
topic_by_medium.plot(kind='bar', stacked=True, ax=ax, colormap='tab20')
ax.set_title('Distribución de tópicos por medio')
ax.set_ylabel('Número de artículos')
ax.set_xlabel('Medio')
plt.legend(title='Tópico', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig('topics_by_medium.png', dpi=150)
print("✅ Gráfico tópicos por medio guardado: topics_by_medium.png")
plt.show()

# Heatmap
fig, ax = plt.subplots(figsize=(10, 6))
import seaborn as sns

# Normalizar para heatmap
topic_by_medium_norm = topic_by_medium.div(topic_by_medium.sum(axis=1), axis=0)

sns.heatmap(topic_by_medium_norm, annot=True, fmt='.2%', cmap='YlOrRd', ax=ax, cbar_kws={'label': '% de cobertura'})
ax.set_title('Proporción de tópicos por medio')
ax.set_ylabel('Medio')
ax.set_xlabel('Tópico')
plt.tight_layout()
plt.savefig('topics_heatmap.png', dpi=150)
print("✅ Heatmap guardado: topics_heatmap.png")
plt.show()
```

---

## FASE 5: NOTEBOOK INTEGRADO

### 5.1 Crear notebook con todos resultados

```python
# Este código genera un Jupyter notebook listo para presentar

notebook_code = """
# Entrega 2: Análisis de Sesgo - Período Duque (2018-2022)

## 1. Introducción
Este notebook analiza sesgo de framing en 8 medios colombianos durante el período Duque.

**Corpus:** 708,768 artículos (99.83% con títulos)
**Medios:** El Tiempo, Blu Radio, Caracol, La República, RCN, Cambio, El Espectador, Semana

## 2. Textometría

### 2.1 Ley de Zipf
[Aquí irá gráfico zipf_law.png]

**Hallazgo:** Los títulos Duque siguen distribución Zipf (poder-ley)

### 2.2 Diversidad Léxica
[Aquí irá gráfico lexical_diversity.png]

### 2.3 N-gramas más frecuentes
[Aquí irá gráfico ngrams.png]

## 3. Análisis de Eventos Polémicos

### 3.1 Cobertura de eventos
[Aquí irá gráfico eventos_framing.png]

### 3.2 Tabla resumida
[Aquí irá tabla eventos_polemicos.csv]

## 4. Topic Modeling

### 4.1 Optimización de K
[Aquí irá gráfico lda_optimization.png]

**K óptimo encontrado:** {optimal_k} tópicos

### 4.2 Tópicos detectados
[Aquí irán tópicos con palabras clave]

### 4.3 Distribución por medio
[Aquí irá gráfico topics_by_medium.png]

[Aquí irá heatmap topics_heatmap.png]

## 5. Conclusiones

1. **Textometría**: El corpus Duque tiene...
2. **Eventos**: Cobertura diferencial de...
3. **Tópicos**: Medios se focalizan en...

## 6. Recomendaciones

...
"""

print("✅ Estructura notebook generada")
print("→ Agregar gráficos manualmente en Jupyter o exportar a .ipynb")
```

---

## FASE 6: EXPORTAR PARA INFORME Y PPT

### 6.1 Crear tabla resumen

```python
# Tabla resumen para informe

resumen_analisis = pd.DataFrame({
    'Métrica': [
        'Total artículos',
        'Períodos análisis',
        'Medios analizados',
        'Vocabulario único',
        'Bigramas significativos',
        'Eventos polémicos',
        'Tópicos detectados',
        'Coherence Score'
    ],
    'Valor': [
        f'{len(df):,}',
        'Agosto 2018 - Agosto 2022',
        '8',
        f'{len(word_freq):,}',
        '50+',
        '3 (Reforma, Conflicto, Corrupción)',
        f'{optimal_k}',
        f'{max(coherence_scores):.4f}'
    ]
})

print("📊 TABLA RESUMEN PARA INFORME")
print(resumen_analisis.to_string(index=False))

resumen_analisis.to_csv('resumen_analisis.csv', index=False)
```

### 6.2 Exportar all visualizations

```python
import os

# Crear carpeta de exports
os.makedirs('exports', exist_ok=True)

archivos_export = [
    'zipf_law.png',
    'lexical_diversity.png',
    'ngrams.png',
    'eventos_framing.png',
    'lda_optimization.png',
    'topics_by_medium.png',
    'topics_heatmap.png',
    'resumen_analisis.csv',
    'eventos_polemicos.csv',
    'bigrams_top100.csv',
    'trigrams_top50.csv'
]

print("📁 Exportando archivos...")
for archivo in archivos_export:
    if os.path.exists(archivo):
        os.system(f'cp {archivo} exports/')
        print(f"  ✅ {archivo}")

print("\n✅ Todos los archivos exportados a carpeta 'exports/'")
print("→ Usar estos para informe LaTeX y PPT")
```

---

## CHECKLIST FINAL

- [ ] ✅ Fase 1: Corpus cargado y limpiado
- [ ] ✅ Fase 2: Textometría completada (Zipf, diversidad, n-gramas)
- [ ] ✅ Fase 3: Eventos polémicos analizados
- [ ] ✅ Fase 4: Topic modeling entrenado (LDA óptimo)
- [ ] ✅ Fase 5: Notebook integrado con resultados
- [ ] ✅ Fase 6: Visualizaciones exportadas

---

## PRÓXIMOS PASOS (Manual)

1. **Informe LaTeX** (`entrega2.tex`):
   - Insertar gráficos de exports/
   - Escribir interpretaciones
   - Agregar referencias

2. **Presentación PPT**:
   - 9-10 slides
   - Usar gráficos generados
   - Énfasis en hallazgos de sesgo

3. **Validación**:
   - Revisar notebook interactivo (lda_visualization.html)
   - Confirmar hallazgos con equipo

---

## TIEMPO ESTIMADO

- **Ejecución código:** 30-45 min (incluye LDA 5-10 min)
- **Informe + PPT:** 2-3 horas
- **Total:** 3-4 horas

**¡Listo para presentar!** 🚀
