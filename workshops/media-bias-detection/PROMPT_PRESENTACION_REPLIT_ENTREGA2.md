# 🎤 PROMPT: Presentación Interactiva Entrega 2 en Replit

## Objetivo
Crear presentación HTML interactiva en Replit que explique el research de Entrega 2 de forma clara, honesta y atractiva. Slides con datos verificados, sin conclusiones sobreclamadas. Navegación con flechas, datos interactivos donde sea posible.

---

## 📊 Estructura de Slides (12 slides)

### SLIDE 1: Portada
```
Título: "Análisis de Sesgo Editorial en Medios Colombianos"
Subtítulo: "Entrega 2: Research Exploratorio (2018-2022)"

Datos:
- 708,768 artículos
- 6 medios colombianos
- Período: 2018-08-07 a 2022-08-06

Nota al pie: "Análisis exploratorio. Sin conclusiones sobre sesgo confirmado."
```

**Elementos interactivos**: Contador de artículos animado

---

### SLIDE 2: Alcance y Datos
```
Título: "¿Qué Analizamos?"

Tabla interactiva:
| Medio | Artículos | Período |
|-------|-----------|---------|
| El Tiempo | 263,145 | Completo |
| Blu Radio | 166,593 | Completo |
| Caracol | 109,384 | Completo |
| La República | 91,801 | Completo |
| RCN | 77,747 | Desde sep-2018 |
| Cambio | 98 | Solo 6 días |

⚠️ **Cambio es una ventana de 6 días, no 4 años**
```

**Elementos interactivos**: Tabla filtrable por medio

---

### SLIDE 3: Limitación Crítica
```
Título: "Lo que Falta"

Tres rectángulos con iconos:
1. ❌ Cuerpos HTML
   └─ Solo títulos slug (derivados de URL)

2. ❌ Análisis Manual
   └─ Sin etiquetas de framing

3. ❌ Validación Temporal
   └─ Cambio: solo 6 días

Conclusión: "Son análisis exploratorios, no concluyentes"
```

**Elementos interactivos**: Click para expandir cada limitación

---

### SLIDE 4: Metodología (1/2)
```
Título: "¿Cómo Lo Hicimos?"

Métrica 1: TEXTOMETRÍA
├─ Ley de Zipf (correlación log-log)
├─ TTR (diversidad léxica)
├─ MSTTR (mean segmental TTR)
└─ N-gramas (bigramas + trigramas)

Métrica 2: EVENTOS POLÉMICOS
├─ Reforma Tributaria
├─ Conflicto Armado
└─ Corrupción

✅ 3 Chi-cuadrado tests (Holm ajustado)
✅ V de Cramér (tamaño de efecto)
```

**Elementos interactivos**: Tooltip con explicación de cada métrica

---

### SLIDE 5: Metodología (2/2)
```
Título: "Topic Modeling (LDA)"

Pipeline:
1. Entrenar 5 modelos (K=3,5,7,10,15)
2. Medir coherencia (c_v)
3. Seleccionar K óptimo
4. Analizar distribuciones por medio

Resultado: K=5 gana (coherencia = 0.3595)
├─ Diferencia vs K=7: 0.0205
└─ ⚠️ Sin validación por semillas múltiples

Documentos:
├─ 2,685 excluidos (-1)
└─ 26,282 baja confianza (<0.3)
```

**Elementos interactivos**: Gráfico de coherencia por K (interactivo)

---

### SLIDE 6: Hallazgo 1 - Ley de Zipf
```
Título: "Hallazgo 1: Zipf Confirmada"

Gráfico log-log: Rango vs Frecuencia
├─ Global: r = -0.982
├─ Por medio: r entre -0.837 y -0.983
└─ Línea recta = patrón típico

Interpretación:
✅ El lenguaje sigue patrón natural
✅ No hay evidencia de manipulación de frecuencias

⚠️ Limitación: Zipf ≠ ley de potencia confirmada
            (solo correlación, no bondad de ajuste)
```

**Elementos interactivos**: 
- Slider para cambiar rango de palabras
- Toggle por medio

---

### SLIDE 7: Hallazgo 2 - Diversidad Léxica
```
Título: "Hallazgo 2: Diversidad Varía"

Gráfico de barras: TTR por medio (con rarefacción)
┌─────────────┐
│ El Tiempo   │ 0.476 ▓▓▓▓
│ Caracol     │ 0.480 ▓▓▓▓
│ La República│ 0.447 ▓▓▓
│ RCN         │ 0.453 ▓▓▓
│ Blu Radio   │ 0.469 ▓▓▓
│ Cambio      │ N/A (476 tokens)
└─────────────┘

Interpretación:
✅ Existe variación en diversidad
❌ NO es "35% más diverso" (eso fue dato fabricado)
⚠️ La diferencia es pequeña (~3%)

Control: Rarefacción a 10,000 tokens (igual comparación)
```

