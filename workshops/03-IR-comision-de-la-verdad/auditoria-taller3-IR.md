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

## Avance 2 — puntos 2-3 (Juan y Jesús)

**Fecha de auditoría:** 2026-09-11
**Modo:** solo lectura y diagnóstico. No se modificaron el código de Juan y Jesús ni `docs/bitacora-taller.md`.

### Inventario frente al Bloque 1

Desde la auditoría anterior aparecieron:

- `preprocesar_corpus.py`, `analisis_exploratorio.py`, `modelo_ir.py`, `segmentacion_entrevistas.py` y `vocabulario.py`.
- `data/corpus_raw.json`, `data/corpus_preprocesado.json` y `data/estadisticas_preprocesamiento.json`.
- Seis figuras PNG: longitud, dos nubes, top de términos y dos gráficos de Zipf.
- `docs/bitacora-taller.md` y `docs/unidad-documental.md`.
- El corpus de entrevistas está presente localmente como `entrevistas_all_2023-03-21_14-24_05.json`, pero aparece sin seguimiento en Git y no forma parte de una base reproducible versionada.

El historial Git muestra una secuencia coherente de cambios para preparación del corpus, análisis exploratorio, TF-IDF, segmentación de entrevistas e integración del décimo tomo. El estado de trabajo tiene un único archivo sin seguimiento: el JSON grande de entrevistas. La bitácora registra primero una cadena de 55.579 documentos y después una de 58.981; el último total sí coincide con los archivos actuales.

### Qué afirma la bitácora y qué se verificó

La bitácora afirma que las entrevistas son consultas y las unidades de libro documentos; que se conservaron IDs `libro:...` y `entrevista:...`; que se generaron corpus raw y preprocesado; que el preprocesamiento aplica tokenización, minúsculas, stopwords de spaCy y lematización; y que se conservaron los documentos vacíos para auditoría. Estas afirmaciones tienen correspondencia en `preprocesar_corpus.py` y en los dos JSON: hay 58.981 documentos, 56.495 de libros y 2.486 entrevistas, sin IDs duplicados ni diferencias entre raw y preprocesado.

También se verifican en el código las decisiones de `modelo_ir.py`: TF-IDF propio con `tf=1+log(f)`, IDF suavizado, vocabulario calculado solo sobre libros, exclusión de notas al pie, `min_df=2`, normalización configurable y agregación de las mejores unidades por libro. `analisis_exploratorio.py` implementa longitud, vocabulario, TTR, hapax, frecuencias, Zipf, solapamiento léxico y nubes para ambos tipos de corpus. `vocabulario.py` centraliza el filtro de ruido de formato.

La bitácora además afirma ejecuciones completas, cifras de ranking, experimentos de normalización, segmentación de entrevistas en pasajes y validación cualitativa. Esas afirmaciones no se pueden confirmar en el estado actual porque no existen `data/ranking_tfidf*.json`, `data/analisis_exploratorio.json` ni `data/corpus_pasajes.json`. Por tanto, el código que produciría esos artefactos existe, pero los resultados reportados no están actualmente disponibles como salidas reproducibles.

### Veredicto por requisito

| Punto | Estado | Evidencia y reserva |
|---|---|---|
| 2. Análisis exploratorio | ⚠️ Cumple con reservas | `analisis_exploratorio.py` calcula estadísticas para libros y entrevistas, genera las seis figuras presentes y calcula el solapamiento léxico/Jaccard entre vocabularios. Las nubes y gráficos están separados por corpus, pero no hay una figura explícita de patrones léxicos comparados más allá del solapamiento y los gráficos de Zipf. Además, falta `data/analisis_exploratorio.json`, aunque el script lo declara como salida; las cifras de la bitácora no pueden auditarse desde un artefacto numérico actual. |
| 3. Modelo de recuperación TF-IDF | ⚠️ Cumple con reservas | `modelo_ir.py` contiene vectorización TF-IDF ejecutable, producto disperso para similitud coseno, ranking por entrevista/unidad, agregación por libro y diagnóstico. Conserva los IDs y el fragmento crudo de evidencia. Sin embargo, no hay ningún ranking guardado actualmente y tampoco está `corpus_pasajes.json`; por eso no se puede verificar hoy la ejecución, el ejemplo cualitativo ni los números de la bitácora. |

### Punto 2 — evidencia y riesgos

