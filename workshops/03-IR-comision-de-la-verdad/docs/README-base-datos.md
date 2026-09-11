# Base de datos reproducible

## Archivos

Desde esta carpeta del taller:

- `corpus/*.json`: unidades segmentadas de los nueve libros CEV.
- `corpus/_manifiesto.json`: estado de la última segmentación, con éxitos,
  errores y conteos por libro.
- `entrevistas_all_2023-03-21_14-24_05.json`: corpus de entrevistas original.
- `data/corpus_raw.json`: unión normalizada de libros y entrevistas, sin limpiar.
- `data/corpus_preprocesado.json`: unión con el texto lematizado y la misma
  identidad de cada documento.
- `docs/unidad-documental.md`: decisión y contrato de la unidad de recuperación.
- `preprocesar_corpus.py`: pipeline común de exportación.

## Esquemas

El archivo de entrevistas original es una lista de **2.486** objetos con:

```json
{
  "id_doc": "...",
  "pages": 123,
  "text": "..."
}
```

No contiene campos explícitos de fecha o persona. Un ejemplo representativo
se conserva por estructura, no por contenido completo, en `data/corpus_raw.json`:

```json
{
  "id": "entrevista:<id_doc>",
  "tipo": "entrevista",
  "texto": "<contenido completo de text>",
  "metadatos": {
    "id_doc": "<id_doc>",
    "pages": 123,
    "origen": "entrevistas_all_2023-03-21_14-24_05.json",
    "posicion_origen": 0
  }
}
```

Cada unidad de libro sigue el mismo contrato, pero `tipo` vale `libro` y sus
metadatos incluyen libro, parte, capítulo, título, subtítulo, flags de relato y
nota al pie, archivo de origen y posición original.

En el archivo preprocesado, cada entrada conserva `id`, `tipo`, `metadatos` y
`texto_preprocesado`. Por tanto, el vínculo con el raw no depende del orden de
las listas.

La ejecución validada produjo **57.172 documentos**: 54.686 unidades de libro y
2.486 entrevistas. Los dos archivos tienen exactamente el mismo conjunto de
IDs. Hay **188 entradas** cuyo `texto_preprocesado` queda vacío (186 de libros y
2 de entrevistas), principalmente unidades formadas solo por stopwords,
marcadores o contenido editorial sin términos. Se conservan en ambos archivos
para no perder trazabilidad; los índices de la siguiente fase deben excluirlas
del cálculo de puntuaciones y conservar su `id` para auditoría.

## Cómo regenerar

El entorno recomendado es `.venv` dentro de la carpeta del taller:

```bash
.venv/bin/python preprocesar_corpus.py
```

El script requiere `PyMuPDF` solo para regenerar la segmentación desde PDF y
requiere `spacy` con el modelo `es_core_news_md` para el preprocesamiento. La
ejecución del preprocesador no modifica los JSON originales de `corpus/`; crea
o reemplaza atómicamente los dos archivos de `data/`.

Para regenerar primero los libros, con los PDFs e índices presentes:

```bash
.venv/bin/python segmentacion_libros.py
```

Ese comando reemplaza cada JSON únicamente después de completar su generación.
Si un libro falla, elimina el JSON anterior de ese libro y registra el error en
`corpus/_manifiesto.json`, evitando confundir una salida vieja con una nueva.

## Unidad documental

La decisión detallada está en [unidad-documental.md](unidad-documental.md).
En resumen: cada unidad segmentada de libro es recuperable y cada entrevista
completa funciona como consulta. El equipo debe agregar los resultados al nivel
de libro cuando necesite construir el cuadro entrevista-libro.