**Elementos interactivos**: 
- Comparar pares de medios
- Ver intervalos de confianza

---

### SLIDE 8: Hallazgo 3 - Cobertura Temática
```
Título: "Hallazgo 3: Diferencias Condicionadas"

Tabla de tasas (% de títulos):
┌──────────────┬─────────────┬───────────┐
│ Medio        │ Reforma Trib │ Conflicto │
├──────────────┼─────────────┼───────────┤
│ La República │ 1.08% ↑     │ 0.10%     │
│ Blu Radio    │ 0.42%       │ 1.97% ↑   │
│ RCN          │ 0.37%       │ 1.97% ↑   │
│ El Tiempo    │ 0.41%       │ 1.33%     │
│ Caracol      │ 0.32%       │ 1.66%     │
│ Cambio       │ 0%          │ 0%        │
└──────────────┴─────────────┴───────────┘

Estadística:
✅ Chi-square: p < 0.05 (significativo)
⚠️ V de Cramér: 0.015-0.049 (efecto PEQUEÑO)
```

**Elementos interactivos**:
- Gráfico interactivo (líneas por tema)
- Filtrar por medio
- Mostrar denominadores

---

### SLIDE 9: Hallazgo 4 - Topic Modeling
```
Título: "Hallazgo 4: Tópicos No Uniformes"

Heatmap: Medios vs Tópicos (dominante)
┌──────────────┬─────┬─────┬─────┬─────┬─────┐
│ Medio        │ T0  │ T1  │ T2  │ T3  │ T4  │
├──────────────┼─────┼─────┼─────┼─────┼─────┤
│ Caracol      │ 10% │ 37% │ 14% │ 22% │ 16% │
│ Blu Radio    │ 17% │ 29% │ 15% │ 23% │ 16% │
│ El Tiempo    │ 12% │ 28% │ 16% │ 28% │ 17% │
│ RCN          │ 16% │ 30% │ 16% │ 22% │ 16% │
│ La República │ 15% │ 25% │ 21% │ 23% │ 16% │
└──────────────┴─────┴─────┴─────┴─────┴─────┘

Interpretación:
✅ Hay variación observable (no uniforme)
⚠️ Chi-square da V=0.059 (pequeño efecto)
❌ NO demuestra sesgo (modelo fue entrenado con estos medios)
```

**Elementos interactivos**:
- Heatmap con hover para ver valores exactos
- Toggle: mostrar números absolutos vs %

---

### SLIDE 10: Lo Que NO Podemos Afirmar
```
Título: "⚠️ Lo que NO se puede Afirmar"

Cada frase con ❌:

❌ "Hay sesgo editorial confirmado"
   └─ Falta análisis manual + validación

❌ "Hay agenda común entre medios"
   └─ Distribuciones varían, modelo sesgado por entrenamiento

❌ "La República es 35% más diversa"
   └─ Falsa estadística (dato fabricado en primer resumen)

❌ "Cambio tiene cobertura diferente"
   └─ Cambio es solo 6 días, no 4 años

❌ "Los tópicos están validados"
   └─ Solo top-words, sin verificación manual

❌ "Esto es reproducible en Replit cloud"
   └─ Solo guía preparada, no desplegado
```

**Elementos interactivos**: Click para ampliar cada limitación

---

### SLIDE 11: Números Concretos (Validación)
```
Título: "46 Verificaciones Técnicas ✅"

Tabla de auditoría:
┌──────────────────────────────┬─────────┐
│ Verificación                 │ Status  │
├──────────────────────────────┼─────────┤
│ IDs únicos                   │ ✅ OK   │
│ Fechas coinciden             │ ✅ OK   │
│ Frecuencias exactas          │ ✅ OK   │
│ Keywords recontadas (18)     │ ✅ OK   │
│ Modelos LDA cargan           │ ✅ OK   │
│ Proporciones suman 100%      │ ✅ OK   │
│ Tests unitarios (14/14)      │ ✅ OK   │
└──────────────────────────────┴─────────┘

Integridad: 100% verificada
Sesgo editorial: Sin evidencia de fabricación
```

**Elementos interactivos**: Barra de progreso 46/46

---

