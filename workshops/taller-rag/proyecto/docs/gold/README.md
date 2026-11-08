# Gold estándar: cómo se construye y cómo se guarda

El principio que organiza todo: **el gold estándar es fijo; las configuraciones cambian.**
Las preguntas y sus documentos relevantes se escriben una vez y no se tocan al cambiar `k`,
el modelo o el tamaño de fragmento. Cada ejecución se guarda aparte y se une al gold por
`question_id`. Si mezcla las dos cosas en un mismo archivo, deja de poder comparar.

```
data/gold/
  subconjunto_ids.txt     documentos indexados; FIJO para todo el experimento
  muestra.jsonl           metadatos de los documentos muestreados
  paquete_01.md …         pasajes para el prompt de generación
  gold.jsonl              LAS PREGUNTAS  ← el entregable
  anotador_a.jsonl        submuestra del anotador A (kappa)
  anotador_b.jsonl        submuestra del anotador B (kappa)
data/runs/
  configuraciones.jsonl   una línea por configuración probada
  run_<config_id>_<n>.jsonl   resultados crudos, una línea por pregunta
reports/
  recuperacion.csv        tabla de métricas de recuperación
  generacion.csv          tabla de métricas de generación
```

## Orden de trabajo

```bash
# 1. ¿De qué trata el corpus? (decide los temas de las preguntas)
docker compose exec api python -m scripts.perfilar_temas --input data/documentos_rag.parquet

# 2. Muestra estratificada → documentos a indexar + pasajes para el prompt
docker compose exec api python -m scripts.muestrear_gold \
  --input data/documentos_rag.parquet \
  --cuota media_cloud:es=18 --cuota media_cloud:en=10 \
  --cuota bluesky:es=8  --cuota bluesky:en=8 \
  --cuota gdelt:es=3    --cuota gdelt:en=3 \
  --desde 2025-01-01 --excluir-ruido --semilla 20261106

# 3. Indexar EXACTAMENTE ese subconjunto (no --limit: eso toma las primeras filas)
docker compose exec api python -m scripts.ingest \
  --input data/documentos_rag.parquet --ids-file data/gold/subconjunto_ids.txt --limit 0

# 4. Generar candidatas con el prompt (docs/gold/prompt_generacion.md), revisarlas a mano
#    y escribirlas en data/gold/gold.jsonl

# 5. Validar antes de evaluar
docker compose exec api python -m scripts.validar_gold \
  --gold data/gold/gold.jsonl --ids data/gold/subconjunto_ids.txt \
  --corpus data/documentos_rag.parquet
```

El paso 3 es el que hace reproducible todo lo demás. Con `--limit 500` se indexan las primeras
500 filas del archivo, que no son una muestra aleatoria ni cubren las cuotas por fuente e idioma.

## `gold.jsonl`: una pregunta por línea

```json
{
  "question_id": "q007",
  "pregunta": "¿Qué razón dio el gobierno para aplazar la medida?",
  "idioma": "es",
  "tipo": "interpretativa",
  "dificultad": "media",
  "fuente_esperada": "media_cloud",
  "documentos_relevantes": ["a3f9c1...", "77b2de..."],
  "respuesta_referencia": "La falta de presupuesto para el segundo semestre.",
  "evidencia_literal": "el aplazamiento obedece a que no hay presupuesto asignado para el segundo semestre",
  "split": "dev",
  "origen": "llm_revisado",
  "anotadores": ["KL", "AA"],
  "notas": "El documento 77b2de también la responde; se agregó en la revisión.",
  "creada": "2026-11-07"
}
```

| Campo | Para qué sirve |
|---|---|
| `question_id` | Une la pregunta con todas sus ejecuciones. Nunca se reutiliza ni se renumera. |
| `documentos_relevantes` | **La verdad de referencia.** Sin esto no hay Recall@k, MRR ni nDCG. Vacía en `sin_evidencia`. |
| `respuesta_referencia` | Para juzgar corrección de la generación. |
| `evidencia_literal` | Frase textual del documento. El validador comprueba que exista de verdad. |
| `split` | `dev` para iterar prompts y parámetros; `test` solo se usa al final. |
| `tipo` | `factual`, `interpretativa`, `comparativa`, `sin_evidencia`, `adversarial`, `temporal`. |
| `origen` | `manual` o `llm_revisado`. Trazabilidad exigida por el informe. |

