# PROMPT: Sincronizar cambios de Kelly + Validar entrega2 + Continuar informe

## OBJETIVO
1. Copiar cambios de Kelly a carpeta principal (estructura ordenada)
2. Validar notebook + informe que Kelly publicó
3. Preparar para continuar desarrollo del informe final

---

## FASE 1: Sincronizar cambios de Kelly

### 1.1 Definir rutas y backup

```bash
#!/bin/bash
set -euo pipefail

# Rutas
MAIN="/Users/abelalbuez/Documents/Maestria/Cuarto Semestre/PLN/natural-language-processing-workshops/workshops/media-bias-detection/news-retrieval"
KELLY="$MAIN/dumps/kelly/natural-language-processing-workshops-corpus-v2/workshops/media-bias-detection/news-retrieval"

# Verificar que existan
[[ -d "$MAIN" ]] || { echo "ERROR: $MAIN no existe"; exit 1; }
[[ -d "$KELLY" ]] || { echo "ERROR: $KELLY no existe"; exit 1; }

# Backup de lo actual
BACKUP_DIR="$MAIN/BACKUP_$(date +%Y%m%d_%H%M%S)"
echo "→ Creando backup en: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cp -r "$MAIN/src" "$BACKUP_DIR/src.backup" 2>/dev/null || true
cp -r "$MAIN/config" "$BACKUP_DIR/config.backup" 2>/dev/null || true

echo "✅ Backup creado"
```

### 1.2 Copiar cambios de Kelly

```bash
echo "→ Copiando cambios de Kelly a carpeta principal..."

# Copiar código
cp -r "$KELLY/src" "$MAIN/src_kelly_$(date +%Y%m%d)" || true
cp -r "$KELLY/config" "$MAIN/config_kelly_$(date +%Y%m%d)" || true
cp -r "$KELLY/tests" "$MAIN/tests_kelly_$(date +%Y%m%d)" || true

# Copiar dependencias
cp "$KELLY/requirements.txt" "$MAIN/requirements_kelly.txt" 2>/dev/null || true
cp "$KELLY/pyproject.toml" "$MAIN/pyproject_kelly.toml" 2>/dev/null || true
cp "$KELLY/Dockerfile.jupyter" "$MAIN/Dockerfile.jupyter_kelly" 2>/dev/null || true

echo "✅ Cambios copiados a:"
echo "   src_kelly_$(date +%Y%m%d)"
echo "   config_kelly_$(date +%Y%m%d)"
echo "   tests_kelly_$(date +%Y%m%d)"
```

### 1.3 Analizar diferencias

```bash
echo ""
echo "→ Analizando diferencias en src/..."
echo ""

# Archivos nuevos en Kelly
echo "ARCHIVOS NUEVOS en Kelly:"
diff -r "$KELLY/src" "$MAIN/src" --new-file | grep "Only in $KELLY" || echo "(Ninguno)"

# Archivos modificados
echo ""
echo "ARCHIVOS MODIFICADOS:"
diff -r "$KELLY/src" "$MAIN/src" -u | head -100 || echo "(Igual)"

# Archivos removidos en Kelly
echo ""
echo "ARCHIVOS REMOVIDOS en Kelly (en main pero no en Kelly):"
diff -r "$MAIN/src" "$KELLY/src" --new-file | grep "Only in $MAIN" || echo "(Ninguno)"
```

### 1.4 Resumen de cambios

```bash
echo ""
echo "═══════════════════════════════════════════════════════"
echo "RESUMEN: ¿Qué cambió en Kelly?"
echo "═══════════════════════════════════════════════════════"
echo ""

# Contar archivos
echo "Archivos Python:"
echo "  Main: $(find "$MAIN/src" -name "*.py" 2>/dev/null | wc -l)"
echo "  Kelly: $(find "$KELLY/src" -name "*.py" 2>/dev/null | wc -l)"

echo ""
echo "Documentación:"
ls -1 "$KELLY/docs"/*.md 2>/dev/null | xargs -I {} basename {} || echo "(ninguna)"

echo ""
echo "Configuración:"
ls -1 "$KELLY/config"/*.yaml 2>/dev/null | xargs -I {} basename {} || echo "(ninguna)"

echo ""
echo "RECOMENDACIÓN: Revisar cambios antes de mergear."
echo "Carpeta backup: $BACKUP_DIR"
```

---

## FASE 2: Validar cambios de Kelly (GitHub)

### 2.1 Descargary verificar notebook

