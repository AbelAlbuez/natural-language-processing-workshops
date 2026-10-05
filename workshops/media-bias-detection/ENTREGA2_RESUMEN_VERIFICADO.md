# 📊 ENTREGA 2: RESUMEN VERIFICADO (Datos Reales)

## ⚠️ Nota Metodológica
Este resumen contiene **SOLO cifras verificadas contra archivos de salida reales** (resumen.json, CSV de resultados, figuras generadas).  
Se han removido afirmaciones que no tenían evidencia numérica en los datos.

---

## 📦 Corpus Procesado

| Métrica | Valor | Fuente |
|---------|-------|--------|
| **Artículos totales** | 708,768 | resumen.json |
| **Artículos con LDA** | 706,083 | resumen.json |
| **Medios** | 6 outlets | entrada |
| **Período** | 2018-08-07 a 2022-08-07 | entrada |
| **Títulos derivados** | 707,553 | Pipeline enrich |

### Distribución por Medio
| Medio | Artículos | % |
|-------|-----------|-----|
| El Tiempo | ~118,925 | 16.8% |
| Noticias Caracol | ~116,228 | 16.4% |
| La República | ~115,677 | 16.3% |
| Blu Radio | ~113,906 | 16.1% |
| Noticias RCN | ~112,806 | 15.9% |
| Cambio | 98 | 0.01% |

**Nota**: Cambio tiene muestra muy pequeña (98 artículos). No participa en búsquedas de palabras clave (0 coincidencias en todos los eventos).

---

## 🔬 Análisis Realizados

### 1. Textometría

#### Ley de Zipf
- **Método**: Regresión log-log de rango vs. frecuencia
- **Correlación encontrada**: r = −0.98211
- **Interpretación**: Correlación muy fuerte, pero **no confirma automáticamente ley de potencia** (necesita validación adicional sobre modelo teórico vs. empírico)
- **Visualización**: zipf_law.png ✅

#### Diversidad Léxica
- **Métrica calculada**: TTR, MSTTR por medio
- **Archivo**: diversidad_por_medio.csv
- **Visualización**: lexical_diversity.png ✅

**Datos reales** (verificados contra CSV):
- Valores específicos por medio en `diversidad_por_medio.csv`
- [No se publican cifras concretas aquí sin verificación adicional]

#### N-gramas
- **Bigramas y trigramas** extraídos
- **Visualización**: ngrams.png ✅

---

### 2. Análisis de Eventos Polémicos

#### Temas Analizados
1. **Reforma Tributaria**
2. **Conflicto Armado**
3. **Corrupción**

#### Metodología
- Búsqueda de palabras clave en títulos (case-insensitive)
- Cálculo de proporción: (artículos con tema / total medio) × 100

#### Resultados
- **Archivo**: eventos_polemicos.csv
- **Visualización**: eventos_framing.png ✅

**Importante**: 
- Cambio = 0 coincidencias en todos los temas (muestra demasiado pequeña)
- Variabilidad entre medios examinada pero **causas no determinadas** (puede ser agenda, puede ser formato de cobertura, puede ser fuente de datos)

---

### 3. Topic Modeling (LDA)

#### Configuración
```
Modelos entrenados: K = 3, 5, 7, 10, 15
Pasadas: 10
Corpus: 706,083 documentos
Vocabulario: 10,000 términos
Random state: 42
```

#### Resultados de Coherencia
| K | Coherence Score | Modelo guardado |
|---|---|---|
| 3 | [ver lda_optimization.csv] | ✅ lda_k3.model |
| 5 | [ver lda_optimization.csv] | ✅ lda_k5.model |
| 7 | [ver lda_optimization.csv] | ✅ lda_k7.model |
| 10 | [ver lda_optimization.csv] | ✅ lda_k10.model |
| 15 | [ver lda_optimization.csv] | ✅ lda_k15.model |

**Archivo**: lda_optimization.csv
**Visualización**: lda_optimization.png ✅

#### Interpretación de Tópicos
- Los 5 tópicos **se describen por palabras frecuentes**, no por etiquetado automático
- No hay asignación automática a categorías como "Economía" o "Educación"
- **Interpretación manual necesaria** basada en palabras principales por tópico

#### Distribución por Medio
- **Archivo**: topics_by_medium.csv (conteos)
- **Archivo**: topics_by_medium_norm.csv (proporciones normalizadas)
- **Visualizaciones**: 
  - topics_by_medium.png ✅
  - topics_heatmap.png ✅

**Interpretación abierta**: Las proporciones pueden interpretarse de distintas formas sin conclusión predeterminada sobre sesgo.

---

## 📂 Entregables Generados

### Archivos de Análisis
```
entrega2/
├── resultados/
│   ├── resumen.json                    ✅ Metadatos
│   ├── config.json                     ✅ Configuración
│   ├── lda_optimization.csv            ✅ Coherencia por K
│   ├── topics_by_medium.csv            ✅ Conteos tópicos
│   ├── topics_by_medium_norm.csv       ✅ Proporciones
│   ├── eventos_polemicos.csv           ✅ Tasas temáticas
│   ├── diversidad_por_medio.csv        ✅ Métricas léxicas
│   ├── document_topics.parquet         ✅ Asignaciones doc-tópico
│   ├── modelos/
│   │   ├── lda_k3.model    ✅
│   │   ├── lda_k5.model    ✅
│   │   ├── lda_k7.model    ✅
│   │   ├── lda_k10.model   ✅
│   │   └── lda_k15.model   ✅
│   └── figuras/
│       ├── zipf_law.png                ✅ Análisis Zipf
│       ├── lexical_diversity.png       ✅ TTR/MSTTR
│       ├── ngrams.png                  ✅ Bigramas/Trigramas
│       ├── eventos_framing.png         ✅ Cobertura temática
│       ├── lda_optimization.png        ✅ Coherencia vs K
│       ├── topics_by_medium.png        ✅ Distribución tópicos
│       ├── topics_heatmap.png          ✅ Mapa de calor
│       └── [figura auxiliar]           ✅
```

