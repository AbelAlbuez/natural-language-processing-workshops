# Unidad documental de recuperación

## Decisión

El sistema tendrá dos lados explícitos:

- **Documentos recuperables:** cada unidad segmentada de los libros CEV. Una
  unidad puede ser un párrafo narrativo, un testimonio delimitado, un título o
  una nota al pie, según el campo `pie_de_pagina`/`es_relato` del corpus.
- **Consultas:** cada entrevista completa del archivo de entrevistas. No se
  divide por turnos porque el JSON disponible no trae intervenciones, hablantes
  ni marcas de diálogo confiables.

La salida deberá conservar el `id` estable y los metadatos del libro para que
los rankings posteriores puedan agregarse por libro, capítulo o parte sin
perder la evidencia de la unidad que produjo la coincidencia.

## Justificación cuantitativa

Los nueve corpus de libros contienen **54.686 unidades**. Su longitud media es
de aproximadamente **65 palabras** y la mediana es de **46 palabras**. El
corpus de entrevistas contiene **2.486 registros**; 2.484 tienen texto y su
longitud media es de aproximadamente **14.300 palabras**, con mediana de
**11.731 palabras**.

Estas escalas son muy distintas. Tratar cada libro completo como documento
mezclaría muchos temas y ocultaría coincidencias locales; tratar una entrevista
completa como unidad de libro produciría documentos no comparables y muy pocos
resultados interpretables. Por eso se conserva el detalle segmentado de los
libros y la entrevista completa como consulta contextual. Los métodos de IR
posteriores deben reportar cómo agregan las unidades ganadoras al nivel de
libro.

## Limitaciones y contrato para el equipo

- `libro:<nombre>:<posición>` identifica una unidad de libro.
- `entrevista:<id_doc>` identifica una entrevista.
- El archivo de entrevistas solo contiene `id_doc`, `pages` y `text`; no hay
  fecha ni persona explícitas.
- El preprocesamiento es el mismo para ambos tipos: minúsculas, eliminación de
  puntuación, eliminación de stopwords españolas y lematización con
  `es_core_news_md`.
- Las métricas de la siguiente fase deben indicar si comparan entrevistas
  completas contra unidades individuales o si agregan puntuaciones por libro.
- El preprocesamiento conserva unidades sin términos (`texto_preprocesado` vacío)
  para mantener trazabilidad. La indexación debe excluirlas, no borrarlas del
  raw ni del archivo preprocesado.