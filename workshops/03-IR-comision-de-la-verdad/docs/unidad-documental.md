# Unidad documental de recuperación

## Decisión

El sistema tendrá dos lados explícitos:

- **Documentos recuperables:** cada unidad segmentada de los libros CEV. Una
  unidad puede ser un párrafo narrativo, un testimonio delimitado, un título o
  una nota al pie, según el campo `pie_de_pagina`/`es_relato` del corpus.
- **Consultas:** cada **pasaje** de entrevista. Un pasaje es un grupo de turnos
  consecutivos del testigo, agrupados hasta ~150 palabras
  (`segmentacion_entrevistas.py`). El puntaje de una entrevista frente a una
  unidad es el **máximo** sobre sus pasajes.

> **Corrección (2026-09-10).** La versión anterior de este documento afirmaba
> que las entrevistas no se dividían por turnos "porque el JSON disponible no
> trae intervenciones, hablantes ni marcas de diálogo confiables". Es falso: las
> transcripciones marcan el hablante al inicio de línea (`TEST:`, `ENT:`,
> `ENT1:`, `INF2:`) y 2.457 de las 2.486 entrevistas las traen, con ~282 turnos
> cada una. La entrevista completa como consulta hacía colapsar el ranking
> (ver 6.4 de [bitacora-taller.md](bitacora-taller.md)); los pasajes lo
> resuelven.

La salida deberá conservar el `id` estable y los metadatos del libro para que
los rankings posteriores puedan agregarse por libro, capítulo o parte sin
perder la evidencia de la unidad que produjo la coincidencia.

## Justificación cuantitativa

Los diez corpus de libros contienen **56.495 unidades**. Su longitud media es
de **40,0 palabras** y la mediana es de **18 palabras** (palabras separadas por
espacio sobre el texto crudo de la unidad). El corpus de entrevistas contiene
**2.486 registros**; 2.484 tienen texto y su longitud media es de **14.331
palabras**, con mediana de **11.768 palabras**.

Estas escalas son muy distintas, y esa diferencia resultó ser decisiva. Tratar
cada libro completo como documento mezclaría muchos temas y ocultaría
coincidencias locales, así que se conserva el detalle segmentado de los libros.
Pero usar la entrevista completa como consulta —200 veces más larga que una
unidad— hace que la consulta cubra 1.128 de los 17.497 términos del vocabulario
y se parezca un poco a todo: el ranking colapsa y devuelve casi las mismas
unidades a todas las entrevistas. Con diez tomos el efecto es extremo: una sola
unidad —la más larga del índice— gana 2.334 de las 2.484 entrevistas.

Por eso la consulta es el **pasaje**: 161.636 pasajes con mediana de 57 tokens
preprocesados, frente a unidades de mediana 13. La relación de longitudes pasa
de ~200× a ~4×, y las unidades distintas en el top-1 pasan de 117 a 1.801 sobre
2.484 entrevistas.

Los métodos de IR posteriores deben reportar cómo agregan las unidades
ganadoras al nivel de libro.

## Limitaciones y contrato para el equipo

- `libro:<nombre>:<posición>` identifica una unidad de libro.
- `entrevista:<id_doc>` identifica una entrevista.
- `pasaje:<id_doc>:<índice>` identifica un pasaje de entrevista; su campo
  `entrevista` apunta al id de la entrevista a la que pertenece.
- La indexación excluye las notas al pie, las unidades de menos de 2 tokens y
  los pasajes de menos de 5: todas siguen en el corpus, solo no se indexan.
- El archivo de entrevistas solo contiene `id_doc`, `pages` y `text`; no hay
  fecha ni persona explícitas.
- El campo `es_relato` **no es homogéneo**: en nueve tomos marca testimonios
  delimitados por `« »` y en `CUANDO_LOS_PAJAROS_NO_CANTABAN`, unidades bajo
  subtítulo de testimonio. Ver 4.2.2 y 6.9 de [bitacora-taller.md](bitacora-taller.md).
- El nombre del libro de una unidad es el **nombre de su archivo** en `corpus/`,
  no el campo `libro` del registro, que puede venir con extensión.
- El preprocesamiento es el mismo para ambos tipos: minúsculas, eliminación de
  puntuación, eliminación de stopwords españolas y lematización con
  `es_core_news_md`.
- Las métricas de la siguiente fase deben indicar si comparan entrevistas
  completas contra unidades individuales o si agregan puntuaciones por libro.
- El preprocesamiento conserva unidades sin términos (`texto_preprocesado` vacío)
  para mantener trazabilidad. La indexación debe excluirlas, no borrarlas del
  raw ni del archivo preprocesado.