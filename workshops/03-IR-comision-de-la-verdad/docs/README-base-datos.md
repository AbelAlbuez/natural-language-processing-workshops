# Base de datos reproducible

## Archivos

Desde esta carpeta del taller:

- `corpus/*.json`: unidades segmentadas de los diez libros CEV.
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
- `data/corpus_pasajes.json`: las entrevistas partidas en 161.636 pasajes por
  turnos de hablante, con su texto preprocesado.
- `data/ranking_tfidf.json`: ranking oficial por pasajes, con las 20 unidades
  de libro más similares por entrevista, fragmento de evidencia y puntaje
  agregado por libro. Usa TF-IDF con normalización L2 en consultas y
  documentos, equivalente a similitud coseno. No se conserva una variante sin
  normalizar.

`CUANDO_LOS_PAJAROS_NO_CANTABAN` llegó ya segmentado y sin PDF: no se regenera
con `segmentacion_libros.py` y no está en su lista `LIBROS`. Su campo `libro`
trae la extensión `.pdf` y no tiene `id`; el preprocesador toma el nombre del
archivo, así que los ids salen igual que los del resto.
- `docs/bitacora-taller.md`: bitácora ordenada de pasos, decisiones y cifras;
  es el borrador del informe final.
- `docs/unidad-documental.md`: decisión y contrato de la unidad de recuperación.
- `preprocesar_corpus.py`: pipeline común de exportación.
- `analisis_exploratorio.py`: análisis exploratorio (actividad 2 del taller).
- `modelo_ir.py`: índice TF-IDF y ranking entrevista → unidades de libro
  (actividad 3); escribe `data/ranking_tfidf.json`.
- `vocabulario.py`: regla única de ruido de formato, compartida por el análisis
  y el índice.
- `segmentacion_entrevistas.py`: parte las entrevistas en pasajes por turnos de
  hablante, que son las consultas del modelo.

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

La ejecución validada produjo **58.981 documentos**: 56.495 unidades de libro y
2.486 entrevistas. Los dos archivos tienen exactamente el mismo conjunto de
IDs. Hay **379 entradas** cuyo `texto_preprocesado` queda vacío (377 de libros y
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
`--entrevistas RUTA`. `corpus/` contiene únicamente los diez libros
segmentados; el archivo de entrevistas que se deje ahí se reconoce como
entrevistas, no como un libro más. Sin él, el preprocesador se detiene con un
mensaje explícito. Para avanzar solo con los libros:

El archivo esperado mide 231.409.620 bytes y su SHA-256 de referencia es
`32bcc2cf100cf2873cf87d9897a308451a472d73a762a4293ed08adc7689afdf`. Debe
obtenerse por el canal de entrega del curso; GitHub no admite este blob de más
de 100 MB. Verifícalo antes de procesar con:

```bash
shasum -a 256 entrevistas_all_2023-03-21_14-24-05.json
```

Si el hash no coincide, no mezcles esa entrada con los JSON derivados: las
cifras y los IDs podrían cambiar.

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
preprocesados de las entrevistas y 6,4 % de los de los libros. La
exclusión es solo para graficar: el JSON conserva el ranking completo y el
detalle de lo excluido en `ruido_de_formato`.

## Unidad documental

La decisión detallada está en [unidad-documental.md](unidad-documental.md).
En resumen: cada unidad segmentada de libro es recuperable y cada entrevista
completa funciona como consulta. El equipo debe agregar los resultados al nivel
de libro cuando necesite construir el cuadro entrevista-libro.

## Artefactos reproducibles de los puntos 2 y 3

El 2026-09-11 se regeneró la cadena completa con la entrada de entrevistas
verificada y el décimo tomo presente en `corpus/`:

```bash
.venv/bin/python preprocesar_corpus.py
.venv/bin/python analisis_exploratorio.py
.venv/bin/python segmentacion_entrevistas.py
.venv/bin/python modelo_ir.py --consultas pasajes
```

La primera orden es necesaria para que `data/` incorpore las 3.402 unidades de
`CUANDO_LOS_PAJAROS_NO_CANTABAN`. La ejecución actual contiene 58.981
documentos, 56.495 unidades de libro, 2.486 entrevistas y 379 documentos
vacíos tras el preprocesamiento.

El ranking oficial usa L2 en consultas y documentos, equivalente a similitud
coseno, y conserva `k=20` unidades por entrevista en `data/ranking_tfidf.json`.
No se conserva una variante sin normalizar: en una prueba de cinco entrevistas
quitando la normalización cambiaron 4 de 5 puestos en una y 5 de 5 puestos en
las otras cuatro, con dominancia de unidades largas.

Artefactos generados el 2026-09-11 (hora local):

| Archivo | Tamaño | Contenido |
|---|---:|---|
| `data/analisis_exploratorio.json` | 14.114 bytes | Estadísticas de libros y entrevistas |
| `data/corpus_pasajes.json` | 146.013.275 bytes | 161.636 pasajes de 2.486 entrevistas |
| `data/ranking_tfidf.json` | 48.653.428 bytes | 2.484 entrevistas con top-20 |

Los tres archivos son JSON válidos y se regeneran con los comandos anteriores,
sin pasos manuales ocultos aparte de disponer del archivo de entrevistas y del
modelo spaCy `es_core_news_md`. El salto histórico de 188 a 379 documentos
vacíos sigue sin poder descomponerse completamente porque los JSON anteriores
no están versionados; sí queda confirmado que los 1.809 documentos adicionales
provienen del décimo tomo.