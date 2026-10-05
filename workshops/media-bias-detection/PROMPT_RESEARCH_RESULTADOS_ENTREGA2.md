# 🔬 PROMPT: Deep Research de Resultados Entrega 2

## Objetivo
Investigar a fondo los resultados generados en Entrega 2, validarlos contra datos brutos, extraer insights, identificar limitaciones, y producir un reporte ejecutivo que sirva como base para documentación en Replit.

---

## 📋 Fases del Research

### FASE 1: Validación de Integridad de Datos

**Preguntas a investigar:**

1. **¿Coincide el corpus procesado con la entrada?**
   - Verificar: `resumen.json['articulos']` == conteo en duque-candidatos.parquet
   - Verificar: Rango de fechas coincide con período esperado
   - Verificar: 6 medios confirmados en columna source_id

2. **¿Qué pasó con Cambio (la muestra pequeña)?**
   - Contar artículos reales de Cambio en entrada
   - Verificar por qué es tan pequeño (¿filtrado en pipeline? ¿data faltante?)
   - ¿Es representativo para análisis?

3. **¿Los títulos derivados realmente tienen 99.83% cobertura?**
   - Verificar: NULL count en columna title antes/después enrich
   - Verificar: Diferencia entre title_source (slug, sitemap, extracted)
   - ¿Qué URLs no fueron derivables?

**Cómo investigar:**
```python
import pandas as pd
import json

# Cargar entrada
df = pd.read_parquet("duque-candidatos.parquet")

# Contar por medio
print(df['source_id'].value_counts())

# Verificar período
print(df['published_date'].min(), df['published_date'].max())

# Cargar metadatos generados
resumen = json.loads(open("entrega2/resultados/resumen.json").read())
print(f"Artículos en entrada: {len(df)}")
print(f"Artículos en resumen: {resumen['articulos']}")

# Investigar Cambio específicamente
cambio_df = df[df['source_id'] == 'cambio']
print(f"\nCambio en entrada: {len(cambio_df)}")
print(f"Cambio sin titulo: {cambio_df['title'].isna().sum()}")
print(f"Cambio con titulo: {cambio_df['title'].notna().sum()}")
```

---

### FASE 2: Análisis de Textometría

**Preguntas a investigar:**

1. **¿Qué significa la correlación Zipf r=-0.98211?**
   - ¿Es significativa la diferencia respecto a r=-1.0 (potencia pura)?
   - ¿Hay outliers en la distribución?
   - ¿Se cumple ley de Zipf en todos los medios por separado?

2. **¿Qué medios realmente tienen TTR diferente?**
   - Cargar `diversidad_por_medio.csv`
   - Graficar TTR por medio (bar chart)
   - Calcular diferencias relativas
   - ¿Hay diferencias estadísticamente significativas o aleatorias?

3. **¿Qué n-gramas dominan y por qué?**
   - Cargar bigramas/trigramas
   - ¿Son artefactos de formato o patrones editoriales?
   - ¿Hay bigramas específicos por medio o son globales?

**Cómo investigar:**
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Cargar diversidad
diversity = pd.read_csv("entrega2/resultados/diversidad_por_medio.csv")
print(diversity[['source_id', 'ttr_agregado', 'msttr_50_agregado']])

# Visualizar
fig, ax = plt.subplots(figsize=(10,6))
ax.bar(diversity['source_id'], diversity['ttr_agregado'])
ax.set_title("TTR por Medio")
ax.set_ylabel("TTR (diversidad léxica)")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("ttc_por_medio.png")

# Calcular diferencia máx-mín
print(f"TTR range: {diversity['ttr_agregado'].min():.4f} - {diversity['ttr_agregado'].max():.4f}")
print(f"Diferencia: {diversity['ttr_agregado'].max() - diversity['ttr_agregado'].min():.4f}")
print(f"Variación %: {((diversity['ttr_agregado'].max() - diversity['ttr_agregado'].min()) / diversity['ttr_agregado'].mean() * 100):.1f}%")
```

---

### FASE 3: Análisis de Eventos Polémicos

**Preguntas a investigar:**

1. **¿Cuál es el patrón de cobertura por evento y medio?**
   - Cargar `eventos_polemicos.csv`
   - Crear tabla resumen (medios x eventos)
   - ¿Hay medio que domina cada evento?
   - ¿Hay correlación entre medios en cobertura?

2. **¿Cambio realmente tiene 0 coincidencias?**
   - Verificar manualmente búsquedas de palabras clave en Cambio
   - ¿Es porque no cubre esos temas o porque los títulos no contienen keywords?
   - ¿Qué temas sí cubre Cambio si existe?

3. **¿Las diferencias son significativas o aleatorias?**
   - Chi-square test: ¿hay relación significativa entre medio y evento?
   - ¿O es solo ruido de muestreo?

**Cómo investigar:**
```python
import pandas as pd
from scipy.stats import chi2_contingency

