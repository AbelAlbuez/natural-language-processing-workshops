# Auditoría de avance — Taller 3: IR sobre la Comisión de la Verdad

**Fecha de auditoría:** 2026-09-10  
**Modo:** solo lectura y diagnóstico. No se instalaron dependencias ni se modificaron archivos existentes.

## Inventario

Contenido de `03-IR-comision-de-la-verdad` hasta dos niveles:

```text
03-IR-comision-de-la-verdad/
├── README.md
├── Taller recuperacion.pdf
├── segmentacion_libros.py
├── corpus/
│   ├── CONVOCATORIA_A_LA_PAZ_GRANDE.json
│   ├── HALLAZGOS_Y_RECOMENDACIONES.json
│   ├── HASTA_LA_GUERRA_TIENE_LIMITES.json
│   ├── LA_COLOMBIA_FUERA_DE_COLOMBIA.json
│   ├── MI_CUERPO_ES_LA_VERDAD.json
│   ├── NO_ES_UN_MAL_MENOR.json
│   ├── NO_MATARAS.json
│   ├── RESISTIR_NO_ES_AGUANTAR.json
│   └── SUFRIR_LA_GUERRA_Y_REHACER_LA_VIDA.json
└── Libros_CEV/
    ├── contenido/       # 9 PDFs de libros CEV
    └── indices/         # 9 JSON de índices editoriales
```

Resumen de tipos: **1 script Python**, **0 notebooks**, **18 JSON** (9 corpus y 9 índices), **10 PDF** (9 libros y el enunciado), **1 Markdown**. No hay CSV, PKL, Parquet ni DOCX.

No se encontraron notebooks en la carpeta ni en sus subcarpetas. Por tanto, no hay conteo de celdas, `execution_count`, saltos de numeración ni notebooks similares que comparar. El único código está en [segmentacion_libros.py](segmentacion_libros.py).

Los nueve JSON de `corpus/` son listas de unidades y contienen los campos `libro`, `parte`, `capitulo`, `titulo`, `subtitulo`, `es_relato`, `pie_de_pagina` y `texto`. El tamaño va de 296 unidades en `CONVOCATORIA_A_LA_PAZ_GRANDE` a 12.631 en `HASTA_LA_GUERRA_TIENE_LIMITES`. Los nueve índices son listas de nodos con `pagina_inicio`, `parte` y `capitulo`. No existe un par de archivos `raw`/preprocesado.

## Veredicto rápido

| Actividad | Estado | Evidencia observada |
|---|---|---|
| 1. Extracción y preparación del corpus | ⚠️ Cumple con reservas | Hay segmentación estructural de 9 libros y corpus JSON exportados, pero no hay entrevistas, limpieza compartida ni corpus preprocesado separado. |
| 2. Análisis exploratorio | ❌ No cumple | No hay notebook ni código de estadísticas, frecuencias, nubes de palabras o comparación libros/entrevistas. |
| 3. Modelo de Recuperación de Información | ❌ No cumple | No existe vectorización TF-IDF, matriz de similitud, ranking ni medida de similitud. |
| 4. Rocchio y Okapi BM25 | ❌ No cumple | No hay funciones manuales, explicación, ejecución ni comparación de métricas. |
| 5. Comparación de corpus | ❌ No cumple | No hay comparación temática entrevista-libro, cuadro de vínculos ni heatmap. |
| 6. Informe final | ❌ No cumple | Solo existe el README técnico de segmentación; no hay informe integrador con resultados y conclusiones. |

## Bugs bloqueantes

