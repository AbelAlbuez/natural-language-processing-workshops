# PROMPT PARA EJECUTAR Y ANALIZAR BENCHMARKS

## COPIA ESTE PROMPT A TU TERMINAL O COPILOT:

```
He pagado $24 por MediaStack y necesito ejecutar benchmarks para generar corpus de 1K y 17K eventos.

TAREAS:

1. EJECUTAR TEST 1K:
   ```bash
   cd /Users/abelalbuez/Documents/Maestria/Cuarto\ Semestre/PLN/natural-language-processing-workshops/workshops/media-bias-detection/
   time python3 generar_corpus.py --max-eventos 1000 2>&1 | tee bench_1k.log
   ```
   - Registra TODA la salida en bench_1k.log
   - El script imprimirá: tiempo, tamaño, eventos, velocidad, proyección a 17K

2. EJECUTAR TEST 17K:
   ```bash
   time python3 generar_corpus.py --max-eventos 17000 2>&1 | tee bench_17k.log
   ```
   - Registra TODA la salida en bench_17k.log
   - El script imprimirá: tiempo, tamaño, eventos, velocidad real

3. HACER COMMITS:
   ```bash
   git add generar_corpus.py corpus_eventos_reales.json
   git commit -m "test(corpus): 1K events scaling benchmark"
   git push
   
   git add corpus_eventos_reales.json
   git commit -m "test(corpus): 17K events final scaling test"
   git push
   ```

4. ANALIZAR RESULTADOS:
   
   Después de ambas ejecuciones, crea un archivo BENCHMARK_RESULTS.md con:

   ```markdown
   # Benchmark Results: MediaStack Corpus Generation

   ## Test 1K Events
   - **Tiempo ejecutado:** [del log]
   - **Eventos generados:** [del log]
   - **Artículos:** [del log]
   - **Tamaño archivo:** [del log]
   - **Velocidad:** [del log]
   - **Proyección a 17K (estimada):** [del log]

   ## Test 17K Events
   - **Tiempo ejecutado:** [del log]
   - **Eventos generados:** [del log]
   - **Artículos:** [del log]
   - **Tamaño archivo:** [del log]
   - **Velocidad:** [del log]

   ## Análisis de Escalabilidad

   ### Tiempo
   - Test 1K: X minutos
   - Test 17K: Y minutos
   - Ratio: Y/X = [escalabilidad de tiempo]
   - Esperado: ~17x si es lineal
   - Observado: [análisis]

   ### Tamaño
   - Test 1K: A MB
   - Test 17K: B MB
   - Ratio: B/A = [escalabilidad de tamaño]
   - Esperado: ~17x
   - Observado: [análisis]

   ### Velocidad (eventos/segundo)
   - Test 1K: V1 eventos/seg
   - Test 17K: V17 eventos/seg
   - Cambio: [aumento/disminución]
   - Análisis: [mejor/peor con más eventos]

   ## Conclusiones

   1. **¿Es lineal?** El tiempo es proporcional a eventos (V1 ≈ V17)
   2. **¿Eficiencia?** Mejora con más datos o se degrada
   3. **¿Viable?** Para FASE 4, ¿cuántos eventos necesitamos?
   4. **Cuota:** Peticiones usadas de tu cuota de $24
   ```

5. HACER COMMIT FINAL:
   ```bash
   git add BENCHMARK_RESULTS.md bench_1k.log bench_17k.log
   git commit -m "docs: corpus scaling benchmarks and analysis

   - 1K events: X minutos, A MB
   - 17K events: Y minutos, B MB
   - Scaling analysis and efficiency metrics"
   git push
   ```

IMPORTANTE:
- No hagas git add del corpus_eventos_reales.json dos veces (ya está en primero commit)
- Los logs (bench_1k.log, bench_17k.log) sí van en el último commit
- El análisis en BENCHMARK_RESULTS.md es lo más importante
```

---

## PASOS ORDENADOS:

### 1️⃣ Ejecuta en terminal (copia y pega):
```bash
cd /Users/abelalbuez/Documents/Maestria/Cuarto\ Semestre/PLN/natural-language-processing-workshops/workshops/media-bias-detection/
echo "=== TEST 1K ===" 
time python3 generar_corpus.py --max-eventos 1000 2>&1 | tee bench_1k.log
echo && echo "=== TEST 17K ===" 
time python3 generar_corpus.py --max-eventos 17000 2>&1 | tee bench_17k.log
```

### 2️⃣ Copia el output de AMBOS TESTS (lo que aparece en terminal)

### 3️⃣ Abre Claude o Copilot y pega este prompt:
```
Analiza estos resultados de benchmarks y crea un archivo BENCHMARK_RESULTS.md

TEST 1K OUTPUT:
[pega aquí el output de bench_1k.log]

TEST 17K OUTPUT:
[pega aquí el output de bench_17k.log]

Crea BENCHMARK_RESULTS.md con:
- Métricas extraídas (tiempo, eventos, tamaño, velocidad)
- Análisis de escalabilidad (¿es lineal?, ¿eficiencia?)
- Conclusiones (¿viable para FASE 4?)
```

### 4️⃣ Haz los 3 commits:
```bash
# Commit 1: Test 1K
git add generar_corpus.py corpus_eventos_reales.json
git commit -m "test(corpus): 1K events scaling benchmark"
git push

# Commit 2: Test 17K
git add corpus_eventos_reales.json
git commit -m "test(corpus): 17K events final scaling test"
git push

# Commit 3: Análisis
git add BENCHMARK_RESULTS.md bench_1k.log bench_17k.log
git commit -m "docs: corpus scaling analysis and metrics"
git push
```

---

## RESULTADO ESPERADO:

Un documento `BENCHMARK_RESULTS.md` con:
- ✅ Métricas de ambos tests
- ✅ Análisis de escalabilidad
- ✅ Conclusiones para FASE 4
- ✅ 3 commits en el repo

Esto te da data real para saber si MediaStack puede sustentar 17K eventos o si necesitas otra estrategia.