```bash
echo "→ Validando notebook de Kelly..."
NOTEBOOK="$MAIN/notebooks/05-entrega2-eda-representacion.ipynb"

if [[ ! -f "$NOTEBOOK" ]]; then
  echo "⚠️  Notebook no encontrado en:"
  echo "   $NOTEBOOK"
  echo ""
  echo "Descargando desde GitHub..."
  curl -s "https://raw.githubusercontent.com/AbelAlbuez/natural-language-processing-workshops/main/workshops/media-bias-detection/news-retrieval/notebooks/05-entrega2-eda-representacion.ipynb" \
    > "$NOTEBOOK"
  echo "✅ Descargado"
else
  echo "✅ Notebook encontrado"
fi

# Validar estructura
echo ""
echo "Validando estructura del notebook..."
python3 << 'PYTHON'
import json
from pathlib import Path

notebook_path = Path("$NOTEBOOK")
if not notebook_path.exists():
    print(f"ERROR: {notebook_path} no existe")
    exit(1)

with open(notebook_path) as f:
    nb = json.load(f)

print(f"Celdas: {len(nb.get('cells', []))}")
print(f"Kernel: {nb.get('metadata', {}).get('kernelspec', {}).get('display_name', 'unknown')}")

# Contar tipos de celdas
code_cells = sum(1 for c in nb['cells'] if c['cell_type'] == 'code')
markdown_cells = sum(1 for c in nb['cells'] if c['cell_type'] == 'markdown')

print(f"Celdas código: {code_cells}")
print(f"Celdas markdown: {markdown_cells}")
print("✅ Notebook válido")
PYTHON
```

### 2.2 Validar informe LaTeX

```bash
echo "→ Validando informe LaTeX..."
INFORME="$MAIN/informe/entrega2.tex"

if [[ ! -f "$INFORME" ]]; then
  echo "⚠️  Informe no encontrado en:"
  echo "   $INFORME"
  echo ""
  echo "Descargando desde GitHub..."
  mkdir -p "$MAIN/informe"
  curl -s "https://raw.githubusercontent.com/AbelAlbuez/natural-language-processing-workshops/main/workshops/media-bias-detection/informe/entrega2.tex" \
    > "$INFORME"
  echo "✅ Descargado"
else
  echo "✅ Informe encontrado"
fi

# Validar sintaxis LaTeX básica
echo ""
echo "Validando sintaxis LaTeX..."
python3 << 'PYTHON'
from pathlib import Path

informe_path = Path("$INFORME")
if not informe_path.exists():
    print(f"ERROR: {informe_path} no existe")
    exit(1)

content = informe_path.read_text()

# Conteos básicos
sections = content.count('\\section{')
subsections = content.count('\\subsection{')
references = content.count('\\cite{')
figures = content.count('\\includegraphics{')

print(f"Secciones: {sections}")
print(f"Subsecciones: {subsections}")
print(f"Referencias citadas: {references}")
print(f"Figuras: {figures}")
print(f"Líneas: {len(content.splitlines())}")

# Verificar estructura básica
if '\\documentclass{' in content and '\\begin{document}' in content:
    print("✅ Estructura LaTeX válida")
else:
    print("⚠️  Estructura LaTeX incompleta")

PYTHON
```

### 2.3 Listar contenido de Kelly en GitHub

```bash
echo ""
echo "═══════════════════════════════════════════════════════"
echo "CAMBIOS PUBLICADOS POR KELLY en GitHub (main)"
echo "═══════════════════════════════════════════════════════"
echo ""

echo "📓 Notebook:"
echo "  https://github.com/AbelAlbuez/natural-language-processing-workshops/blob/main/workshops/media-bias-detection/news-retrieval/notebooks/05-entrega2-eda-representacion.ipynb"
echo ""

echo "📄 Informe provisional:"
echo "  https://github.com/AbelAlbuez/natural-language-processing-workshops/blob/main/workshops/media-bias-detection/informe/entrega2.tex"
echo ""

echo "💡 NOTA DE KELLY:"
echo "  'Falta la propuesta para el análisis de sesgo, que yo creo que es posible'"
echo "  'por rankings, o seleccionar temas polémicos y mirar cómo se publican en cada medio'"
echo ""
```

---

## FASE 3: Preparar para continuar informe

### 3.1 Crear plan de trabajo

