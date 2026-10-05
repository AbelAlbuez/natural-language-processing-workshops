# PROMPT PARA GENERAR SCRIPT CORPUS

Copia este prompt en Copilot o Claude y pídele que genere el archivo Python.

---

## PROMPT A COPILOT/CLAUDE:

```
Necesito un script Python que:

1. SE EJECUTE LOCALMENTE en mi PC (no en Colab)
2. Use MediaStack API con mi API key: 5f855a76f3e987cdbc21d5fb1a84ba0e
3. Busque noticias REALES de Colombia sobre estos temas:
   - reforma tributaria 2023
   - acuerdo de paz
   - reforma pensional
   - elecciones locales 2024

4. FILTRE POR ESTOS 3 OUTLETS:
   - El Tiempo
   - Noticias Caracol  
   - Blu Radio

5. GENERE UN ARCHIVO JSON con esta estructura (IMPORTANTE - IGUAL AL corpus_ejemplo.json):

```json
[
  {
    "evento_id": "evento-001",
    "medio": "El Tiempo",
    "titulo": "Título del artículo",
    "fecha": "YYYY-MM-DD",
    "url": "https://...",
    "texto": "Contenido del artículo aquí"
  }
]
```

REQUISITOS ESPECÍFICOS:

- El script debe leer corpus_ejemplo.json como REFERENCIA (solo para ver la estructura)
- Debe BUSCAR EVENTOS REALES usando MediaStack API
- Debe agrupar artículos del MISMO EVENTO cubiertos por DIFERENTES MEDIOS
- Si encuentra el mismo evento en 2+ outlets → lo agrupa
- Mínimo 20 artículos de cada outlet si es posible
- Máximo 50 eventos (si encuentra)
- Guardar en: workshops/media-bias-detection/corpus_eventos_reales.json

PARÁMETROS MEDIASTACK:
- API URL: https://api.mediastack.com/v1/news
- Parámetros principales:
  * access_key: 5f855a76f3e987cdbc21d5fb1a84ba0e
  * keywords: [reforma tributaria, acuerdo paz, reforma pensional, elecciones]
  * countries: co
  * limit: 100
  * sort: published_desc

LÓGICA DEL SCRIPT:
1. Para cada palabra clave → busca en MediaStack
2. Filtra resultados por los 3 outlets
3. Agrupa por EVENTO (artículos sobre el mismo tema)
4. Estructura como JSON (igual a corpus_ejemplo.json)
5. Guarda en corpus_eventos_reales.json
6. Imprime estadísticas: cuántos artículos x outlet, cuántos eventos encontrados

MANEJO DE ERRORES:
- Si MediaStack falla → mensajes claros de error
- Si no encuentra artículos → indicar que intente con palabras diferentes
- Mostrar progreso mientras busca

El script debe estar LISTO para ejecutar con: python3 generar_corpus.py
```

---

## CÓMO USARLO:

1. Copia TODO el texto entre los backticks (```) de arriba
2. Abre **Copilot** (en Visual Studio Code) o **Claude.ai**
3. Pega el prompt
4. Copilot/Claude te generará un script Python
5. Guarda el script como: `generar_corpus.py`
6. En tu terminal local ejecuta:
   ```bash
   cd /Users/abelalbuez/Documents/Maestria/Cuarto\ Semestre/PLN/natural-language-processing-workshops/workshops/media-bias-detection/
   python3 generar_corpus.py
   ```

---

## RESULTADO ESPERADO:

El script debería:
✅ Generar corpus_eventos_reales.json
✅ Con artículos REALES de MediaStack API
✅ De los 3 outlets colombianos
✅ Sobre eventos reales (2023-2024)
✅ Estructura idéntica a corpus_ejemplo.json
✅ Mostrar: "Guardado: X artículos en Y eventos"

---

## SI MEDIASTACK FALLA:

Si el API está bloqueado en tu red, el script indicará.
En ese caso, el script puede tener un FALLBACK para:
- Leer artículos de ejemplo
- O pedirte que descarges manualmente 

Pero intenta primero con el API.
