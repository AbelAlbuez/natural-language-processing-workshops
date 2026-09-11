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
- `data/analisis_exploratorio.json`: estadísticas descriptivas, diversidad
  léxica y ajustes de la ley de Zipf por corpus.
- `figuras/zipf_*.png`: distribuciones rango-frecuencia en log-log.
- `figuras/longitud_documentos.png`, `figuras/top_terminos.png`,
  `figuras/nube_*.png`: longitud de documento, ranking de términos y nubes.
- `docs/bitacora-taller.md`: bitácora ordenada de pasos, decisiones y cifras;
  es el borrador del informe final.
- `docs/unidad-documental.md`: decisión y contrato de la unidad de recuperación.
- `preprocesar_corpus.py`: pipeline común de exportación.
- `analisis_exploratorio.py`: análisis exploratorio (actividad 2 del taller).

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

La ejecución validada produjo **55.579 documentos**: 53.093 unidades de libro y
2.486 entrevistas. Los dos archivos tienen exactamente el mismo conjunto de
IDs. Hay **366 entradas** cuyo `texto_preprocesado` queda vacío (364 de libros y
2 de entrevistas): unidades formadas solo por stopwords, marcadores o contenido
editorial sin términos, y 256 notas al pie cuyo texto era únicamente una URL
(el preprocesamiento las elimina, el corpus raw las conserva). Se conservan en ambos archivos
para no perder trazabilidad; los índices de la siguiente fase deben excluirlas
del cálculo de puntuaciones y conservar su `id` para auditoría.

## Cómo regenerar

El entorno recomendado es `.venv` dentro de la carpeta del taller, con las
dependencias de `requirements.txt`:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download es_core_news_md
.venv/bin/python preprocesar_corpus.py
```

El script requiere `PyMuPDF` solo para regenerar la segmentación desde PDF y
requiere `spacy` con el modelo `es_core_news_md` para el preprocesamiento. La
ejecución del preprocesador no modifica los JSON originales de `corpus/`; crea
o reemplaza atómicamente los dos archivos de `data/`.

`entrevistas_all_2023-03-21_14-24_05.json` es un dato de entrada del taller y
**no está versionado**: hay que copiarlo a la carpeta del taller o a `corpus/`
—el preprocesador busca en ambas— o indicar su ubicación con
`--entrevistas RUTA`. `corpus/` contiene únicamente los nueve libros
segmentados; el archivo de entrevistas que se deje ahí se reconoce como
entrevistas, no como un libro más. Sin él, el preprocesador se detiene con un
mensaje explícito. Para avanzar solo con los libros:

```bash
.venv/bin/python preprocesar_corpus.py --sin-entrevistas
```

Esa corrida marca los tres archivos de `data/` con `entrevistas_incluidas:
false`; el corpus queda incompleto y no sirve para la comparación
entrevista-libro que pide el taller.

Para regenerar primero los libros, con los PDFs e índices presentes:

```bash
.venv/bin/python segmentacion_libros.py
```

Ese comando reemplaza cada JSON únicamente después de completar su generación.
Si un libro falla, elimina el JSON anterior de ese libro y registra el error en
`corpus/_manifiesto.json`, evitando confundir una salida vieja con una nueva.

## Análisis exploratorio

Con los dos archivos de `data/` ya generados:

```bash
.venv/bin/python analisis_exploratorio.py
```

Calcula, para libros y entrevistas por separado y sobre el texto crudo y el
preprocesado: tokens, vocabulario, TTR, hapax, longitud de documento, términos
más frecuentes y el exponente de la ley de Zipf (ajuste log-log por mínimos
cuadrados, completo y en la banda de rangos 10–1000). Escribe
`data/analisis_exploratorio.json` y seis figuras en `figuras/`.

Las figuras de contenido (nubes y ranking de términos) excluyen el **ruido de
formato**: etiquetas de hablante de las transcripciones (`TEST`, `ENT`, `ENT1`),
marcas entre corchetes (`[INTERRUP]`, `[INAD]`, `[CONT]`, `[DUD]`), restos de
URL de las notas al pie y tokens numéricos. Pesan 11,0 % de los tokens
preprocesados de las entrevistas y 6,8 % de los de los libros. La
exclusión es solo para graficar: el JSON conserva el ranking completo y el
detalle de lo excluido en `ruido_de_formato`.

## Unidad documental

La decisión detallada está en [unidad-documental.md](unidad-documental.md).
En resumen: cada unidad segmentada de libro es recuperable y cada entrevista
completa funciona como consulta. El equipo debe agregar los resultados al nivel
de libro cuando necesite construir el cuadro entrevista-libro.