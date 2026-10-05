# 📊 REPORTE DE RESEARCH: Resultados Entrega 2
## Análisis de Sesgo Editorial en Medios Colombianos (2018-2022)

**Generado**: [FECHA]  
**Investigador**: [USUARIO]  
**Datos**: Corpus Duque (708,768 artículos)  
**Validación**: Verificado contra archivos de salida

---

## I. RESUMEN EJECUTIVO

### ¿Qué se hizo?
Se procesaron 708,768 artículos de 6 medios colombianos (2018-2022) con tres métodos complementarios:
- Textometría (Ley de Zipf, diversidad léxica, n-gramas)
- Análisis de eventos polémicos (3 temas)
- Topic modeling (LDA con K=3-15, K=5 óptimo)

### 3 Hallazgos Clave
1. **[HALLAZGO 1 - Verificado]**
   - Cifra exacta: [_____]
   - Interpretación: [_____]
   - Fuente: [archivo CSV/JSON]

2. **[HALLAZGO 2 - Verificado]**
   - Cifra exacta: [_____]
   - Interpretación: [_____]
   - Fuente: [archivo CSV/JSON]

3. **[HALLAZGO 3 - Verificado]**
   - Cifra exacta: [_____]
   - Interpretación: [_____]
   - Fuente: [archivo CSV/JSON]

### 2 Limitaciones Críticas
1. **[Limitación 1]**: [Impacto en conclusiones]
2. **[Limitación 2]**: [Impacto en conclusiones]

### Conclusión Principal
[Una frase: qué se puede afirmar con confianza]

---

## II. METODOLOGÍA

### II.1 Corpus

| Aspecto | Valor | Validación |
|---------|-------|-----------|
| **Artículos totales** | 708,768 | ✅ resumen.json |
| **Período** | 2018-08-07 a 2022-08-07 | ✅ entrada |
| **Medios** | 6 outlets | ✅ source_id único |
| **Títulos derivados** | 99.83% | ✅ title_source |

**Distribución por medio:**