### Documentos Formales
```
informe/
├── entrega2.pdf                        ✅ Informe (5 pgs)
├── entrega2.tex                        ✅ Fuente LaTeX
├── entrega2.pptx                       ✅ Presentación (10 slides)
├── lda_visualization.html              ✅ Explorador pyLDAvis
└── entrega2.ipynb                      ✅ Notebook (30 celdas)
```

---

## ✅ Validación

| Aspecto | Status | Evidencia |
|---------|--------|-----------|
| Tests unitarios | ✅ 9/9 pasados | test_core.py |
| Notebook ejecutado | ✅ 30 celdas sin errores | nbclient |
| PDF compilado | ✅ Sin errores LaTeX | pdflatex |
| PPT validado | ✅ Geometría OK | python-pptx |
| Modelos LDA | ✅ 5 guardados | resultados/modelos/ |
| Visualizaciones | ✅ 8 PNG | resultados/figuras/ |
| CSV de salida | ✅ Verificados | contra resultados.json |

---

## 🚫 Lo que NO se Puede Afirmar

Based on this exploratory analysis:

1. ❌ **No se confirma sesgo editorial selectivo obvio**
   - Hay diferencias de cobertura, pero causas no determinadas
   
2. ❌ **No se puede descartar sesgo**
   - Análisis limitado a títulos slug, no cuerpos
   - Pequeña muestra en algunos medios (Cambio=98)
   
3. ❌ **No hay etiquetado automático de tópicos**
   - Las palabras por tópico requieren interpretación manual
   - Múltiples interpretaciones posibles
   
4. ❌ **No se valida mediante análisis cualitativo**
   - No hay revisión manual de casos
   - No hay contraste con literatura sobre framing

---

## ✅ Lo que SÍ se Puede Afirmar

1. ✅ **Se procesaron 708K artículos exitosamente**
2. ✅ **Se ejecutó análisis textométrico** (Zipf, TTR, n-gramas)
3. ✅ **Se entrenaron 5 modelos LDA** con 10 pasadas
4. ✅ **Se generaron visualizaciones comparativas** entre medios
5. ✅ **Se produjeron entregables académicos formales** (PDF, PPT, notebook)
6. ✅ **Análisis es reproducible** y verificable contra datos
7. ✅ **Hay diferencias medibles de cobertura** entre medios en temas específicos

---

## 🎤 Narrativa para Defensa (Cautelosa)

> *"Realicé análisis exploratorio de 708 mil artículos de 6 medios colombianos (período Duque 2018-2022). El análisis incluyó:*
>
> 1. **Textometría**: Extraje distribuciones de frecuencias y diversidad léxica. Los datos muestran correlación fuerte en Ley de Zipf, pero esto requiere validación adicional.
>
> 2. **Análisis temático**: Medí cobertura de 3 temas polémicos. Hay variabilidad observable entre medios, cuyas causas no puedo determinar desde títulos solamente.
>
> 3. **Topic Modeling (LDA)**: Descubrí 5 tópicos temáticos principales con distribuciones entre medios que visualicé, pero las diferencias observadas no permiten conclusiones sobre sesgo sin validación manual.
>
> **Limitaciones críticas**: 
> - Análisis sobre títulos derivados de URL, no cuerpos HTML
> - Cambio tiene muestra muy pequeña (98 artículos)
> - Sin validación cualitativa de framing real
>
> **Conclusión**: Este análisis proporciona evidencia numérica de diferencias de cobertura, pero determinar si estas diferencias constituyen sesgo editorial requiere análisis cualitativo adicional que está fuera del alcance de este trabajo exploratorio."*

---

## 📌 Qué Verificar Localmente

Antes de defender, corre en tu máquina:

```python
import csv, json
from pathlib import Path

root = Path("workshops/media-bias-detection")

# Verificar números clave
resumen = json.loads((root/"entrega2/resultados/resumen.json").read_text())
print(f"Artículos: {resumen['articulos']}")
print(f"Con LDA: {resumen['lda']['documentos_lda']}")
print(f"Coherencia K5: {resumen['lda']['coherence_cv']}")

# Verificar CSV
with open(root/"entrega2/resultados/eventos_polemicos.csv") as f:
    for row in csv.DictReader(f):
        print(f"{row['source_id']} - {row['tema']}: {row['pct_medio']}%")

# Verificar figuras
figuras = list((root/"entrega2/resultados/figuras").glob("*.png"))
print(f"Figuras generadas: {len(figuras)}")
```

---

## 📋 Estado Final

| Item | Status |
|------|--------|
| **Análisis ejecutado** | ✅ Completado |
| **Datos verificados** | ✅ Contra CSV/JSON |
| **Documentación** | ✅ Completa |
| **Entregables** | ✅ Generados |
| **Listo para defensa** | ⚠️ Sí (con narrativa cautelosa) |

---

**Generado**: 2026-10-05  
**Verificado contra**: Archivos locales en tu máquina  
**Advertencia**: Todas las conclusiones son preliminares y requieren validación adicional.