# Cargar eventos
eventos = pd.read_csv("entrega2/resultados/eventos_polemicos.csv")
print(eventos.head(20))

# Crear tabla pivote
pivot = eventos.pivot_table(
    values='count_tema', 
    index='source_id', 
    columns='tema', 
    fill_value=0
)
print(pivot)

# Normalizar por total de medio
for col in pivot.columns:
    pivot[col] = pivot[col] / pivot.sum(axis=1) * 100

print("\nProporción (%):")
print(pivot.round(2))

# Test de independencia
contingency_table = pivot.astype(int)
chi2, p_value, dof, expected = chi2_contingency(contingency_table)
print(f"\nChi-square test: χ²={chi2:.2f}, p={p_value:.4f}")
if p_value < 0.05:
    print("→ Hay relación significativa entre medio y evento (p<0.05)")
else:
    print("→ No hay relación significativa (p>=0.05)")
```

---

### FASE 4: Análisis de Topic Modeling

**Preguntas a investigar:**

1. **¿Por qué K=5 es óptimo?**
   - Cargar `lda_optimization.csv`
   - Graficar coherencia vs K
   - ¿Es clara la diferencia o marginal?
   - ¿Hay ruido en las métricas?

2. **¿Qué representan realmente los 5 tópicos?**
   - Cargar modelo K=5
   - Extraer top 10 palabras por tópico
   - ¿Son interpretables? ¿Tienen estructura temática?
   - ¿Hay solapamiento entre tópicos?

3. **¿Qué tan diferente es la distribución entre medios?**
   - Cargar `topics_by_medium_norm.csv`
   - ¿La proporción es uniforme (~20% cada) o hay variación?
   - ¿Qué medio se diferencia más?
   - ¿Hay clusters de medios similares?

4. **¿Hay documentos sin tópico dominante?**
   - Verificar asignaciones en `document_topics.parquet`
   - ¿Cuántos tienen confianza baja (<0.3)?
   - ¿Hay correlación entre confianza y cobertura de palabras?

**Cómo investigar:**
```python
import pandas as pd
import json
from gensim.models import LdaModel
import numpy as np

# Cargar coherencia
coherence = pd.read_csv("entrega2/resultados/lda_optimization.csv")
print(coherence)
print(f"K óptimo: {coherence.loc[coherence['coherence_cv'].idxmax(), 'K']}")

# Cargar modelo K=5
model = LdaModel.load("entrega2/resultados/modelos/lda_k5.model")

# Tópicos principales
print("\n5 Tópicos principales (K=5):")
for topic_id in range(5):
    words = model.show_topic(topic_id, topn=10)
    print(f"Tópico {topic_id}: {[w[0] for w in words]}")

# Distribución por medio
topics_medium = pd.read_csv("entrega2/resultados/topics_by_medium_norm.csv", index_col=0)
print("\nDistribución normalizada por tópico:")
print(topics_medium.round(3))

# Estadísticas
print(f"\nRango por tópico:")
for topic in topics_medium.columns:
    print(f"  {topic}: {topics_medium[topic].min():.1%} - {topics_medium[topic].max():.1%}")