| Medio | Artículos | % | Validación |
|-------|-----------|-----|-----------|
| [Medio1] | [#] | [%] | ✅ |
| [Medio2] | [#] | [%] | ✅ |
| [Medio3] | [#] | [%] | ✅ |
| [Medio4] | [#] | [%] | ✅ |
| [Medio5] | [#] | [%] | ✅ |
| [Medio6] | [#] | [%] | ⚠️ |

**Notas sobre medios:**
- [Medio con particularidades]: [Explicación]

### II.2 Métodos

#### Textometría
```
Herramientas: NLTK, scikit-learn
Métricas:
  - Ley de Zipf: log-log regression (rango vs frecuencia)
  - TTR: unique_words / total_words
  - MSTTR: TTR sobre segmentos de 50 tokens
  - Yule's K: índice de diversidad robusta
  - N-gramas: bigramas + trigramas (top 30 y 20)
```

#### Análisis de Eventos
```
Metodología:
  1. Definir palabras clave para 3 temas
  2. Buscar en títulos (case-insensitive)
  3. Contar coincidencias por medio
  4. Calcular proporción: (count/total) * 100
  5. Test chi-square para significancia
```

#### Topic Modeling
```
Modelo: Latent Dirichlet Allocation (Gensim)
Configuración:
  - K: 3, 5, 7, 10, 15 tópicos
  - Pasadas: 10
  - Iteraciones: 400
  - Random state: 42
  - Vocabulario: 10,000 términos
Métrica de optimización: Coherence Score (c_v)
```

### II.3 Validación

**Tests ejecutados:**
```
✅ 9/9 tests unitarios pasados
✅ Notebook 30 celdas ejecutadas sin errores
✅ PDF compilado sin errores LaTeX
✅ PPT validado (geometría OK)
✅ Archivos CSV verificados contra JSON
```

**Verificación de integridad:**
```
✅ Corpus entrada = corpus procesado
✅ Período = rango de fechas
✅ Medios = source_id únicos
✅ Figuras = 8 PNG generados
```

---

## III. RESULTADOS DETALLADOS

### III.1 Textometría

#### Ley de Zipf

**Pregunta**: ¿Sigue el idioma de títulos la ley de Zipf (f ∝ r^-α)?

**Resultado**:
- Correlación encontrada: r = [_____]
- Interpretación: [_____]
- **Validación**: Gráfico en zipf_law.png

```python
# Verificar localmente:
import json
results = json.load(open("resultados/resumen.json"))
print(f"Correlación Zipf: {results['zipf_correlation']}")
```

**Conclusión**: [Confirmada/Parcial/Rechazada]

---

#### Diversidad Léxica

**Pregunta**: ¿Qué medios tienen vocabulario más diverso?

**Resultado**:

| Medio | TTR | MSTTR | Yule's K | Ranking |
|-------|-----|-------|----------|---------|
| [Medio1] | [_] | [_] | [_] | 🥇 |
| [Medio2] | [_] | [_] | [_] | 🥈 |
| [Medio3] | [_] | [_] | [_] | 🥉 |
| [Medio4] | [_] | [_] | [_] | 4 |
| [Medio5] | [_] | [_] | [_] | 5 |
| [Medio6] | [_] | [_] | [_] | 6 |

**Validación**: diversidad_por_medio.csv  
**Visualización**: lexical_diversity.png

**Análisis**:
- Diferencia máxima (TTR): [_____]
- Variación relativa: [___]%
- Significancia: [Sí/No estadística]

**Conclusión**: [_____]

---

#### N-gramas

**Pregunta**: ¿Qué palabras coocurren más frecuentemente?

**Top 10 Bigramas** (Global):
1. [bigram] - [frecuencia]
2. [bigram] - [frecuencia]
3. ...

**Interpretación**:
- ¿Artefactos de formato? [Sí/No] → [Ejemplos]
- ¿Patrones editoriales? [Sí/No] → [Ejemplos]
- ¿Diferencias por medio? [Sí/No] → [Ejemplos]

**Validación**: ngrams.png + CSV de bigramas/trigramas

**Conclusión**: [_____]

---

### III.2 Análisis de Eventos Polémicos

**Pregunta**: ¿Hay diferencias de cobertura en temas polémicos?

**Eventos analizados**:
1. Reforma Tributaria (keywords: reforma, tributaria, impuesto)
2. Conflicto Armado (keywords: conflicto, guerrilla, bombardeo)
3. Corrupción (keywords: corrupción, fraude, peculado)

**Resultados por Evento**:

#### Evento 1: [Nombre]

| Medio | Artículos | Total | % Cobertura | Ranking |
|-------|-----------|-------|-------------|---------|
| [Medio1] | [#] | [#] | [%] | 🥇 |
| [Medio2] | [#] | [#] | [%] | 🥈 |
| [Medio3] | [#] | [#] | [%] | 🥉 |
| [Medio4] | [#] | [#] | [%] | 4 |
| [Medio5] | [#] | [#] | [%] | 5 |
| [Medio6] | [#] | [#] | [%] | 6 |

**Chi-square test**: χ² = [___], p = [____]  
**Interpretación**: [Significativo/No significativo]

**Validación**: eventos_polemicos.csv

---

#### Evento 2: [Nombre]
[Tabla similar]

#### Evento 3: [Nombre]
[Tabla similar]

**Análisis Comparativo**:
- Medio que más cubre temas polémicos: [_____]
- Medio que menos cubre: [_____]
- Variación máxima: [____]%
- Conclusión: [_____]

---

### III.3 Topic Modeling (LDA)

**Pregunta**: ¿Cuáles son los temas latentes en el corpus?

#### Optimización de K

| K | Coherence | Modelo | Interpretabilidad |
|---|-----------|--------|-------------------|
| 3 | [_____] | ✅ | [Baja/Media/Alta] |
| 5 | [_____] | ✅ | [Baja/Media/Alta] |
| 7 | [_____] | ✅ | [Baja/Media/Alta] |
| 10 | [_____] | ✅ | [Baja/Media/Alta] |
| 15 | [_____] | ✅ | [Baja/Media/Alta] |

**K Óptimo**: 5 (Coherence = [_____])  
**Validación**: lda_optimization.csv + lda_optimization.png

---

#### Descripción de los 5 Tópicos (K=5)

**Tópico 1**
- Top 10 palabras: [____], [____], [____], ...
- Interpretación temática: [_____]
- Ejemplos de documentos: [Títulos de ejemplo]

**Tópico 2**
- Top 10 palabras: [____], [____], [____], ...
- Interpretación temática: [_____]
- Ejemplos de documentos: [Títulos de ejemplo]

**Tópico 3**
[Similar]

**Tópico 4**
[Similar]

**Tópico 5**
[Similar]

---

#### Distribución por Medio

| Medio | Tópico 1 | Tópico 2 | Tópico 3 | Tópico 4 | Tópico 5 |
|-------|----------|----------|----------|----------|----------|
| [M1] | [%] | [%] | [%] | [%] | [%] |
| [M2] | [%] | [%] | [%] | [%] | [%] |
| [M3] | [%] | [%] | [%] | [%] | [%] |
| [M4] | [%] | [%] | [%] | [%] | [%] |
| [M5] | [%] | [%] | [%] | [%] | [%] |
| [M6] | [%] | [%] | [%] | [%] | [%] |

**Validación**: topics_by_medium_norm.csv + topics_heatmap.png

**Análisis**:
- ¿Distribución uniforme (~20% cada)? [Sí/No]
- Medio que más cubre Tópico [X]: [Medio] ([%])
- Variación por tópico: [Máx - Mín] = [%]
- ¿Hay clusters de medios? [Sí/No] → [Cuáles]

**Conclusión**: [_____]

---

## IV. ANÁLISIS DE DIFERENCIAS

### ¿Qué explica las variaciones observadas?

**Hipótesis 1**: [_____]  
**Evidencia**: [_____]  
**Conclusión**: [Soportada/Rechazada]

**Hipótesis 2**: [_____]  
**Evidencia**: [_____]  
**Conclusión**: [Soportada/Rechazada]

---

### Outliers Identificados

| Outlier | Métrica | Valor | Explicación |
|---------|---------|-------|-------------|
| [Medio/Tema] | [Métrica] | [Valor extremo] | [Explicación] |
| [Medio/Tema] | [Métrica] | [Valor extremo] | [Explicación] |

---

## V. LIMITACIONES

### Limitación 1: [Nombre]
- **Impacto**: Afecta conclusiones sobre [_____]
- **Severidad**: [Baja/Media/Alta]
- **Mitigación**: [_____]

### Limitación 2: [Nombre]
[Similar estructura]

### Limitación 3: [Nombre]
[Similar estructura]

---

## VI. CONCLUSIONES

### Qué se Puede Afirmar ✅

1. **[Afirmación 1]** - Datos verificados, conclusión robusta
2. **[Afirmación 2]** - Datos verificados, conclusión robusta
3. **[Afirmación 3]** - Datos verificados, conclusión robusta

### Qué NO se Puede Afirmar ❌

1. ❌ Sesgo editorial confirmado (falta análisis cualitativo)
2. ❌ Agenda editorial uniforme (variabilidad observada)
3. ❌ Causalidad (solo correlaciones observadas)

### Recomendaciones para Trabajo Futuro 🔲

1. Extraer cuerpos HTML completos (no solo títulos)
2. Análisis manual de framing en muestra representativa
3. Comparación temporal Duque vs Petro
4. Validación con expertos en sesgo mediático

---

## 📚 Referencias de Datos

| Archivo | Tipo | Función |
|---------|------|---------|
| resumen.json | JSON | Metadatos principales |
| lda_optimization.csv | CSV | Coherencia por K |
| topics_by_medium_norm.csv | CSV | Distribución tópicos |
| eventos_polemicos.csv | CSV | Cobertura temática |
| diversidad_por_medio.csv | CSV | Métricas léxicas |
| zipf_law.png | PNG | Visualización Zipf |
| lexical_diversity.png | PNG | Visualización TTR |
| events_framing.png | PNG | Gráfico eventos |
| lda_optimization.png | PNG | Curva coherencia |
| topics_by_medium.png | PNG | Barras tópicos |
| topics_heatmap.png | PNG | Mapa calor |

---

## ✅ Checklist de Validación

- [ ] Todos los números verificados contra CSV/JSON
- [ ] Gráficos existentes y válidos
- [ ] Conclusiones respaldadas por datos
- [ ] Limitaciones documentadas
- [ ] Recomendaciones claras
- [ ] Formato profesional
- [ ] Listo para Replit

---

**Reporte Generado**: [FECHA]  
**Validación Final**: [✅ COMPLETO / ⚠️ INCOMPLETO / ❌ FALTA REVISAR]  
**Listo para Replit**: [✅ SÍ / ⚠️ PARCIAL / ❌ NO]