🔴 **La extracción no puede reproducirse en el entorno actual.** La importación de [segmentacion_libros.py](segmentacion_libros.py#L37-L40) falla con `ModuleNotFoundError: No module named 'fitz'` antes de poder llamar a `construir_corpus`. No se instaló PyMuPDF porque la auditoría pidió avisar antes de instalar.

🔴 **El proyecto no contiene la implementación principal del taller.** No hay notebooks ni otro script que ejecute el flujo IR. En consecuencia, no es posible validar un `Restart & Run All`, rankings, métricas, gráficos o cifras del informe: esas piezas no están presentes.

🔴 **El script puede ocultar fallos de lote y dejar salidas antiguas.** En el bloque principal, cada libro se procesa dentro de un `try/except` amplio y el lote continúa tras cualquier excepción ([segmentacion_libros.py](segmentacion_libros.py#L405-L419)). Si un libro falla, su JSON previo no se elimina ni se marca como inválido. Esto puede producir un corpus mezclado entre ejecuciones sin que el resumen deje una salida inequívoca para consumo posterior.

## Resultados que no se sostienen

🟠 **Los JSON existentes no constituyen un corpus preprocesado.** Son corpus segmentados: el campo `texto` conserva texto de extracción y el README documenta que pueden quedar guiones de división silábica ([README.md](README.md#L43-L48)). No hay una segunda representación con tokenización, stopwords, lematización o normalización común.

🟠 **No hay una base comparable de entrevistas.** Todos los registros encontrados pertenecen a libros CEV; no hay archivos ni código que cargue entrevistas. Por eso no se puede sostener ninguna conclusión sobre similitud o patrones entre ambos corpus.

🟠 **La segmentación tiene limitaciones declaradas que afectan el análisis.** El propio código indica que testimonios sin guillemets pueden descartarse y que la clasificación depende de fuentes y tamaños tipográficos concretos ([segmentacion_libros.py](segmentacion_libros.py#L1-L31)). Esto exige cuantificar cobertura y revisar errores antes de usar las unidades como documentos de IR.

🟠 **La unidad documental aún no está conectada al modelo de recuperación.** El extractor sí conserva libro, parte, capítulo, título, subtítulo, relato y página implícita en la unidad ([segmentacion_libros.py](segmentacion_libros.py#L311-L365)), pero no existe una decisión posterior sobre si recuperar por unidad, testimonio, capítulo o libro completo, ni una evaluación de esa elección.

🟠 **No hay umbral ni normalización de similitud que auditar.** Al no existir ranking o heatmap, no puede comprobarse si las puntuaciones se comparan por longitud, si hay fuga entre consulta y documentos, o si un umbral arbitrario cambia los vínculos reportados.

## Faltantes de requisito

El PDF [Taller recuperacion.pdf](Taller%20recuperacion.pdf) exige, entre otros puntos, “Preprocesar los textos extraídos y las entrevistas para su análisis” (p. 2), “Utilizar técnicas como la vectorización de textos (TF-IDF)” (p. 2), “Comparación de patrones léxicos entre los textos de los libros y las entrevistas” (p. 2), “Implementar manualmente las métricas de Rocchio y Okapi BM25” (p. 2), un gráfico de “heatmap” del relacionamiento (p. 3), y un informe final que integre los resultados (p. 3). No se encontró evidencia ejecutable de ninguno de esos componentes.

### Checklist de entregables

- [ ] **Corpus extraído y preprocesado:** hay corpus segmentado de libros, pero falta el archivo preprocesado y el corpus de entrevistas; tampoco hay dos archivos explícitos `raw` + preprocesado.
- [ ] **Informe de análisis exploratorio:** no existe.
- [ ] **Código + reporte del modelo de IR:** no existe.
- [ ] **Funciones manuales de Rocchio y BM25:** no existen.
- [ ] **Cuadro + gráfico de entrevistas vinculadas a libros:** no existen.
- [ ] **Informe final integrador con evaluación crítica:** no existe.

### Detalle por actividad

1. **Extracción y preparación:** el script define una morfología de unidad razonable para libros: párrafos reconstruidos, títulos/subtítulos, testimonios delimitados por `« »`, notas al pie y contexto editorial. La relación con parte/capítulo se resuelve por página y archivo de índice ([segmentacion_libros.py](segmentacion_libros.py#L311-L365)). Falta explicar y aplicar una morfología equivalente para entrevistas.
2. **Exploración:** no hay estadísticas de longitud, diversidad léxica, frecuencias, nubes ni comparación conjunta.
3. **IR:** no hay TF-IDF ni cosine similarity, ni una relación explícita entrevista-documento-libro.
4. **Relevancia:** no hay código de Rocchio ni BM25. El requisito de implementación manual no puede satisfacerse usando solo una librería externa; tampoco hay explicación o comparación de resultados.
5. **Comparación:** no hay selección de temas similares, ranking por libro o heatmap legible.
6. **Informe:** el README documenta exclusivamente el extractor y sus limitaciones; no integra análisis exploratorio, IR, evaluación ni conclusiones.

## Lo que ya está bien hecho

- Existe una separación clara entre PDFs fuente, índices editoriales y salidas en `corpus/`.
- El extractor no hace una extracción plana: usa estructura tipográfica y geometría para reconstruir bloques, distingue títulos y subtítulos, y conserva contexto editorial ([README.md](README.md#L17-L39)).
- La salida está estructurada y es utilizable como base para indexación: cada unidad conserva libro, parte, capítulo, título, subtítulo, flags de relato/nota y texto.
- La segmentación trata explícitamente testimonios multilínea y notas al pie; además, el script registra conteos de unidades, relatos y notas ([segmentacion_libros.py](segmentacion_libros.py#L368-L399)).
- Las limitaciones conocidas están documentadas en vez de quedar ocultas: testimonios sin guillemets, acoplamiento a fuentes tipográficas y guiones de corte de línea ([README.md](README.md#L86-L93)).
- Los nueve corpus existentes tienen estructura homogénea y los nombres de libro coinciden con sus archivos de salida, lo que deja una base concreta para continuar.

## Plan de trabajo priorizado

### Bloque 1 — Hacer reproducible la base

1. Confirmar e instalar, con autorización, la dependencia necesaria para PyMuPDF; después ejecutar el extractor en un directorio de trabajo controlado.
2. Eliminar o versionar salidas anteriores antes de regenerar, y registrar libros fallidos en un manifiesto.
3. Medir cobertura de segmentación: unidades por libro, testimonios capturados, notas, textos vacíos, guiones de corte y testimonios sin delimitadores.
4. Exportar explícitamente corpus raw y corpus preprocesado, incluyendo también las entrevistas.

### Bloque 2 — Cumplir el núcleo del taller

1. Definir la unidad documental y el protocolo de limpieza común para libros y entrevistas.
2. Añadir exploración para ambos corpus: longitud, diversidad, frecuencias, nubes y comparación léxica.
3. Implementar TF-IDF y similitud entre cada entrevista y las unidades/libros, guardando rankings reproducibles.
4. Escribir funciones propias de Rocchio y Okapi BM25, documentar la fórmula y comparar sus resultados bajo el mismo conjunto de consultas.
5. Crear el cuadro de vínculos entrevista-libro y un heatmap reducido/legible, justificando selección, orden y cualquier umbral.

### Bloque 3 — Cerrar evidencia e informe

1. Evaluar sensibilidad a longitud, normalización, tokenización y umbrales; separar corpus de referencia y consultas cuando corresponda.
2. Cruzar todas las cifras del informe con archivos exportados y salidas reproducibles.
3. Elaborar el informe final con extracción, exploración, modelo IR, evaluación de Rocchio/BM25, comparación, limitaciones, conclusiones y mejoras.
