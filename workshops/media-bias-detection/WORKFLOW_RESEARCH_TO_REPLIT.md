# 🔄 WORKFLOW: De Research a Documentación Replit

**Objetivo**: Investigar resultados → Generar reporte verificado → Crear documentación Replit  
**Duración**: 2-3 horas  
**Output**: Reporte profesional + Guías Replit  
**Validación**: Datos contra CSV/JSON reales

---

## 📋 El Flujo Completo

```
┌─────────────────────────────────────────────────────────────┐
│                    WORKFLOW COMPLETO                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. RESEARCH (Fase 1-5)                                     │
│     └─→ Investigar datos reales                             │
│         └─→ Verificar contra CSV/JSON                       │
│             └─→ Extraer insights                            │
│                                                              │
│  2. REPORT (Genera documento)                               │
│     └─→ Llenar TEMPLATE_RESEARCH_REPORT.md                 │
│         └─→ Con datos del research                          │
│             └─→ Verificación final                          │
│                                                              │
│  3. REPLIT DOCS (Simplificar para usuarios)                 │
│     └─→ Basar en hallazgos del report                       │
│         └─→ Lenguaje accesible                              │
│             └─→ Ejemplos ejecutables                        │
│                                                              │
│  4. COMMIT & PUSH                                           │
│     └─→ GitHub                                              │
│         └─→ Listo para defensa + Replit                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📍 PASO 1: RESEARCH (2-3 fases del PROMPT)

### Paso 1.1: Descarga el Prompt de Research
```bash
# Ya lo tienes:
PROMPT_RESEARCH_RESULTADOS_ENTREGA2.md
```

### Paso 1.2: Ejecuta Investigación Local (Opción A)

**En tu máquina (donde tienes datos):**

```bash
cd workshops/media-bias-detection

# Abre terminal Python
python3

# Copiar y ejecutar FASE 1: Validación de Integridad
import pandas as pd
import json

df = pd.read_parquet("news-retrieval/exports/duque-candidatos.parquet")
print(f"Corpus entrada: {len(df)} artículos")
print(f"Período: {df['published_date'].min()} a {df['published_date'].max()}")
print(f"Medios: {df['source_id'].unique()}")

resumen = json.load(open("entrega2/resultados/resumen.json"))
print(f"\nCorpus procesado: {resumen['articulos']} artículos")
print(f"Con LDA: {resumen['lda']['documentos_lda']} documentos")

# Validar coincidencia
assert len(df) == resumen['articulos'], "No coinciden!"
print("✅ Datos coinciden")
```

### Paso 1.3: Ejecuta Investigación en Replit (Opción B)

**Crea notebook en Replit:**

```python
# FASE 1: Validación
import pandas as pd, json
df = pd.read_parquet("entrega2/resultados/sample.parquet")  # o adjunta CSV
resumen = json.load(open("entrega2/resultados/resumen.json"))
print(f"Artículos: {resumen['articulos']}")

# FASE 2: Textometría
diversity = pd.read_csv("entrega2/resultados/diversidad_por_medio.csv")
print(diversity)

# FASE 3: Eventos
eventos = pd.read_csv("entrega2/resultados/eventos_polemicos.csv")
print(eventos.sort_values('pct_medio', ascending=False))

# FASE 4: LDA
topics = pd.read_csv("entrega2/resultados/topics_by_medium_norm.csv", index_col=0)
print(topics)

# FASE 5: Síntesis
print("\n3 HALLAZGOS CLAVE:")
print("1. [Completar con datos]")
print("2. [Completar con datos]")
print("3. [Completar con datos]")
```

---

## 📄 PASO 2: REPORT (Genera documento formal)

### Paso 2.1: Llena el Template

**Archivo**: `TEMPLATE_RESEARCH_REPORT.md`

**Secciones a llenar:**

#### I. Resumen Ejecutivo
```
[ ] 3 hallazgos clave (con cifras exactas)
[ ] 2 limitaciones críticas
[ ] 1 conclusión principal
```

**Ejemplo**:
```markdown
### 3 Hallazgos Clave

1. **Ley de Zipf Confirmada**
   - Correlación: r = -0.9821
   - Interpretación: Patrón típico de lenguaje natural
   - Fuente: lda_optimization.csv

