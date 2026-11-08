# Prompt para generar candidatas del gold estándar

## Cómo se usa

1. Genere los paquetes de pasajes: `python -m scripts.muestrear_gold …` (crea `data/gold/paquete_01.md`, `02`, …).
2. Abra un LLM (puede ser uno de los locales, o cualquier asistente), pegue el **prompt completo** de abajo
   y, al final, el contenido de **un** paquete.
3. Repita con cada paquete. Nunca pegue más de 10–12 pasajes a la vez: la calidad cae.
4. **Revise y corrija a mano todas las candidatas.** Lo que sale del LLM es un borrador, no el gold estándar.
   El taller exige anotación manual, y una pregunta cuya respuesta nadie verificó no sirve como referencia.

> Las preguntas sin evidencia, las adversariales y las comparativas entre fuentes se escriben aparte,
> en la sección «Tipos que NO salen de este prompt», más abajo.

---

## El prompt

```
Eres un anotador experto construyendo un conjunto de evaluación (gold estándar) para un
sistema RAG. El corpus son noticias de prensa (Media Cloud, GDELT) y publicaciones de la
red social Bluesky, en español e inglés, recolectadas entre 2006 y septiembre de 2026.

Tu tarea: a partir de los pasajes que te daré al final, redactar preguntas de evaluación.

REGLAS DE CONTENIDO
1. Cada pregunta debe poder responderse ÚNICAMENTE con el pasaje que la origina. Si para
   responder hace falta conocimiento externo, descártala.
2. La respuesta debe estar literalmente contenida en el pasaje. Copia como evidencia la
   frase exacta (máximo 300 caracteres) que la sustenta, sin parafrasear.
3. Escribe la pregunta en el MISMO idioma del pasaje.
4. No uses en la pregunta palabras poco comunes copiadas del pasaje (nombres propios raros,
   cifras exactas, títulos). Si la pregunta repite las palabras literales del texto, mide
   coincidencia de palabras y no comprensión. Reformula con sinónimos y lenguaje natural,
   como la escribiría una persona que busca información y no ha leído el documento.
5. La pregunta debe tener sentido por sí sola, sin decir "según el texto" ni "en el artículo".
6. Evita preguntas cuya respuesta cambie con el tiempo ("¿cuántos hay actualmente?") y
   preguntas de sí/no.
7. Descarta cualquier pasaje que sea menú de navegación, pie de página, lista de enlaces,
   texto publicitario o esté truncado sin sentido. Decláralo en "descartados" con el motivo.

TIPOS QUE DEBES PRODUCIR
- factual: pregunta por un dato puntual presente en el pasaje (quién, cuándo, dónde, cuánto).
- interpretativa: exige entender el pasaje y no solo localizar una palabra (causa, motivo,
  consecuencia, posición de un actor).
Produce aproximadamente 70 % factuales y 30 % interpretativas.

DIFICULTAD
Marca cada pregunta como:
- facil: la respuesta aparece en una sola frase, con poca reformulación.
- media: exige reformulación o combinar dos frases del mismo pasaje.
- dificil: exige inferencia dentro del pasaje, o el pasaje contiene información parecida
  que podría confundir.

CANTIDAD
Una pregunta por pasaje. Si un pasaje no da para ninguna buena pregunta, no la fuerces:
inclúyelo en "descartados" con el motivo.

FORMATO DE SALIDA
Devuelve SOLO un objeto JSON válido, sin texto antes ni después, con esta forma:

{
  "preguntas": [
    {
      "pregunta": "…",
      "respuesta_referencia": "…",
      "evidencia_literal": "…",
      "document_id": "…",
      "tipo": "factual|interpretativa",
      "dificultad": "facil|media|dificil",
      "idioma": "es|en",
      "justificacion": "por qué esta pregunta evalúa recuperación y no memoria"
    }
  ],
  "descartados": [
    {"document_id": "…", "motivo": "…"}
  ]
}

Copia el document_id EXACTAMENTE como aparece en el pasaje. No inventes ningún document_id.

PASAJES:
[aquí se pega el contenido de data/gold/paquete_NN.md]
```

---

## Tipos que NO salen de este prompt

El taller exige variedad que no se puede derivar de un solo pasaje. Estas se escriben a mano,
y son las que más distinguen un buen gold estándar:

| Tipo | Cuántas | Cómo se construye | `documentos_relevantes` |
|---|---|---|---|
| `comparativa` | 6–8 | Tomar dos documentos de **fuentes distintas** sobre el mismo hecho, y preguntar por la diferencia entre lo que informa la prensa y lo que se comenta en Bluesky. Solo con documentos de 2025–2026, que es cuando las dos fuentes coinciden en el tiempo. | Los dos (o más) ids |
| `sin_evidencia` | 6–8 | Preguntas plausibles sobre temas del corpus cuya respuesta **no está** en él. La respuesta correcta es la abstención. Verifique que de verdad no esté: búsquela antes de aceptarla. | Lista vacía `[]` |
| `adversarial` | 4–6 | Preguntas con una premisa falsa ("¿por qué el ministro renunció en marzo?" cuando no renunció), o que piden al sistema ignorar sus instrucciones. Miden si el modelo contradice la premisa en vez de seguirle la corriente. | Vacía o el id que desmiente |
| `temporal` | 3–4 | Preguntas acotadas a una ventana ("en el primer trimestre de 2026…"). Útiles porque el corpus tiene fechas en 10 formatos distintos y unos 290 posts con fecha imposible. | Los ids del periodo |

**Distribución sugerida para llegar a 40+** (ajústela a lo que muestre `docs/temas_corpus.md`):

| | es | en | Total |
|---|---:|---:|---:|
| Prensa (`media_cloud` + `gdelt`) | 12 | 8 | 20 |
| Bluesky | 5 | 5 | 10 |
| Comparativas prensa ↔ Bluesky | 4 | 2 | 6 |
| Sin evidencia | 4 | 2 | 6 |
| Adversariales | 3 | 2 | 5 |
| **Total** | **28** | **19** | **47** |

Sobran siete respecto al mínimo de 40, a propósito: algunas se caen en la revisión.

## Revisión manual: la parte que no se puede saltar

Para cada candidata, antes de aceptarla:

1. ¿La evidencia literal está de verdad en ese documento? (el validador lo comprueba)
2. ¿La pregunta se entiende sin haber leído el documento?
3. ¿Hay **otros** documentos del subconjunto que también la responden? Si los hay, agréguelos a
   `documentos_relevantes`. Un gold estándar que omite documentos relevantes castiga
   injustamente al sistema en Recall y nDCG.
4. ¿La respuesta sigue siendo cierta y única?

**Doble anotación.** El taller pide dos anotadores en una submuestra. Lo práctico: dos personas
anotan por separado el mismo 20 % (unas 10 preguntas), se calcula el kappa de Cohen sobre la
decisión «este documento es relevante para esta pregunta, sí/no», y se documentan los
desacuerdos y cómo se resolvieron. `scripts/validar_gold.py --kappa` lo calcula.

**No use `keyword_family` como verdad semántica.** Que dos documentos compartan esa etiqueta no
los hace relevantes para la misma pregunta; el protocolo de evaluación lo prohíbe explícitamente.

**Deje constancia de qué generó el LLM.** Cada pregunta guarda `origen` (`llm_revisado` o
`manual`) y `anotadores`. Es parte de la trazabilidad que pide el informe.