- **Ambos corpus:** `analisis_exploratorio.py` usa `TIPOS = ("libro", "entrevista")` y calcula longitud, vocabulario, TTR, hapax, frecuencias y Zipf para cada tipo, tanto crudo como preprocesado.
- **Nubes:** existen `figuras/nube_libros.png` y `figuras/nube_entrevistas.png`; el código usa `figura_nube` para cada tipo.
- **Comparación:** `comparar_vocabularios` calcula vocabulario compartido, Jaccard y vocabularios exclusivos. Esto es una comparación explícita, pero limitada a solapamiento léxico; no constituye todavía una comparación interpretativa de patrones o temas.
- **Trazabilidad del Bloque 1:** `preprocesar_corpus.py` consume los JSON de `corpus/` y el archivo de entrevistas, y produce los dos corpus de `data/`. No se observó un pipeline alternativo que sustituya el corpus preprocesado. La trazabilidad por IDs se conserva.
- **Cifra vigente:** el preprocesado actual contiene 379 documentos vacíos, 377 de libros y 2 entrevistas, no 188. La bitácora tiene cifras de distintas ejecuciones; debe distinguirse explícitamente qué ejecución produjo cada tabla.

### Punto 3 — evidencia y riesgos

- **TF-IDF real:** `modelo_ir.py` implementa `construir_vocabulario`, `matriz_tfidf`, `normalizar` y el cálculo de similitudes por multiplicación de matrices dispersas. No es solo una mención documental.
- **Ranking:** la función principal construye resultados por entrevista y conserva `id`, libro, parte, capítulo, `es_relato`, número de tokens y fragmento. La salida se escribiría en `data/ranking_tfidf*.json`, pero ninguno de esos archivos existe ahora.
- **IDs:** `preprocesar_corpus.py` conserva el ID de cada unidad y crea IDs de entrevista; `modelo_ir.py` los copia al ranking. La implementación, por tanto, sí preserva la trazabilidad, aunque no hay ranking persistido para inspeccionarla en resultados.
- **Documentos vacíos:** la lógica de `modelo_ir.py` no vectoriza unidades de libro con menos de dos tokens; las entrevistas sin términos se excluyen de las consultas. Las notas al pie se excluyen antes de construir el vocabulario. Esto cubre los 188 vacíos de la ejecución actual, aunque la bitácora reporta otra ejecución con 379 vacíos. Debe guardarse el manifiesto de descartes junto al ranking.
- **Asimetría de longitud:** la bitácora sí detecta el problema y prueba normalización de potencia y pasajes. La solución que presenta como elegida es `--consultas pasajes`, con una relación aproximada de 4×. Pero al no existir `data/corpus_pasajes.json` ni su ranking, la mitigación no está disponible ni reproducible en el estado actual. La línea base de entrevista completa sigue siendo vulnerable al colapso descrito por la propia bitácora.
- **Validación cualitativa:** la bitácora incluye ejemplos de coincidencias textuales y umbrales, pero esos ejemplos viven solo en la documentación. Sin ranking ni pasajes guardados no se pueden volver a inspeccionar automáticamente.

### Bugs bloqueantes y riesgos técnicos

1. **Bloqueante de reproducibilidad:** faltan las salidas que sostienen las afirmaciones centrales del punto 3: rankings TF-IDF y corpus de pasajes. Un tercero puede leer el código, pero no revisar los top-k ni reproducir las cifras reportadas sin volver a disponer del JSON de entrevistas y ejecutar la cadena completa.
2. **Salida exploratoria ausente:** `analisis_exploratorio.py` declara `data/analisis_exploratorio.json`, pero ese archivo no está en `data/`. Las figuras existen, pero no basta para recalcular cifras exactas, filtros y conteos.
3. **Bitácora no alineada con una única ejecución:** el registro cronológico conserva cifras antiguas y nuevas, entre ellas 55.579/58.981 documentos, 160.934/161.636 pasajes y distintos conteos de top-1. Esto no es necesariamente un bug del código, pero sí un riesgo documental: cada tabla debe indicar el archivo y la configuración exacta que la produjo.
4. **Filtro de ruido no demostrable desde los datos:** `vocabulario.py` y `modelo_ir.py` sí contienen `es_ruido_de_formato`, pero los JSON actuales no guardan una marca por token ni un resumen del vocabulario final. El ranking faltante impide confirmar que la ejecución reportada aplicó exactamente ese filtro.
5. **Dependencia local no versionada:** el JSON de entrevistas es requerido para reconstruir raw, preprocesado y ranking, pero está sin seguimiento en Git. La bitácora explica la decisión por su tamaño, aunque falta un mecanismo verificable de obtención o un hash/versionado externo documentado.

