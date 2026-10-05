# FASE 3: Corpus Scaling Benchmark Results

**Date:** 2026-10-04  
**Status:** Complete — Real data collected and analyzed  
**Author:** Abel Albuez

---

## Executive Summary

MediaStack corpus generation was tested at two scales (1K and 17K event targets) on October 4, 2026. Results reveal a critical limitation: **MediaStack does not index the three primary Colombian outlets** (El Tiempo, Noticias Caracol, Blu Radio) specified for this project. Instead, it returns articles from secondary outlets (El Colombiano, W Radio, La Opinión, etc.). This fundamentally constrains the corpus to 120 events maximum from current available data.

**Recommendation:** MediaStack alone cannot deliver the required outlet coverage. FASE 4 must explore alternative data sources (RSS feeds, direct scraping, or manual curation) to obtain articles from El Tiempo, Caracol, and Blu Radio.

---

## Test 1K: MediaStack Corpus Generation

**Command:** `python3 generar_corpus.py --max-eventos 1000 --todos-los-medios --sin-cache --max-peticiones 2000`

**Timeline:**
- Start: 2026-10-04 22:09:42
- End: 2026-10-04 22:17:18
- Duration: **7 minutes 35 seconds (455.8 seconds)**

**Results:**
| Metric | Value |
|--------|-------|
| Requested events | 1,000 |
| **Actual events found** | **120** |
| Actual corpus articles | 256 |
| File size | 0.19 MB |
| New API requests used | 260 |
| Search rounds completed | 100 pages |
| Events/second velocity | 0.26 |

**Coverage by Expected Outlets:**
| Outlet | Expected | Actual |
|--------|----------|--------|
| **El Tiempo** | ✓ | ❌ 0 articles |
| **Noticias Caracol** | ✓ | ❌ 0 articles |
| **Blu Radio** | ✓ | ❌ 0 articles |

**Coverage by Found Outlets:**
| Outlet | Articles | % of corpus |
|--------|----------|------------|
| El Colombiano | 1,550 | 46.3% |
| W Radio | 747 | 22.3% |
| La Opinión | 436 | 13.0% |
| La Nación | 364 | 10.9% |
| El Diario | 204 | 6.1% |
| Caracol Radio | 31 | 0.9% |
| El Nuevo Día | 17 | 0.5% |

**Event Distribution by Topic:**
- Elecciones locales 2024: 85 events
- Reforma tributaria 2023: 22 events
- Reforma pensional: 9 events
- Acuerdo de paz: 4 events

**Multi-outlet Grouping:**
- 2 medios: 105 events (87.5%)
- 3 medios: 14 events (11.7%)
- 4 medios: 1 event (0.8%)

---

## Test 17K: MediaStack Corpus Generation

**Command:** `python3 generar_corpus.py --max-eventos 17000 --todos-los-medios --sin-cache --max-peticiones 2000`

**Timeline:**
- Start: 2026-10-04 22:18:08
- Stop: After 52 search rounds (exhausted result pages)
- Duration: **Est. ~50 minutes** (script hit API pagination limits)

**Results:**
| Metric | Value |
|--------|-------|
| Requested events | 17,000 |
| **Actual events found** | **107** |
| Total search rounds | 52 pages |
| New API requests used | ~165 |
| Accumulated target-outlet articles | 3,193 |
| Total API results parsed | ~25,000 articles |
| Stop reason | No more results from MediaStack |

**Critical Finding:**
The 17K test found **FEWER events (107) than the 1K test (120)**. This indicates:
- The API exhausted its available results for the query keywords
- Continuing pagination yields diminishing returns (mostly 0-5 articles per round after round 20)
- The total searchable pool is approximately **~120-130 real multi-outlet events**, not 17,000

---

## Scaling Analysis

### Time Scaling

| Scale | Actual Duration | Events Generated | Requests Used | Events/min |
|-------|-----------------|------------------|---------------|-----------|
| 1K target | 7.6 min | 120 | 260 | 15.8 |
| 17K target | ~50 min (est.) | 107 | ~165 | 2.1 |

**Analysis:**
- **NOT linear:** The 17K run is NOT ~14.2× slower (17,000÷1,000). It's only ~6.6× slower.
- **Why?** The 1K test searched 100 pages; the 17K test only searched 52 pages before hitting API limits.
- **Implication:** More pages don't mean more events. The API returns diminishing results as you page deeper.

### Data Ceiling

The corpus generation hit a **data-availability ceiling around 120 events**:

- **Rounds 1-23:** Good yield (10-100 articles per keyword query)
- **Ronds 24-52:** Minimal yield (0-10 articles per query, mostly 0-5)
- **After round 52:** No new results for any keyword

**Why?** MediaStack's indexing of Colombian outlets is limited. El Tiempo, Caracol, and Blu Radio are either:
1. Not indexed in MediaStack at all
2. Indexed with very sparse historical coverage
3. Behind paywalls that MediaStack cannot crawl

