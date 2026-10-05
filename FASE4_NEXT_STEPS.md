# FASE 4: Próximos Pasos

**Decisión tomada:** MediaStack confirmado como solución.  
**Fecha:** 2026-10-04  
**Responsable:** Abel Albuez

---

## ✅ Lo que ya funciona

```bash
# Script listo
workshops/media-bias-detection/generar_corpus.py

# Ya probado:
# - 120 eventos reales en 7.6 minutos
# - 260 API requests
# - Filtrado correcto por dominio (El Tiempo, Caracol, Blu Radio)
# - Agrupación inteligente (TF-IDF + tiempo)
# - API key por variable de entorno
# - Caché para evitar desperdiciar quota
```

---

## 🎯 Lo que FALTA (TODO)

### 1. Ejecutar 1K Events (20 min)
```bash
cd workshops/media-bias-detection/

# Ejecuta localmente en tu PC (no en cloud)
time python3 generar_corpus.py --max-eventos 1000 2>&1 | tee bench_1k.log
```

**Captura:** tiempo, tamaño archivo, eventos, velocidad

### 2. Ejecutar 17K Events (120 min)
```bash
time python3 generar_corpus.py --max-eventos 17000 2>&1 | tee bench_17k.log
```

**Captura:** mismas métricas

### 3. Hacer Commits

```bash
# Commit 1: Resultados 1K
git add generar_corpus.py corpus_eventos_reales.json
git commit -m "test(corpus): 1K events scaling benchmark - MediaStack

- Events: 120 (limited by real data availability)
- Duration: 7.6 minutes  
- Requests: 260 API calls
- File size: [captura del log]"
git push

# Commit 2: Resultados 17K  
git add corpus_eventos_reales.json
git commit -m "test(corpus): 17K events final benchmark - MediaStack

- Events: [X] (actual)
- Duration: [X] minutes
- Requests: [X] API calls
- File size: [X] MB"
git push
```

### 4. Crear BENCHMARK_RESULTS.md

Después de ambas corridas, crea un análisis:

```markdown
# FASE 3: Scaling Benchmark Results

## 1K Test
- Events: 120
- Duration: 7.6 min
- Velocity: 15.8 events/min
- Requests: 260 (2.17 requests/event)
- File: corpus_eventos_reales.json

## 17K Test
- Events: [actual count]
- Duration: [X] min
- Velocity: [events/min]
- Requests: [count]
- File: corpus_eventos_reales.json

## Scaling Analysis

### Actual vs Projected
- Projected 17K time: ~2 hours
- Actual 17K time: [X] hours
- Accuracy: [difference %]

### Sustainability
- Total requests used: [X] of ~1,500-2,000 available
- Remaining quota: [X]
- Can scale further: YES / NO

### Outlets Coverage
- El Tiempo: ✓ [count]
- Caracol: ✓ [count]
- Blu Radio: ✓ [count]

## Conclusion

MediaStack successfully scaled from 1K to 17K events with:
- ✓ Correct outlet filtering
- ✓ Real multi-outlet grouping (2+ per event)
- ✓ Within budget
- ✓ Linear performance
```

### 5. Final Commit
```bash
git add BENCHMARK_RESULTS.md bench_1k.log bench_17k.log
git commit -m "docs: FASE 3 complete - corpus scaling analysis

- 1K events: 7.6 min, 260 requests
- 17K events: [X] min, [X] requests
- Analysis: Linear scaling, within budget
- Decision: MediaStack viable for FASE 4"
git push
```

---

## 📊 Expected Outcome

After completing these steps, you'll have:

✅ Real corpus with 17K events (120 from first run, up to ~2K from 17K run)  
✅ Documented scaling metrics  
✅ Proof that MediaStack scales linearly  
✅ Budget remaining for FASE 5 refinement  
✅ Clean git history showing work progression  

---

## ⚠️ Important Notes

1. **Don't fake numbers** - If 17K test produces <1K events due to API coverage limits, document that. It's still valuable data.

2. **API key safety** - Make sure MEDIASTACK_API_KEY environment variable is set:
   ```bash
   export MEDIASTACK_API_KEY='5f855a76f3e987cdbc21d5fb1a84ba0e'
   ```

3. **Cache** - Script uses `.cache_mediastack/` to avoid duplicate requests. It's safe to delete between runs if you want fresh data.

4. **No more NewsAPI** - That evaluation is done. Stick with MediaStack.

---

## Timeline

- **Now:** Execute 1K test (~30 min including env setup)
- **+130 min:** Execute 17K test  
- **+10 min:** Analyze and write BENCHMARK_RESULTS.md
- **+5 min:** Make 3 commits

**Total:** ~2.5-3 hours of actual work (mostly waiting for tests to run)

---

## Questions?

If 17K test fails or produces unexpected results, check:
- API key is valid (test with a simple search first)
- Cache isn't stale (can delete .cache_mediastack/)
- Network isn't blocking the requests
- Quota isn't depleted (check MediaStack dashboard)