No se encontraron errores de sintaxis en los scripts Python. Las rutas principales se derivan de `Path(__file__).resolve().parent`, lo que evita rutas absolutas del equipo; el punto débil de reproducibilidad es la ausencia de entradas/salidas versionadas y la dependencia del modelo `es_core_news_md`, cuya versión debe quedar fijada en el entorno.

### Qué está listo para el punto 4

Está lista la base conceptual y de código para reutilizar documentos, IDs, TF-IDF e IDF. También está documentada una hipótesis útil: comparar BM25 y Rocchio contra la configuración de pasajes, no contra la línea base colapsada de entrevistas completas. No está listo todavía un resultado confiable sobre el cual comparar, porque falta regenerar y conservar `corpus_pasajes.json` y el ranking TF-IDF elegido.

Para cerrar los puntos 2 y 3 al 100% faltan:

- regenerar y guardar el JSON numérico del análisis exploratorio, o ajustar la documentación para referenciar una salida existente;
- conservar el archivo de entrevistas mediante un procedimiento reproducible y un hash;
- generar `data/corpus_pasajes.json` y el ranking TF-IDF de pasajes con su configuración, conteos de descartes y diagnóstico;
- revisar al menos una entrevista completa con sus top-k unidades y libros, guardando la evidencia que sustenta la validación cualitativa;
- consolidar las cifras de la bitácora para una sola ejecución y separar claramente línea base, potencia y pasajes;
- mostrar una comparación léxica más explícita entre libros y entrevistas, además del Jaccard, si el enunciado se interpreta como comparación de patrones y no solo de vocabulario.

### Próximos pasos sugeridos

1. Fijar la entrada de entrevistas con hash, modelo spaCy y versión de dependencias; regenerar raw, preprocesado y estadísticas.
2. Ejecutar el análisis exploratorio y conservar su JSON junto a las figuras; actualizar las cifras de la bitácora a esa ejecución.
3. Generar pasajes y el ranking TF-IDF de pasajes, comprobar exclusión de vacíos/notas y revisar manualmente varios top-k con sus IDs.
4. Declarar esa salida como línea base del punto 4 y comparar BM25 y Rocchio sobre las mismas consultas, documentos y métricas de diagnóstico.
5. Solo después construir el cuadro y heatmap de la actividad 5; de lo contrario, el error de longitud del ranking se propagará a la comparación de corpus.

## Avance 3 — cierre de pendientes (puntos 2-3)

**Fecha:** 2026-09-11

La cadena se regeneró desde el corpus actual mediante `preprocesar_corpus.py`,
`analisis_exploratorio.py`, `segmentacion_entrevistas.py` y
`modelo_ir.py --consultas pasajes`. La regeneración previa había usado JSON
derivados antiguos de 57.172 documentos; después del preprocesamiento completo
el corpus vigente contiene 58.981 documentos: 56.495 unidades de libro y 2.486
entrevistas.

| Punto | Estado | Evidencia actual |
|---|---|---|
| 2. Análisis exploratorio | ✅ Cumple | `data/analisis_exploratorio.json` existe y contiene estadísticas para libros y entrevistas; las seis figuras también fueron regeneradas. La comparación explícita disponible es léxica (frecuencias, Zipf y vocabulario compartido/Jaccard). |
| 3. Modelo de recuperación TF-IDF | ✅ Cumple con alcance documentado | `data/ranking_tfidf.json` existe, es JSON válido, contiene 2.484 entrevistas, top-20 por consulta, IDs `entrevista:` y `libro:`, y diagnóstico persistido. El resultado oficial usa pasajes y L2×L2; no se conserva una variante sin normalizar. |

El ranking oficial no es la línea base de entrevistas completas: usa
`data/corpus_pasajes.json`, 161.636 pasajes, máximo por unidad de libro entre
los pasajes de cada entrevista, `min_df=2`, y normalización L2 en ambos lados.
La decisión está justificada por la prueba de cinco entrevistas: sin
normalización cambiaron 4/5 puestos en una y 5/5 en las otras cuatro, con
dominancia de unidades largas. El archivo persistido guarda `k=20`.