```bash
echo "═══════════════════════════════════════════════════════"
echo "PLAN: Continuar Entrega 2"
echo "═══════════════════════════════════════════════════════"
echo ""

cat > "$MAIN/PLAN_ENTREGA2.md" << 'PLAN'
# Plan de Trabajo: Entrega 2

## ✅ Ya Hecho (Kelly)
- [x] EDA + representación (notebook)
- [x] Informe provisional (estructura)
- [x] Análisis base de datos Duque

## ⏳ Falta Hacer

### 1. PROPUESTA DE ANÁLISIS DE SESGO
- [ ] Definir metodología (rankings vs temas polémicos)
- [ ] Seleccionar temas de prueba
- [ ] Implementar cálculo de sesgo por medio

### 2. ANÁLISIS DE RANKINGS
- [ ] Implementar ranking de artículos por medio
- [ ] Comparar posición de temas entre medios
- [ ] Medir desviación estándar por medio

### 3. TEMAS POLÉMICOS
- [ ] Listar temas polémicos en Duque
- [ ] Contar apariciones por medio/tema
- [ ] Calcular índice de sesgo

### 4. VISUALIZACIONES
- [ ] Gráficos de cobertura por tema
- [ ] Heatmaps medio vs tema
- [ ] Series temporales de sesgo

### 5. INFORME FINAL
- [ ] Integrar resultados en entrega2.tex
- [ ] Agregar figuras y tablas
- [ ] Escribir conclusiones

## 📊 DATOS DISPONIBLES

### Corpus Duque (Nuevo - Hoy)
- Archivo: duque-candidatos.csv (708,768 artículos)
- Cobertura títulos: 99.83%
- Período: 2018-08-07 a 2022-08-07

### Corpus Petro (Existente)
- En: news_corpus DB (PostgreSQL)
- Período: 2022-08-07 a 2026-08-31

## 🎯 PRÓXIMOS PASOS INMEDIATOS

1. [ ] Sincronizar cambios Kelly → carpeta principal
2. [ ] Leer notebook de Kelly (05-entrega2-eda-representacion.ipynb)
3. [ ] Revisar informe provisional (entrega2.tex)
4. [ ] Proponer metodología de análisis de sesgo
5. [ ] Implementar en Python

PLAN

echo "✅ Plan creado en: $MAIN/PLAN_ENTREGA2.md"
cat "$MAIN/PLAN_ENTREGA2.md"
```

### 3.2 Verificar datos Duque disponibles

```bash
echo ""
echo "→ Verificando corpus Duque..."
echo ""

# Buscar exports
if [[ -d "$MAIN/exports" ]]; then
  echo "Archivos en exports/:"
  ls -lh "$MAIN/exports/duque-candidatos."* 2>/dev/null || echo "(no encontrados - revisar ruta)"
else
  echo "⚠️  Carpeta exports/ no existe"
fi

# Buscar dumps
if [[ -d "$MAIN/dumps" ]]; then
  echo ""
  echo "Dumps disponibles:"
  ls -lh "$MAIN/dumps/news_corpus_duque_rebuild"* 2>/dev/null || echo "(no encontrados)"
else
  echo "⚠️  Carpeta dumps/ no existe"
fi

echo ""
echo "✅ Validación completada"
```

### 3.3 Crear archivo de configuración para análisis

```bash
cat > "$MAIN/ANALISIS_SESGO_CONFIG.yaml" << 'CONFIG'
# Configuración para análisis de sesgo - Entrega 2

## Corpus
corpus:
  duque:
    csv: "exports/duque-candidatos.csv"
    periodo: "2018-08-07 a 2022-08-07"
    articulos: 708768
    cobertura_titulos: 0.9983
  petro:
    db: "news_corpus"
    periodo: "2022-08-07 a 2026-08-31"

## Medios
medios:
  - el_tiempo
  - blu_radio
  - noticias_caracol
  - la_republica
  - noticias_rcn
  - cambio
  - el_espectador
  - semana

## Metodología de análisis de sesgo
analisis:
  opciones:
    - nombre: "Rankings por tema"
      descripcion: "Comparar posición de artículos por tema entre medios"
      complejidad: "media"
      ventaja: "Identifica énfasis diferencial"
    
    - nombre: "Temas polémicos"
      descripcion: "Seleccionar temas controversiales y medir cobertura/framing"
      complejidad: "alta"
      ventaja: "Directo y comprensible"

## Temas de prueba
temas_polemicos_potenciales:
  - "reforma tributaria"
  - "protestas"
  - "economía"
  - "seguridad"
  - "salud"
  - "educación"
  - "corrupción"

CONFIG

echo "✅ Configuración creada: ANALISIS_SESGO_CONFIG.yaml"
```

---

## EJECUCIÓN

### Paso 1: Ejecutar sincronización
```bash
bash ~/Desktop/sync_kelly.sh
```

### Paso 2: Revisar plan
```bash
cat "$MAIN/PLAN_ENTREGA2.md"
```

### Paso 3: Próximos pasos
1. Leer notebook de Kelly
2. Revisar informe provisional
3. Proponer metodología de sesgo
4. Implementar análisis

---

## CHECKLIST

- [ ] Cambios de Kelly sincronizados
- [ ] Notebook validado
- [ ] Informe validado
- [ ] Datos Duque disponibles
- [ ] Plan de trabajo creado
- [ ] Configuración lista

---

## NOTAS

**Kelly dijo:**
> "Falta la propuesta para el análisis de sesgo, que yo creo que es posible por rankings, o seleccionar temas polémicos y mirar cómo se publican en cada medio"

**Tenemos:**
- ✅ Corpus Duque completo (99.83% títulos)
- ✅ Corpus Petro (existente)
- ✅ Código de Kelly (pipeline validado)
- ✅ EDA básica (notebook de Kelly)

**Siguiente:** Implementar análisis de sesgo (rankings o temas polémicos)
