# PROMPT PARA BENCHMARKS CON NewsAPI

Alternativa a MediaStack para comparar escalabilidad y cobertura de noticias colombianas.

---

## COPIA ESTE PROMPT A TU TERMINAL O COPILOT:

```
He pagado NewsAPI y necesito ejecutar benchmarks con su API para generar corpus de 1K y 17K eventos.

TAREAS NEWSAPI:

1. CREAR SCRIPT ALTERNATIVO generar_corpus_newsapi.py:
   ```python
   #!/usr/bin/env python3
   import requests
   import json
   import time
   from datetime import datetime, timedelta
   from collections import defaultdict
   from pathlib import Path
   import sys
   import os

   # API Key de NewsAPI
   NEWSAPI_KEY = os.getenv('NEWSAPI_KEY', 'd8e82adf19434eb0a1b3a57925071b8c')
   NEWSAPI_URL = 'https://newsapi.org/v2/everything'

   KEYWORDS = [
       'reforma tributaria',
       'acuerdo paz',
       'reforma pensional',
       'elecciones colombia',
       'gobierno colombia',
       'crisis economia',
       'seguridad colombia',
       'conflicto armado',
       'educacion colombia',
       'salud colombia'
   ]

   OUTLETS = {
       'el-tiempo': 'El Tiempo',
       'caracol': 'Noticias Caracol',
       'blu-radio': 'Blu Radio'
   }

   def buscar_noticias_newsapi(palabra, limit=100):
       """Busca en NewsAPI"""
       try:
           params = {
               'q': palabra,
               'apiKey': NEWSAPI_KEY,
               'sortBy': 'publishedAt',
               'language': 'es',
               'pageSize': limit
           }

           response = requests.get(NEWSAPI_URL, params=params, timeout=10)
           if response.status_code == 200:
               return response.json().get('articles', [])
       except:
           pass
       return []

   def agrupar_eventos(articulos, max_eventos=None):
       """Agrupa artículos por evento"""
       eventos_dict = defaultdict(list)

       for art in articulos:
           # Crear clave por palabras clave
           palabras = set()
           titulo = art.get('title', '').lower().split()
           descripcion = art.get('description', '').lower().split()

           palabras = tuple(sorted(set([p for p in titulo + descripcion if len(p) > 4])))

           if palabras:
               eventos_dict[palabras].append({
                   'medio': art.get('source', {}).get('name', 'unknown'),
                   'titulo': art.get('title', '')[:100],
                   'fecha': art.get('publishedAt', '')[:10],
                   'url': art.get('url', ''),
                   'texto': (art.get('description', '') or '')[:500]
               })

       # Filtrar eventos con 2+ medios
       eventos = []
       for i, (palabras, grupo) in enumerate(eventos_dict.items(), 1):
           if len(grupo) >= 2:
               eventos.append({
                   'evento_id': f'evento-{i:06d}',
                   'fecha': grupo[0]['fecha'],
                   'titulo': grupo[0]['titulo'],
                   'articulos': grupo
               })

           if max_eventos and len(eventos) >= max_eventos:
               break

       return eventos

   def generar_corpus_newsapi(max_eventos=1000, nombre_salida='corpus_eventos_newsapi.json'):
       """Genera corpus con NewsAPI y timing"""
       print(f"\n{'='*80}")
       print(f"🚀 GENERANDO CORPUS (NewsAPI): {max_eventos} eventos")
       print(f"{'='*80}\n")

       inicio = time.time()

       # Buscar
       print(f"📡 Buscando en NewsAPI ({len(KEYWORDS)} palabras clave)...")
       todos_articulos = []

       for palabra in KEYWORDS:
           print(f"   • {palabra}...", end=' ')
           articulos = buscar_noticias_newsapi(palabra, limit=100)
           todos_articulos.extend(articulos)
           print(f"✅ {len(articulos)} artículos")

       # Agrupar
       print(f"\n🔗 Agrupando por eventos...")
       eventos = agrupar_eventos(todos_articulos, max_eventos=max_eventos)

       # Guardar
       print(f"\n💾 Guardando {len(eventos)} eventos...")
       with open(nombre_salida, 'w', encoding='utf-8') as f:
           json.dump(eventos, f, indent=2, ensure_ascii=False)

       # Estadísticas
       tiempo_total = time.time() - inicio
       tamaño_mb = Path(nombre_salida).stat().st_size / (1024 * 1024)

       print(f"\n{'='*80}")
       print(f"✅ COMPLETADO")
       print(f"{'='*80}")
       print(f"⏱️  Tiempo: {tiempo_total:.2f} segundos ({tiempo_total/60:.2f} minutos)")
       print(f"📁 Archivo: {nombre_salida}")
       print(f"📊 Eventos: {len(eventos)}")
       print(f"📄 Tamaño: {tamaño_mb:.2f} MB")
       print(f"📈 Velocidad: {len(eventos)/tiempo_total:.0f} eventos/segundo")

       return tiempo_total, tamaño_mb, len(eventos)

   if __name__ == '__main__':
       max_eventos = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

       print(f"\n🧪 TEST NEWSAPI")
       print(f"   Meta: {max_eventos:,} eventos")
       print(f"   Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

       tiempo, tamaño, eventos = generar_corpus_newsapi(max_eventos)

       print(f"\n💡 Para 17K eventos:")
       tiempo_estimado_17k = tiempo * (17000 / max_eventos)
       print(f"   ⏱️  Tiempo estimado: {tiempo_estimado_17k/60:.1f} minutos")
       print(f"   📁 Tamaño estimado: {tamaño * (17000 / max_eventos):.1f} MB")
   ```

2. EJECUTAR TESTS:
   ```bash
   cd workshops/media-bias-detection/
   
   # Test 1K
   time python3 generar_corpus_newsapi.py 1000 2>&1 | tee bench_newsapi_1k.log
   
   # Test 17K
   time python3 generar_corpus_newsapi.py 17000 2>&1 | tee bench_newsapi_17k.log
   ```

3. CREAR COMPARATIVA:
   
   Después de ambos tests, crea BENCHMARK_COMPARISON.md:
   
   ```markdown
   # Benchmark Comparison: MediaStack vs NewsAPI

   ## Test 1K Events

   ### MediaStack
   - Tiempo: X minutos
   - Tamaño: A MB
   - Velocidad: V1 eventos/seg
   - Eventos encontrados: N1

   ### NewsAPI
   - Tiempo: Y minutos
   - Tamaño: B MB
   - Velocidad: V2 eventos/seg
   - Eventos encontrados: N2

   ## Test 17K Events

   ### MediaStack
   - Tiempo: X' minutos
   - Tamaño: A' MB
   - Velocidad: V1' eventos/seg

   ### NewsAPI
   - Tiempo: Y' minutos
   - Tamaño: B' MB
   - Velocidad: V2' eventos/seg

   ## Análisis Comparativo

   ### Velocidad
   - MediaStack vs NewsAPI: [ratio]
   - Escalabilidad: [lineal o sublineal?]

   ### Cobertura
   - MediaStack: ¿qué outlets cubre?
   - NewsAPI: ¿qué outlets cubre?
   - ¿Cuál tiene más eventos reales?

   ### Costo
   - MediaStack: $24 de quota
   - NewsAPI: X requests usadas de quota
   - ¿Cuál es más eficiente?

   ## Recomendación para FASE 4
   - ¿MediaStack o NewsAPI?
   - ¿Combinación de ambas?
   - ¿RSS feeds como respaldo?
   ```

4. HACER COMMITS:
   ```bash
   git add generar_corpus_newsapi.py corpus_eventos_newsapi.json
   git commit -m "test(corpus): NewsAPI 1K events scaling benchmark"
   git push
   
   git add corpus_eventos_newsapi.json
   git commit -m "test(corpus): NewsAPI 17K events final test"
   git push
   
   git add BENCHMARK_COMPARISON.md bench_newsapi_1k.log bench_newsapi_17k.log
   git commit -m "docs: MediaStack vs NewsAPI comparison and analysis"
   git push
   ```
```

---

## PASOS RÁPIDOS:

### 1️⃣ Crea el script Python (copia todo el código arriba)
Guarda como `generar_corpus_newsapi.py`

### 2️⃣ Ejecuta los tests:
```bash
cd /Users/abelalbuez/Documents/Maestria/Cuarto\ Semestre/PLN/natural-language-processing-workshops/workshops/media-bias-detection/

echo "=== TEST 1K NewsAPI ===" 
time python3 generar_corpus_newsapi.py 1000 2>&1 | tee bench_newsapi_1k.log

echo && echo "=== TEST 17K NewsAPI ===" 
time python3 generar_corpus_newsapi.py 17000 2>&1 | tee bench_newsapi_17k.log
```

### 3️⃣ Analiza y compara:
Pega los outputs aquí para que genere `BENCHMARK_COMPARISON.md`

---

## RESULTADO ESPERADO:

✅ Script alternativo funcional con NewsAPI  
✅ Benchmarks de 1K y 17K eventos  
✅ Comparativa MediaStack vs NewsAPI  
✅ Datos para decidir cuál usar en FASE 4  
✅ 3 commits documentando alternativa  

**Beneficio:** Sabrás cuál API escala mejor, cubre más outlets, y es más eficiente.