**La regla del `test`:** si mira los resultados del `test` para decidir un cambio, ese conjunto
deja de ser independiente y las cifras finales dejan de significar lo que dicen. Use `dev` para
todo el ajuste, y toque `test` una sola vez, al final. Reparta alrededor de 60 % `dev` y 40 % `test`,
manteniendo las proporciones de tipo, fuente e idioma en ambos.

**JSONL y no CSV:** cada línea es un JSON independiente, los campos de lista caben sin inventar
separadores, y el archivo se puede ir ampliando. Excel destroza los acentos y convierte los ids
en notación científica. Si quiere anotar en una hoja de cálculo, expórtela a JSONL antes de usarla.

## Probar con distintos parámetros

Cada configuración es una línea en `data/runs/configuraciones.jsonl`:

```json
{"config_id": "c01", "descripcion": "línea base",
 "chunk_size": 1000, "overlap": 150, "encoder": "intfloat/multilingual-e5-small",
 "k": 5, "llm": "qwen2.5:1.5b", "temperatura": 0, "prompt_version": "p1",
 "coleccion": "rag_e5s_c1000_v1", "subconjunto": "data/gold/subconjunto_ids.txt"}
{"config_id": "c02", "descripcion": "k=10", "k": 10, "...": "resto igual a c01"}
{"config_id": "c03", "descripcion": "fragmentos de 256 tokens",
 "chunk_size": 256, "unidad": "tokens", "coleccion": "rag_e5s_tok256_v1", "...": "resto igual a c01"}
```

Y cada ejecución escribe `data/runs/run_c01_1.jsonl`, con una línea por pregunta:

```json
{"run_id": "c01_1", "config_id": "c01", "question_id": "q007", "repeticion": 1,
 "recuperados": ["chunkA", "chunkB", "chunkC", "chunkD", "chunkE"],
 "documentos_recuperados": ["a3f9c1...", "0ddc21...", "..."],
 "scores": [0.878, 0.841, 0.822, 0.810, 0.799],
 "respuesta": "…", "abstuvo": false, "citas": [1, 3],
 "latencia_recuperacion_s": 0.09, "latencia_generacion_s": 11.4,
 "arranque": "caliente", "timestamp": "2026-11-07T10:14:03Z"}
```

Tres reglas que hacen comparable el experimento:

1. **Un parámetro a la vez.** Si cambia `k` y el modelo juntos, no sabrá a cuál atribuir la diferencia.
2. **Una colección por configuración de indexado.** Cambiar `chunk_size` o el encoder obliga a
   reindexar: ponga un nombre distinto (`rag_e5s_c1000_v1`, `rag_e5s_tok256_v1`) en vez de
   sobrescribir. Si reutiliza el nombre, mezcla vectores de dos configuraciones y los resultados
   dejan de significar nada.
3. **Tres repeticiones por condición**, y anote si el modelo estaba en arranque frío o caliente.
   La primera consulta a un modelo recién cargado tarda mucho más y distorsiona la latencia media.

Las métricas se calculan después, uniendo `gold.jsonl` con cada `run_*.jsonl` por `question_id`:
Recall@k, hit@k, MRR y nDCG@k salen de comparar `documentos_recuperados` con
`documentos_relevantes`; la abstención y las citas salen de la respuesta. Separe la tabla de
recuperación de la de generación: con la recuperación fija, las diferencias entre modelos son
atribuibles al LLM, que es la pregunta central del taller.

## Errores que arruinan un gold estándar

- **Preguntas copiadas del texto.** Si la pregunta repite las palabras exactas del documento,
  mide coincidencia léxica y no comprensión, y cualquier buscador la resuelve.
- **Documentos relevantes incompletos.** Si tres documentos responden la pregunta y solo anotó
  uno, el sistema pierde puntos por recuperar un documento que sí era correcto.
- **Preguntas que dependen del momento.** "¿Cuántos hay actualmente?" no tiene respuesta estable.
- **Todo en español, o todo de prensa.** El corpus es 56 % inglés y 35 % Bluesky; un gold
  desbalanceado mide un sistema distinto del que tienen.
- **Usar `keyword_family` como verdad.** Compartir etiqueta temática no es ser relevante para
  una pregunta. El protocolo lo prohíbe explícitamente.