2. **Diversidad Léxica Varía entre Medios**
   - Media1 (TTR=0.42) vs Media6 (TTR=0.31) = 35% diferencia
   - Variación: [___]%
   - Fuente: diversidad_por_medio.csv

3. **Tópicos Distribuidos de Manera Similar**
   - K=5 optimal (coherencia=0.356)
   - Rango por tópico: 19-23%
   - Fuente: topics_by_medium_norm.csv
```

#### II. Metodología
```
[ ] Corpus (verificado contra entrada)
[ ] Métodos (con configuración real)
[ ] Validación (tests pasados)
```

#### III. Resultados Detallados
```
[ ] Zipf: gráfico + análisis
[ ] Diversidad: tabla por medio
[ ] N-gramas: top 10 bigramas
[ ] Eventos: tabla comparativa + chi-square
[ ] LDA: K óptimo + 5 tópicos + distribución
```

#### IV. Análisis de Diferencias
```
[ ] ¿Dónde hay más variación? (medio vs tema)
[ ] Outliers identificados
[ ] Clusters de medios
```

#### V. Limitaciones
```
[ ] Cambio (muestra pequeña)
[ ] Títulos slug (no validados)
[ ] Sin análisis cualitativo
[ ] [Otras específicas del análisis]
```

#### VI. Conclusiones
```
[ ] Qué se afirma (✅)
[ ] Qué NO se afirma (❌)
[ ] Recomendaciones (🔲)
```

### Paso 2.2: Valida Cada Tabla

**Para cada tabla numérica:**

```bash
# 1. Abre el CSV correspondiente
grep "medio,tema,count" entrega2/resultados/eventos_polemicos.csv

# 2. Verifica que números coincidan con TEMPLATE_RESEARCH_REPORT.md

# 3. Marca como ✅ si coinciden
```

**Ejemplo**:
```python
# En tu máquina
import pandas as pd

# Cargar CSV
eventos = pd.read_csv("entrega2/resultados/eventos_polemicos.csv")

# Crear tabla para reporte
table = eventos.pivot_table(
    values='count_tema',
    index='source_id',
    columns='tema',
    fill_value=0
)

# Copiar a reporte
print(table.to_markdown())
```

### Paso 2.3: Genera el Reporte Final

**Archivo**: `RESEARCH_REPORT_ENTREGA2.md`

```markdown
# REPORTE DE RESEARCH: Resultados Entrega 2

## I. RESUMEN EJECUTIVO
[Completado con datos verificados]

## II. METODOLOGÍA
[Completado con detalles reales]

## III. RESULTADOS DETALLADOS
[Con tablas y gráficos]

## IV. ANÁLISIS
[Interpretaciones soportadas]

## V. LIMITACIONES
[Honestas y documentadas]

## VI. CONCLUSIONES
[Solo lo que se puede afirmar]
```

---

## 🚀 PASO 3: REPLIT DOCS (Simplificar para usuarios)

### Paso 3.1: Abre el Template

**Archivo**: `REPLIT_DOCUMENTATION_FROM_RESEARCH.md` (ya existe)

Este archivo es una **simplificación del research report** pensada para Replit.

### Paso 3.2: Personalízalo con Tus Hallazgos

**Reemplaza placeholders:**

```markdown
# Reemplaza esto:
[Medio con TTR más alto]

# Con esto:
La República (TTR=0.42)

---

# Reemplaza esto:
[X%] más diverso el #1 vs #6

# Con esto:
35% más diverso
```

### Paso 3.3: Verifica que Tenga:

```
✅ Explicación simple de 3 métodos
✅ Hallazgos con datos reales
✅ Gráficos/archivos referenciados
✅ Limitaciones claras
✅ Narrativa para defensa
✅ Q&A
✅ Links a entregables
✅ Código Python para explorar
```

### Paso 3.4: Crea Versión Replit

**Genera archivo**: `REPLIT_GUIDE_ENTREGA2_FINAL.md`

```markdown
# 🚀 Guía Replit: Análisis Entrega 2

[Contenido de REPLIT_DOCUMENTATION_FROM_RESEARCH.md]
[Personalizado con tus hallazgos]

## 🔬 Datos de Este Análisis

### Hallazgo 1: [Tu hallazgo]
- Cifra: [número verificado]
- Fuente: [archivo CSV específico]
- Gráfico: [PNG específico]

### Hallazgo 2: [Tu hallazgo]
...

## 📊 Cómo Explorar Tú Mismo

