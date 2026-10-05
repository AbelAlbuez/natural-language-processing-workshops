# PROMPT: Ejecutar Corpus con NewsAPI

## Advertencia IMPORTANTE

NewsAPI tiene **limitaciones críticas**:
- Max 100 resultados por consulta
- Solo últimos 30 días
- NO indexa El Tiempo, Caracol, Blu Radio
- Probablemente dará 0 eventos

Pero si quieres probar:

## Ejecuta esto:

```bash
# 1. Ve a la carpeta
cd /Users/abelalbuez/Documents/Maestria/Cuarto\ Semestre/PLN/natural-language-processing-workshops/

# 2. Configura API key NewsAPI
export NEWSAPI_KEY="d8e82adf19434eb0a1b3a57925071b8c"

# 3. Ejecuta el script
cd workshops/media-bias-detection/
time python3 generar_corpus_newsapi.py 1000 2>&1 | tee bench_newsapi.log

# 4. Verifica resultado
cat bench_newsapi.log | tail -20
```

## Qué esperar

```
Resultado probable:
   Eventos: 0 (NewsAPI no tiene cobertura)
   Razón: No indexa El Tiempo/Caracol/Blu Radio
```

Si quieres resultados REALES, usa `generar_corpus.py` (MediaStack) en su lugar. 🎯