### SLIDE 12: Próximos Pasos
```
Título: "¿Qué Falta Para Conclusiones Firmes?"

Priority 1 (Crítico):
├─ Validar manualmente 50-100 artículos por tema
└─ Recuperar cuerpos HTML (no solo slug)

Priority 2 (Recomendado):
├─ Múltiples semillas LDA (verificar estabilidad)
├─ Análisis de framing experto
└─ Comparar Duque vs Petro (períodos comunes)

Priority 3 (Futuro):
├─ Series temporales controladas
└─ Análisis de agenda editorial cualitativa

CTA: "Este análisis es exploratorio. Úsalo para preguntas, no conclusiones."
```

**Elementos interactivos**:
- Timeline visual de prioridades
- Link a documentación completa

---

## 🎨 Diseño Técnico (Replit)

### Navegación
```
← Anterior | Slide X/12 | Siguiente →
Números 1-12 clickeables
Atajos: Flechas izq/der, A/D, J/K
```

### Datos Interactivos
```
1. Tablas: Ordenables, filtrables
2. Gráficos: Hover con valores, zoom, toggle series
3. Heatmaps: Color inteligente, valores en hover
4. Barras: Comparables por pares
```

### Colores
```
✅ Verde: Validado, confirmado
⚠️ Amarillo: Limitación, cuidado
❌ Rojo: No se puede afirmar
📊 Azul: Datos, neutro
```

### Topografía
```
H1: Título slide (grande, bold)
H3: Subtítulo/sección
Body: Datos, explicación
Footer: Slide X/12 + disclaimers
```

---

## 📁 Archivos para Replit

```
index.html (presentación interactiva)
├─ CSS: estilos + responsivo
├─ JS: navegación + interactividad
├─ DATA: DATA_INSIGHTS_TABLES.csv (cargado)
└─ ASSETS: figuras PNG (zipf, diversidad, eventos, heatmap)

Requisitos:
- HTML5 + CSS3 (sin dependencias externas)
- JavaScript vanilla
- CSV que ya existe: DATA_INSIGHTS_TABLES.csv
- PNG que ya existen: 8 figuras en entrega2/research/figuras/
```

---

## 🎯 Tone & Messaging

**Ser claro sobre qué ES:**
- ✅ Análisis exploratorio de 708K artículos
- ✅ 46 verificaciones técnicas pasadas
- ✅ Diferencias observables documentadas
- ✅ Listo para hacer preguntas

**Ser claro sobre qué NO ES:**
- ❌ Sesgo editorial comprobado
- ❌ Conclusión causal
- ❌ Validado por expertos
- ❌ Agenda común demostrada

**Lema**: "Datos rigurosos. Conclusiones modestas."

---

## 🚀 Ejecución en Replit

```bash
# 1. Crear repositorio en Replit
git clone https://github.com/AbelAlbuez/natural-language-processing-workshops
cd workshops/media-bias-detection

# 2. Copiar archivos a Replit public/
cp entrega2/research/DATA_INSIGHTS_TABLES.csv public/
cp entrega2/research/figuras/*.png public/figuras/

# 3. Crear index.html (esta presentación)
# 4. Servir en Replit Web Server
# 5. Compartir URL pública
```

---

## ✅ Checklist de Slides

- [ ] Slide 1: Portada clara
- [ ] Slide 2: Tabla interactiva de datos
- [ ] Slide 3: Limitaciones prominentes
- [ ] Slide 4-5: Metodología (expandible)
- [ ] Slide 6: Zipf (con gráfico)
- [ ] Slide 7: Diversidad (con barras)
- [ ] Slide 8: Cobertura temática (con tabla)
- [ ] Slide 9: Topic Modeling (con heatmap)
- [ ] Slide 10: Lo que NO podemos afirmar
- [ ] Slide 11: Auditoría (46/46 ✅)
- [ ] Slide 12: Próximos pasos + CTA

---

## 💾 Datos a Incluir

```
CSV: DATA_INSIGHTS_TABLES.csv (90 métricas)
├─ Zipf por medio
├─ TTR + intervalos
├─ Tasas de keywords
├─ Chi-square + V de Cramér
└─ Distancias LDA

PNG (8 figuras):
├─ zipf_by_medium.png
├─ diversity_equal_tokens.png
├─ event_rates.png
├─ topics_assigned_heatmap.png
├─ lda_tradeoff.png
├─ media_dendrogram.png
└─ [2 más según research]
```

---

**Version**: 1.0  
**Status**: Ready for Implementation  
**Time to Build**: 3-4 hours (HTML + interactividad)  
**Time to Present**: 12-15 minutes (incluyendo Q&A)