### En Excel
1. Descarga: entrega2/resultados/[archivo.csv]
2. ...

### En Python
[Código ejecutable]

### En Replit
[Cómo copiar datos]
```

---

## 💾 PASO 4: COMMIT & PUSH

### Paso 4.1: Stage & Commit

```bash
cd /home/claude/natural-language-processing-workshops

# Agregar archivos nuevos
git add workshops/media-bias-detection/RESEARCH_REPORT_ENTREGA2.md
git add workshops/media-bias-detection/REPLIT_GUIDE_ENTREGA2_FINAL.md

# Commit
git commit -m "docs: research report and Replit guide with verified data

Research Report:
- 5 phases of investigation with findings
- All numbers verified against CSV/JSON
- Professional format ready for evaluation

Replit Guide:
- Simplified explanations for users
- Based on actual research findings
- Code examples and exploration tips
- Defense narrative included

Both documents link to source data and visualizations.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EQANUvPrQ9MkHj5yk7Lhiw"
```

### Paso 4.2: Push

```bash
git push -u origin feature/fase3-architecture-documentation
```

---

## ✅ Checklist Final

### Research Completo
- [ ] Fase 1: Validación de datos ✅
- [ ] Fase 2: Textometría ✅
- [ ] Fase 3: Eventos ✅
- [ ] Fase 4: LDA ✅
- [ ] Fase 5: Síntesis ✅

### Report Generado
- [ ] Resumen ejecutivo ✅
- [ ] Metodología ✅
- [ ] Resultados con datos ✅
- [ ] Análisis ✅
- [ ] Limitaciones ✅
- [ ] Conclusiones ✅
- [ ] Referencias ✅

### Replit Docs
- [ ] Métodos explicados ✅
- [ ] Hallazgos personalizados ✅
- [ ] Limitaciones claras ✅
- [ ] Defensa narrativa ✅
- [ ] Q&A ✅
- [ ] Código ejecutable ✅

### Validación Final
- [ ] Todos los números verificados
- [ ] Todos los links funcionales
- [ ] Gráficos referenciados existen
- [ ] Texto legible y claro
- [ ] Listo para defensa + Replit

### GitHub
- [ ] Commit mensaje descriptivo
- [ ] Push a feature branch
- [ ] Listo para merge a main

---

## 🎯 Resultado Final

```
Tienes 3 documentos:

1. PROMPT_RESEARCH_RESULTADOS_ENTREGA2.md
   ├─ Guía para investigar resultados
   └─ 5 fases estructuradas

2. RESEARCH_REPORT_ENTREGA2.md
   ├─ Reporte profesional (15-20 pgs)
   ├─ Hallazgos verificados
   └─ Conclusiones rigurosas

3. REPLIT_GUIDE_ENTREGA2_FINAL.md
   ├─ Explicaciones simples
   ├─ Datos reales
   └─ Listo para usuarios
```

---

## ⏱️ Cronograma Estimado

```
Fase 1: Research (0.5-1 hora)
  ├─ Ejecutar investigación
  └─ Extraer cifras

Fase 2: Report (1-1.5 horas)
  ├─ Llenar template
  ├─ Verificar números
  └─ Pulir redacción

Fase 3: Replit Docs (0.5-1 hora)
  ├─ Personalizar template
  └─ Agregar ejemplos

Fase 4: GitHub (10 min)
  ├─ Commit
  └─ Push

TOTAL: 2.5-3.5 horas
```

---

## 🎬 Para Empezar Ahora

```bash
# 1. Descarga el prompt
cat PROMPT_RESEARCH_RESULTADOS_ENTREGA2.md

# 2. Ejecuta FASE 1 localmente (5 min)
python3 << 'EOF'
import json, pandas as pd
resumen = json.load(open("entrega2/resultados/resumen.json"))
print(f"Artículos: {resumen['articulos']}")
print("✅ Datos cargados")
EOF

# 3. Completa template del reporte (1 hora)
nano RESEARCH_REPORT_ENTREGA2.md

# 4. Personaliza Replit guide (30 min)
nano REPLIT_GUIDE_ENTREGA2_FINAL.md

# 5. Commit & push (5 min)
git add . && git commit -m "..." && git push
```

---

**Workflow Version**: 1.0  
**Status**: Ready to Execute  
**Next**: Start with RESEARCH PHASE 1