# Asignaciones de documentos
doc_topics = pd.read_parquet("entrega2/resultados/document_topics.parquet")
print(f"\nDocumentos sin tópico dominante (confidence<0.3): {(doc_topics['topic_confidence'] < 0.3).sum()}")
print(f"Confianza promedio: {doc_topics['topic_confidence'].mean():.3f}")
```

---

### FASE 5: Síntesis e Insights

**Preguntas finales:**

1. **¿Cuáles son los 3 hallazgos principales?**
   - Validados contra datos
   - Con confianza en las métricas
   - Relevantes para sesgo editorial

2. **¿Qué limitaciones críticas hay?**
   - Tamaño de muestra (Cambio)
   - Cobertura de datos (títulos slug vs cuerpos)
   - Inferencias causales imposibles

3. **¿Qué conclusiones seguras se pueden hacer?**
   - Diferencias observadas ✅
   - Sesgo editorial confirmado ❌
   - Agenda común ❌
   - Necesidad de validación cualitativa ✅

4. **¿Qué recomendaciones hay para trabajo futuro?**
   - Extracción de cuerpos HTML
   - Análisis manual de framing
   - Comparación Duque vs Petro
   - Series temporales

---

## 📊 Estructura del Reporte a Generar

### I. Resumen Ejecutivo (1 página)
- Qué se hizo
- 3 hallazgos clave
- 2 limitaciones críticas
- 1 conclusión

### II. Metodología (2 páginas)
- Corpus: origen, tamaño, período
- Métodos: textometría, eventos, LDA
- Validación: tests unitarios, reproducibilidad

### III. Resultados Detallados (5 páginas)
- 3.1 Textometría
  - Ley de Zipf (gráfico + análisis)
  - Diversidad léxica (tabla + interpretación)
  - N-gramas (top 10 + artefactos)
  
- 3.2 Eventos Polémicos
  - Tabla de cobertura por medio/evento
  - Chi-square test (significancia)
  - Visualización comparativa
  
- 3.3 Topic Modeling
  - Curva de coherencia (K óptimo)
  - Descripción de 5 tópicos
  - Distribución por medio (heatmap)
  - Documentos por tópico

### IV. Análisis de Diferencias (3 páginas)
- ¿Dónde hay más variación? (medium o event)
- ¿Cuáles son outliers?
- ¿Hay clusters de medios similares?
- ¿Qué explica las diferencias?

### V. Limitaciones (2 páginas)
- Muestra pequeña (Cambio)
- Títulos slug sin validación
- Sin análisis cualitativo
- Sin información de intención editorial

### VI. Conclusiones (1 página)
- Qué se puede afirmar
- Qué queda pendiente
- Recomendaciones para Replit

---

## 🎯 Outputs del Research

1. **RESEARCH_REPORT_ENTREGA2.md** (15-20 páginas)
   - Investigación completa
   - Verificación de cada aspecto
   - Insights y análisis profundo

2. **REPLIT_DOCUMENTATION_FROM_RESEARCH.md**
   - Versión simplificada para usuarios
   - Basada en hallazgos del research
   - Con ejemplos ejecutables

3. **DATA_INSIGHTS_TABLES.csv**
   - Tablas de referencia rápida
   - Para gráficos en Replit
   - Verificadas contra fuentes

4. **RESEARCH_VALIDATION_CHECKLIST.md**
   - Qué se validó ✅
   - Qué no se pudo validar ⚠️
   - Qué quedó pendiente 🔲

---

## 🚀 Cómo Ejecutar Este Research

### Opción A: En Claude (Simple)
1. Copia este prompt
2. Adjunta los CSV de resultados
3. Pide: "Haz el research según las 5 fases"
4. Genera reporte

### Opción B: En tu Máquina (Reproducible)
```bash
cd workshops/media-bias-detection

# Ejecuta scripts de investigación
python research_phase1_data_validation.py
python research_phase2_textometrics.py
python research_phase3_events.py
python research_phase4_lda.py
python research_phase5_synthesis.py

# Genera reporte
python generate_research_report.py
```

### Opción C: En Replit (Cloud)
```bash
# Clone repo
git clone ...
cd workshops/media-bias-detection

# Run research
python -c "
import subprocess
phases = [1,2,3,4,5]
for phase in phases:
    subprocess.run([f'python', f'research_phase{phase}.py'])
"
```

---

## 📝 Próximos Pasos

1. **Ejecuta el research** (tu máquina o Replit)
2. **Genera reporte** (RESEARCH_REPORT_ENTREGA2.md)
3. **Crea documentación Replit** (basada en reporte)
4. **Commit y push** a GitHub
5. **Usa en presentación** (con datos verificados)

---

**Prompt Version**: 1.0  
**Propósito**: Deep validation + Replit documentation  
**Output**: Reporte profesional + Guía ejecutable