Los artefactos actuales fueron validados el 2026-09-11:

- `data/analisis_exploratorio.json`: 14.114 bytes.
- `data/corpus_pasajes.json`: 146.013.275 bytes.
- `data/ranking_tfidf.json`: 48.653.428 bytes.

**¿Puede el equipo comenzar hoy el punto 4 sobre este ranking? Sí.** El punto
3 queda listo como línea base reproducible para Rocchio y BM25, siempre que se
mantengan la misma unidad de consulta (pasajes), los mismos documentos,
parámetros e IDs. Rocchio todavía debe declararse como retroalimentación de
pseudo-relevancia porque no existen juicios de relevancia manuales.

Pendientes que permanecen abiertos: el salto histórico de 188 a 379 documentos
vacíos no puede descomponerse por completo porque los JSON anteriores no están
versionados; solo está demostrada la adición de 1.809 unidades del décimo tomo.
Además, la comparación del punto 2 sigue siendo principalmente léxica y no una
evaluación temática con juicios humanos. Ninguno de esos pendientes impide
iniciar la implementación manual de Rocchio y BM25 sobre el ranking fijado.

## Cierre del taller

**Fecha:** 2026-09-11

| Actividad | Estado | Evidencia final |
|---|---|---|
| 1. Extracción y preparación del corpus | ✅ Cumple con reservas documentadas | `corpus/*.json`, `data/corpus_raw.json`, `data/corpus_preprocesado.json` y `data/estadisticas_preprocesamiento.json`. La reserva es que la entrada de entrevistas se obtiene localmente y el salto histórico de 188 a 379 vacíos no puede reconstruirse por completo desde Git. |
| 2. Análisis exploratorio | ✅ Cumple | `analisis_exploratorio.py`, `data/analisis_exploratorio.json` y seis figuras en `figuras/`, con estadísticas para libros y entrevistas. |
| 3. Modelo TF-IDF | ✅ Cumple | `modelo_ir.py` y `data/ranking_tfidf.json`, con pasajes, L2×L2, `k=20`, IDs trazables y 41.034 documentos indexables. |
| 4. Rocchio y Okapi BM25 | ✅ Cumple con reserva metodológica | `modelos_relevancia.py`, `data/ranking_rocchio.json`, `data/ranking_bm25.json` y `data/comparacion_metricas.*`. Las implementaciones son manuales, pero no hay juicios humanos y Rocchio usa pseudo-relevancia. |
| 5. Comparación de corpus y heatmap | ✅ Cumple | `comparacion_corpus.py`, `data/cuadro_vinculos.json` y `figuras/heatmap_vinculos_tfidf.png`, agregados al nivel de libro para 2.484 entrevistas y 10 libros. |
| 6. Informe final | ✅ Cumple con limitaciones explícitas | `informe-taller3-IR.md` integra preparación, exploración, TF-IDF, Rocchio, BM25, cuadro, heatmap, limitaciones y conclusiones. |

### Checklist de entregables

1. **Corpus extraído y preprocesado:** listo en `corpus/`, `data/corpus_raw.json` y `data/corpus_preprocesado.json`.
2. **Informe de análisis exploratorio:** listo en `data/analisis_exploratorio.json` y las figuras de `figuras/`.
3. **Código y reporte del modelo IR:** listos en `modelo_ir.py`, `data/ranking_tfidf.json` e `informe-taller3-IR.md`.
4. **Funciones manuales de Rocchio y BM25:** listas en `modelos_relevancia.py`, con salidas separadas y comparación en `data/comparacion_metricas.json` y `data/comparacion_metricas.md`.
5. **Cuadro y gráfico de entrevistas vinculadas a libros:** listos en `data/cuadro_vinculos.json` y `figuras/heatmap_vinculos_tfidf.png`.
6. **Informe final integrador:** listo en `informe-taller3-IR.md`.

Antes de entregar solo quedan pendientes metodológicos, ya declarados en el
informe: anotar relevancia humana para medir precisión/recall, calibrar los
parámetros de Rocchio y BM25 con esa evaluación y explicar históricamente con
mayor detalle el salto de 188 a 379 documentos vacíos. No queda pendiente
técnico bloqueante para entregar la cadena reproducible actual.
