# NewsAPI Evaluation for FASE 3 Corpus

**Status:** ❌ DISCARDED - Does not meet project requirements

**Date:** 2026-10-04  
**Evaluator:** Abel Albuez  
**Method:** API testing + code review

---

## Summary

NewsAPI was evaluated as a potential alternative to MediaStack for corpus generation. After testing and analysis, it **does not provide viable data** for this project due to:

1. **Limited plan**: Free tier only (not a paid plan limitation)
2. **No Colombian outlet coverage**: El Tiempo, Caracol, Blu Radio not indexed
3. **Temporal limitation**: 30-day window only (2026-09-04 to 2026-10-03)
4. **Script issues**: Would produce 0 or misleading events

---

## Technical Findings

### API Limitations

| Parameter | Finding |
|-----------|---------|
| **Plan** | Developer (free) - d8e82adf19434eb0a1b3a57925071b8c |
| **Max results** | 100 per request |
| **Pages supported** | 1 (page 2 returns `426 maximumResultsReached`) |
| **Data window** | Last 30 days only |
| **Countries** | No `country=co` parameter support |

### Outlet Coverage Test

| Outlet | Domain(s) Tested | Results |
|--------|------------------|---------|
| **El Tiempo** | eltiempo.com | 0 articles |
| **Blu Radio** | bluradio.com | 0 articles |
| **Noticias Caracol** | noticias.caracoltv.com, caracol.com.co | 0 articles |
| **El Colombiano** | elcolombiano.com | 0 articles |
| **W Radio** | wradio.com.co | 0 articles |
| **Semana** | semana.com | 0 articles |
| **El Espectador** | blogs.elespectador.com | Limited (blog only) |

**Spanish-language results instead:** RT (Russia), df.cl (Chile), abc.es (Spain), La Tercera (Chile)

### Script Analysis

The generated `generar_corpus_newsapi.py` would fail in production:

```python
# Problem 1: Grouping strategy
palabras = tuple(sorted(set([p for p in titulo + descripcion if len(p) > 4])))
# Two different news outlets almost NEVER have identical word tuples
# → Would produce 0-5 events even with 1000 articles
```

```python
# Problem 2: Scalability illusion
# Same 10 keyword searches × 2 = same 10 API requests
# 1K test and 17K test would be IDENTICAL in actual requests
# → Cannot measure real scaling behavior
```

```python
# Problem 3: Crash on missing data
art.get('description', '').lower()  # Crashes if description is None
# NewsAPI returns None for some articles
```

```python
# Problem 4: Security
NEWSAPI_KEY = 'd8e82adf19434eb0a1b3a57925071b8c'  # In public repo
# API key would be exposed on GitHub
```

---

## MediaStack Results (for comparison)

**1K Events Test** (2026-10-04)
- **API requests**: 260
- **Duration**: 7.6 minutes
- **Events generated**: 120 actual events
- **File size**: Not measured
- **Outlets found**: El Tiempo, Caracol, Blu Radio ✅
- **Scaling**: Approximately linear (260 requests ≈ 2.6 per event desired)

**17K Events Projection**
- **Estimated requests**: 4,400 (well within $24 quota)
- **Estimated duration**: ~2 hours
- **Feasibility**: ✅ YES

---

## Decision

**Use MediaStack. Do not use NewsAPI.**

### Reasoning

1. **NewsAPI is fundamentally incompatible** with the project needs
   - Colombian outlets not indexed
   - No paid plan changes this indexing coverage
   
2. **MediaStack already works and scales**
   - Filters by correct domains
   - Groups by semantic similarity (TF-IDF), not exact tuples
   - Produces real events with multiple outlets per event
   - Within budget

3. **Benchmarking NewsAPI would be misleading**
   - Tests would measure API speed, not corpus quality
   - Would produce 0 events or false groupings
   - Numbers would not reflect actual capability

---

## Path Forward

### For PHASE 4

✅ **Continue with MediaStack** + `generar_corpus.py`
- Run: `python3 generar_corpus.py --max-eventos 1000` (already tested)
- Run: `python3 generar_corpus.py --max-eventos 17000` (pending)
- Commit both results with timing data

### For Future Expansion

If additional coverage needed beyond MediaStack:

1. **RSS Feeds** (recommended)
   - El Tiempo official feeds (política, economía, colombia)
   - El Espectador
   - Portafolio
   - Unlimited requests, no API limits

2. **Direct Scraping**
   - With anti-bot measures (puppeteer, rotating user agents)
   - Rate-limited to respect server loads
   
3. **Internet Archive (Wayback Machine)**
   - Historical snapshots from 2023-2024
   - No real-time, but complete historical coverage

---

## Artifacts

- **PROMPT_NEWSAPI_BENCHMARKS.md**: Prompt template (will not be executed)
- **generar_corpus_newsapi.py**: Script (will not be used)

These remain in repo for documentation of evaluation, but are marked as discarded.
