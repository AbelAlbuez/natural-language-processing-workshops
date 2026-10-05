# Benchmark Results: MediaStack Corpus Generation

Fecha: 2026-10-04 · Script: `generar_corpus.py` · Plan MediaStack: pago (HTTPS + histórico)

Ambas ejecuciones usaron los mismos parámetros salvo `--max-eventos`:

```bash
python3 generar_corpus.py --max-eventos {1000|17000} --todos-los-medios --sin-cache --max-peticiones 2000
```

- `--todos-los-medios`: MediaStack **no indexa** El Tiempo, Noticias Caracol ni Blu Radio
  (0 artículos en ambos tests); sin este flag el corpus queda vacío.
- `--sin-cache`: todas las páginas se pidieron a la API, así que los tiempos son reales y comparables.
- `--max-peticiones 2000`: tope de seguridad; no se alcanzó.

Logs completos: [`bench_1k.log`](bench_1k.log), [`bench_17k.log`](bench_17k.log).

## Test 1K Events
- **Tiempo ejecutado:** 455.8 s (7.6 min) — `time`: 7:35.99 total, 22.9 s de CPU
- **Eventos generados:** 120 (solicitados: 1 000)
- **Artículos:** 256
- **Tamaño archivo:** 0.19 MB
- **Velocidad:** 0.26 eventos/segundo
- **Peticiones a MediaStack:** 260 (25 602 resultados recibidos, 3 349 de medios colombianos objetivo)
- **Proyección a 17K (estimada por el script):** 1 076 min (~17.9 h), 26.8 MB
- **Motivo de parada:** MediaStack no tiene más resultados para las palabras clave

## Test 17K Events
- **Tiempo ejecutado:** 453.5 s (7.6 min) — `time`: 7:33.66 total, 23.3 s de CPU
- **Eventos generados:** 120 (solicitados: 17 000)
- **Artículos:** 256
- **Tamaño archivo:** 0.19 MB
- **Velocidad:** 0.26 eventos/segundo
- **Peticiones a MediaStack:** 260
- **Motivo de parada:** MediaStack no tiene más resultados para las palabras clave

El archivo `corpus_eventos_reales.json` de ambos tests es **idéntico byte a byte**
(mismos 120 eventos, mismas 256 URLs).

## Análisis de Escalabilidad

> Ninguno de los dos tests llegó a su objetivo: ambos se detuvieron en el mismo punto
> (la API se quedó sin resultados), así que los ratios 17K/1K no miden escalabilidad,
> sino reproducibilidad. La escalabilidad real se estima abajo a partir del costo por evento.

### Tiempo
- Test 1K: 7.6 min
- Test 17K: 7.6 min
- Ratio: 453.5 / 455.8 = **0.99**
- Esperado: ~17x si es lineal **y** si hubiera datos para 17K eventos
- Observado: mismo trabajo en ambos (260 peticiones, 100 rondas), por eso el mismo tiempo.
  El 95 % del tiempo es espera de red: 23 s de CPU sobre 455 s totales (~1.75 s por petición).
  La agrupación por eventos no es el cuello de botella.

### Tamaño
- Test 1K: 0.19 MB
- Test 17K: 0.19 MB
- Ratio: **1.0**
- Esperado: ~17x
- Observado: mismo corpus. Por evento: ~1.6 KB (2.1 artículos × ~430 caracteres de texto).
  Para 17 000 eventos eso da ~27 MB, coherente con la proyección del script.
  El texto es solo el resumen de MediaStack (~430 caracteres); con `--texto-completo`
  el tamaño por evento sería varias veces mayor.

### Velocidad (eventos/segundo)
- Test 1K: 0.26 eventos/seg
- Test 17K: 0.26 eventos/seg
- Cambio: ninguno
- Análisis: la velocidad la fija el rendimiento de la API, no el algoritmo:
  **0.46 eventos por petición** (120 / 260). Además el rendimiento decae en las últimas rondas:
  las primeras 20 rondas (101 peticiones) dieron 100 eventos; las 80 siguientes
  (159 peticiones, solo la consulta "elecciones") dieron 20 más.

## Conclusiones

1. **¿Es lineal?** El tiempo es lineal en el **número de peticiones** (~1.75 s cada una), no en
   el número de eventos pedidos. Con las 4 palabras clave actuales el techo es **120 eventos**,
   pidas 1 000 o 17 000.
2. **¿Eficiencia?** Se degrada con más datos: cuanto más se pagina, menos eventos nuevos aparecen
   por petición. El procesamiento local (TF-IDF + agrupación por ventana de fechas) escala bien
   (23 s de CPU para 3 349 artículos y 100 reagrupaciones).
3. **¿Viable para FASE 4?** **No con la configuración actual.** Para 17 000 eventos, al
   rendimiento observado (0.46 eventos/petición) harían falta **~37 000 peticiones** y **~18 h**
   de descarga, y sobre todo **mucho más vocabulario de búsqueda**: hoy las 4 consultas se agotan
   en 260 peticiones. Para escalar habría que:
   - ampliar mucho las palabras clave (más temas de política, economía, orden público, etc.);
   - usar el parámetro `date` (incluido en el plan de pago) para partir cada búsqueda por meses,
     porque MediaStack limita la paginación a ~10 000 resultados por consulta;
   - asumir que El Tiempo, Noticias Caracol y Blu Radio **no** estarán en el corpus, o
     incorporarlos por otra vía (RSS o scraping propio).
   Un objetivo realista con MediaStack y vocabulario ampliado está en el orden de cientos a pocos
   miles de eventos, no 17 000.
4. **Cuota:** los dos benchmarks usaron **520 peticiones** (260 + 260); sumando las pruebas previas,
   unas **600** en total. Con el plan Basic (10 000 peticiones/mes) eso es ~6 % de la cuota mensual.
   17 000 eventos (~37 000 peticiones) equivaldrían a ~4 meses de ese plan.

### Otras observaciones del corpus
- Fechas entre 2020-10 y 2026-05; los nombres de tema ("reforma tributaria 2023",
  "elecciones locales 2024") no filtran por año. 2024 aporta solo 45 de los 256 artículos.
- Temas desbalanceados: "elecciones" concentra 85 de los 120 eventos; "acuerdo de paz" solo 4.
- 105 eventos tienen 2 medios, 14 tienen 3 y 1 tiene 4.