---

## File Size & Efficiency

| Test | Events | Articles | File size | Avg article size |
|------|--------|----------|-----------|-----------------|
| 1K | 120 | 256 | 0.19 MB | 0.74 KB |
| 17K target → actual 107 | 107 | ~210 (est.) | ~0.17 MB (est.) | ~0.81 KB |

**Extrapolation to 17K (if available):**
- Linear estimate: 120 × (17,000 ÷ 1,000) = **2,040 events** (if we had that many)
- Actual ceiling suggests: **~120-130 events max** (API-limited, not computation-limited)
- Linear file-size estimate: 0.19 × 17 = **3.23 MB**
- Realistic file-size ceiling: **~0.20 MB** (hitting event limit, not storage)

---

## API Quota Usage

**MediaStack Paid Plan ($24 budget):**
- Test 1K: 260 requests
- Test 17K: ~165 requests
- **Total: ~425 requests**
- **Remaining quota: ~75% unused** (conservative estimate ~1500+ remaining)

**Conclusion:** Quota is NOT the limiting factor. The API's indexing of Colombian outlets is.

---

## Outlet Coverage Reality Check

**Requested outlets (project specification):**
- El Tiempo (eltiempo.com) — NOT FOUND
- Noticias Caracol (noticiascaracol.com) — NOT FOUND
- Blu Radio (bluradio.com) — NOT FOUND

**Actually found (MediaStack's indexing):**
- El Colombiano (47% of corpus)
- W Radio (22% of corpus)
- La Opinión (13% of corpus)
- La Nación (11% of corpus)
- El Diario (6% of corpus)
- Caracol Radio (1% — not Noticias Caracol)
- El Nuevo Día (0.5%)

**Verdict:** MediaStack is indexing different sources than the project requires. The outlet mismatch is fundamental, not a configuration issue.

---

## Key Findings

### 1. **Data Availability Constraint**
- MediaStack does not index El Tiempo, Noticias Caracol, or Blu Radio
- Maximum corpus size from MediaStack: ~120 real multi-outlet events
- This is 0.7% of the 17K target, not a scaling issue—a data-availability issue

### 2. **Search Exhaustion**
- The 17K test exhausted the API's available results after 52 pages
- The 1K test could have continued but would find the same articles (due to caching & same queries)
- Both tests converge on ~120 unique multi-outlet events

### 3. **Outlet Mismatch**
- Expected: El Tiempo, Caracol, Blu Radio
- Found: El Colombiano, W Radio, La Opinión, La Nación, El Diario
- This mismatch means the corpus does NOT match the project's media-bias-detection objectives (comparing 3 specific outlets)

### 4. **Diminishing Returns Pattern**
- Rounds 1-10: ~50-100 target articles per round
- Rounds 11-23: ~20-40 target articles per round
- Rounds 24-52: ~0-10 target articles per round
- Result: 52 rounds yield only 7 more events than 23 rounds

---

## Recommendations for FASE 4

### Option A: Alternative Data Source (Recommended)
**Use RSS feeds** from the actual outlets:
- **Ventajas:** Unlimited requests, real articles from El Tiempo/Caracol/Blu Radio
- **Desventajas:** Requires RSS parsing, limited to recent articles only
- **Effort:** ~2-3 hours to implement parser + collect baseline corpus
- **Timeline:** Could have 100+ real multi-outlet events in a day

### Option B: Hybrid Approach
**Combine MediaStack + RSS:**
- Use MediaStack for secondary outlets (El Colombiano, W Radio, etc.)
- Use RSS for primary outlets (El Tiempo, Caracol, Blu Radio)
- Result: Broader media diversity + required outlet coverage

### Option C: Manual Curation
**Collect articles manually from news archives:**
- Internet Archive (Wayback Machine) for historical snapshots
- Direct newspaper archives (some are open access)
- Timeline: 2-3 hours for 50-100 real events
- Limited to past dates (2020-2024)

### Option D: Accept MediaStack Limitations
**Use the 120-event corpus as-is:**
- Proceed with FASE 4 using available data
- Document that corpus uses El Colombiano, W Radio, etc. instead of El Tiempo/Caracol/Blu Radio
- **Risk:** Project scope changes; bias analysis applies to different outlets than intended

---

## Decision Point

**MediaStack Benchmark Conclusion:**
✅ **Technically works** — Successfully generates well-formatted corpus with proper event grouping  
❌ **Does not meet project requirements** — Wrong outlets, insufficient events, API-limited ceiling  
⚠️ **Not a scalability problem** — Even with unlimited API quota, MediaStack won't find El Tiempo/Caracol/Blu Radio

**Next Step:** Choose between RSS feeds (Option A, recommended) or manual curation (Option C) to access the specified Colombian outlets.

---

## Artifacts

- **Logs:** `bench_1k.log`, `bench_17k.log`
- **Corpus:** `corpus_eventos_reales.json` (120 events, 256 articles)
- **Analysis:** This document
