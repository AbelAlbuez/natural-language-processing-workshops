# PROMPT: Ejecutar Scripts y Analizar Resultados

## Parte 1: Ejecutar MediaStack (RECOMENDADO)

```bash
# 1. Configura el API key
export MEDIASTACK_API_KEY="5f855a76f3e987cdbc21d5fb1a84ba0e"

# 2. Ve a la carpeta
cd /Users/abelalbuez/Documents/Maestria/Cuarto\ Semestre/PLN/natural-language-processing-workshops/workshops/media-bias-detection/

# 3. Ejecuta con 1000 eventos
echo "=== TEST 1000 EVENTOS ==="
time python3 generar_corpus.py 1000 2>&1 | tee bench_mediastack_1k.log

# 4. Revisa resultados
echo ""
echo "=== RESULTADOS 1K ==="
tail -15 bench_mediastack_1k.log
echo ""
echo "Corpus creado:"
ls -lh corpus_eventos_reales.json
echo ""
echo "Primeros 2 eventos:"
head -50 corpus_eventos_reales.json
```

## Parte 2: OPCIONAL - Ejecutar NewsAPI (para comparar)

```bash
# 1. Configura API key NewsAPI
export NEWSAPI_KEY="d8e82adf19434eb0a1b3a57925071b8c"

# 2. Ejecuta
echo "=== TEST NewsAPI ==="
time python3 generar_corpus_newsapi.py 1000 2>&1 | tee bench_newsapi_1k.log

# 3. Revisa
echo ""
echo "=== RESULTADOS NewsAPI ==="
tail -15 bench_newsapi_1k.log
```

## Parte 3: Análisis Manual

Copia los outputs aquí y responde:

### De MediaStack:
1. **Eventos encontrados:** [X de 1000]
2. **Tiempo total:** [X minutos]
3. **Tamaño archivo:** [X MB]
4. **Medios encontrados:** (Copia la lista)
5. **Velocidad:** [X eventos/segundo]

### De NewsAPI (si lo ejecutaste):
1. **Eventos encontrados:** [X]
2. **Tiempo:** [X minutos]
3. **Medios:** [Cuáles aparecen?]

---

## Parte 4: Comparativa

Después de ejecutar ambos, responde:

```
MEDIASTACK vs NewsAPI:

1. Velocidad
   - MediaStack: X eventos/min
   - NewsAPI: Y eventos/min
   - Ganador: ___

2. Cobertura de outlets
   - MediaStack encontró: ___
   - NewsAPI encontró: ___
   - Ganador: ___

3. Cobertura de OUTLETS OBJETIVO
   - El Tiempo: (MediaStack: SI/NO | NewsAPI: SI/NO)
   - Caracol: (MediaStack: SI/NO | NewsAPI: SI/NO)
   - Blu Radio: (MediaStack: SI/NO | NewsAPI: SI/NO)

4. Conclusión
   - ¿Cuál es mejor para FASE 4? ___
   - ¿Por qué? ___
```

---

## Espera que termine

MediaStack: ~8-10 minutos
NewsAPI: ~2-3 minutos

Luego copia los outputs acá para análisis. 🎯
