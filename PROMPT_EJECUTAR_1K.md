# PROMPT: Ejecutar Corpus con 1000 Eventos

## API Key: Correctamente Configurado

El script `generar_corpus.py` ahora tiene:
- ✓ API key desde **variable de entorno** (no hardcodeado)
- ✓ Palabras clave DIFERENTES para corpus diferente
- ✓ Todo listo para ejecutar

## Ejecuta esto en tu terminal:

```bash
# 1. Ve a la carpeta del proyecto
cd /Users/abelalbuez/Documents/Maestria/Cuarto\ Semestre/PLN/natural-language-processing-workshops/

# 2. Configura el API key (una sola vez)
export MEDIASTACK_API_KEY="5f855a76f3e987cdbc21d5fb1a84ba0e"

# 3. Ejecuta con 1000 eventos
cd workshops/media-bias-detection/
time python3 generar_corpus.py 1000 2>&1 | tee bench_1k_nuevo.log

# 4. Verifica el corpus (será DIFERENTE al anterior)
ls -lh corpus_eventos_reales.json
wc -l corpus_eventos_reales.json
```

## Palabras Clave (DIFERENTES):

```
- elecciones colombia
- reforma laboral
- inflacion colombia
- desempleo
- manifestaciones colombia
- corrupcion
- justicia transicional
- violencia urbana
- migracion venezolanos
- cambio climatico
```

Esto generará eventos sobre **diferentes temas** que el primer test.

## Espera que termine (~8-10 minutos)

El script imprimirá:
```
Tiempo: XX segundos
Eventos: XXX (de 1000 solicitados)
Articulos: XXX
```

Luego comparte aquí el output o el archivo `bench_1k_nuevo.log`
