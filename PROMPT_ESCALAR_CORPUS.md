# PROMPT PARA ESCALAR CORPUS A 1K Y 17K EVENTOS

## COPIA ESTE PROMPT A COPILOT:

```
Necesito actualizar mi script generar_corpus.py para generar CORPUS ESCALABLES.

CAMBIOS REQUERIDOS:

1. AGREGAR PARÁMETRO `--max-eventos N`:
   - Permite especificar cuántos eventos generar (1000, 17000, etc.)
   - Por defecto: 1000 si no se especifica
   - Uso: python3 generar_corpus.py --max-eventos 1000

2. AGREGAR MEDICIÓN DE TIEMPO:
   - Registra cuándo COMIENZA la búsqueda
   - Registra cuándo TERMINA de generar el archivo JSON
   - Imprime: "⏱️  Tiempo total: X segundos (Y minutos)"
   - Imprime: "📊 Velocidad: Z eventos/segundo"

3. AGREGAR ESTADÍSTICAS DEL ARCHIVO:
   - Tamaño del archivo corpus_eventos_reales.json en MB
   - Número total de eventos generados
   - Número total de artículos
   - Imprime al final en formato tabla:
     ```
     RESULTADO FINAL:
     ⏱️  Tiempo: 180 segundos (3.0 minutos)
     📁 Tamaño archivo: 2.5 MB
     📊 Eventos: 1000
     📈 Velocidad: 5.5 eventos/segundo
     ```

4. AGREGAR ESTIMACIÓN PARA 17K:
   - Si ejecutas con 1000 eventos, calcula:
     * Tiempo estimado para 17000: (tiempo_actual * 17000 / 1000)
     * Tamaño estimado para 17000: (tamaño_actual * 17000 / 1000)
   - Imprime:
     ```
     PROYECCIÓN A 17,000 EVENTOS:
     ⏱️  Tiempo estimado: 51 minutos
     📁 Tamaño estimado: 42.5 MB
     ```

5. MANTENER LA LÓGICA ACTUAL:
   - Seguir buscando en MediaStack con las palabras clave
   - Seguir filtrando por medios colombianos
   - Seguir agrupando por eventos (2+ medios)
   - Seguir guardando en corpus_eventos_reales.json

6. LOGGING MEJORADO:
   - Mostrar progreso mientras busca: "[1/10] reforma tributaria... ✅ 145 artículos"
   - Mostrar progreso mientras agrupa: "[Agrupando] 5000 artículos procesados..."
   - Mostrar estado final con estadísticas

REQUISITO IMPORTANTE:
- El script debe poder ejecutarse así:
  ```bash
  python3 generar_corpus.py --max-eventos 1000     # genera 1K eventos
  python3 generar_corpus.py --max-eventos 17000    # genera 17K eventos
  ```

- El flag --max-eventos es OPCIONAL (default 1000 si no se especifica)
- TODOS los cambios se hacen en el script existente
- NO crear un script nuevo, ACTUALIZAR el actual
```

---

## CÓMO USARLO:

1. **Abre Copilot en VS Code** (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. **Copia TODO el prompt de arriba** (desde "Necesito actualizar" hasta el último ```)
3. **Pega en Copilot**
4. **Espera a que genere el código actualizado**
5. **Reemplaza tu script actual** con la versión actualizada

---

## DESPUÉS - EJECUCIÓN:

### Test 1: Generar 1,000 eventos
```bash
cd workshops/media-bias-detection/
time python3 generar_corpus.py --max-eventos 1000
# Registra el TIEMPO TOTAL que imprime
```

### Test 2: Generar 17,000 eventos
```bash
time python3 generar_corpus.py --max-eventos 17000
# Registra el TIEMPO TOTAL que imprime
```

### Commit de ambos resultados:
```bash
# Después de generar 1K
git add generar_corpus.py corpus_eventos_reales.json
git commit -m "test(corpus): generar 1K eventos - timing y estadísticas"
git push

# Después de generar 17K
git add corpus_eventos_reales.json
git commit -m "test(corpus): generar 17K eventos - timing y estadísticas"
git push
```

---

## RESULTADO ESPERADO:

Después de ejecutar ambos tests, tendrás:
- ✅ Script actualizado con timing
- ✅ Corpus de 1,000 eventos con mediciones
- ✅ Corpus de 17,000 eventos con mediciones
- ✅ 2 commits con los resultados
- ✅ Datos para analizar escalabilidad

```
TEST 1K:
⏱️  Tiempo: 180 segundos (3 minutos)
📁 Tamaño: 2.5 MB
📊 Velocidad: 5.5 eventos/segundo

Proyección a 17K:
⏱️  Tiempo estimado: 51 minutos
📁 Tamaño estimado: 42.5 MB

TEST 17K:
⏱️  Tiempo: 3,100 segundos (51.6 minutos) ← verificar si coincide con estimación
📁 Tamaño: 42.8 MB
📊 Velocidad: 5.5 eventos/segundo
```
