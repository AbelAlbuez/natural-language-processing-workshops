# Taller 3 — Recuperacion de informacion sobre el Informe Final de la CEV

Este taller trabaja sobre los tomos del Informe Final de la Comision para el
Esclarecimiento de la Verdad (CEV). El punto de partida es construir un corpus
estructurado a partir de los PDF publicados, para poder indexarlo y consultarlo
despues.

## `segmentacion_libros.py`

Convierte cada tomo en PDF en un JSON de **unidades de texto** listas para
indexar. No es una extraccion plana de texto: reconstruye la estructura
editorial del libro (parte, capitulo, titulo, subtitulo), separa los
**testimonios** del texto narrativo de la Comision y conserva las notas al pie
como unidades propias.

### Que produce

Un arreglo JSON donde cada elemento es una unidad de texto:

```json
{
  "libro": "NO_MATARAS",
  "parte": "Antecedentes historicos (1920-1958)",
  "capitulo": "1. El miedo al comunismo",
  "titulo": "La violencia bipartidista",
  "subtitulo": null,
  "es_relato": true,
  "pie_de_pagina": false,
  "texto": "«Mi papa fue asesinado esa noche...»"
}
```

| Campo | Significado |
|---|---|
| `libro` | Nombre del archivo procesado (la entrada de la lista `LIBROS`) |
| `parte` / `capitulo` | Se resuelven por numero de pagina contra el indice del libro |
| `titulo` / `subtitulo` | Encabezados internos vigentes en ese punto del texto |
| `es_relato` | `true` si la unidad es un testimonio (texto entre `«` y `»` con mas de 15 palabras) |
| `pie_de_pagina` | `true` si la unidad proviene de una nota al pie |
| `texto` | El contenido, con los saltos de linea del PDF ya unidos |

### Estructura de archivos

El script deriva las tres rutas de un solo nombre, el que aparece en la lista
`LIBROS` al inicio del archivo:

```
03-IR-comision-de-la-verdad/
├── Libros_CEV/
│   ├── contenido/<nombre>.pdf      entrada: el tomo en PDF
│   └── indices/<nombre>.json       entrada: tabla de partes/capitulos por pagina
├── corpus/<nombre>.json            salida: el corpus segmentado
└── segmentacion_libros.py
```

Para agregar un tomo basta con dejar el PDF y su indice con el mismo nombre en
las carpetas correspondientes y añadir ese nombre a `LIBROS`.

El indice es una lista ordenada de puntos de inicio; cada nodo aplica desde su
`pagina_inicio` hasta el siguiente:

```json
[
  {"pagina_inicio": 23, "parte": null, "capitulo": "Introduccion"},
  {"pagina_inicio": 33, "parte": "Antecedentes historicos (1920-1958)", "capitulo": null}
]
```

Si falta el indice de un libro, el script avisa y lo procesa igual, dejando
`parte` y `capitulo` en `null`.

### Como funciona

El PDF no trae marcado semantico, asi que la estructura se infiere de la
tipografia y la geometria de cada linea (via PyMuPDF). El pipeline tiene cuatro
etapas:

1. **`extraer_lineas`** — recorre pagina por pagina y clasifica cada linea segun
   la fuente y el tamaño de sus spans: cuerpo (AGaramond 10.5–11.5pt), titulo
   (Futura 15–20pt), subtitulo (Futura <15pt), encabezado de parte/capitulo
   (Futura ≥20pt, que se descarta porque esa informacion viene del indice), o
   nota al pie (9pt, con marcador numerico <7.5pt). Ademas detecta el numero de
   **pagina impresa** —el del pie de pagina, no el indice del PDF— porque es el
   que usa el indice.
2. **`agrupar_en_bloques`** — reconstruye los parrafos. Un parrafo nuevo se
   detecta por la sangria de primera linea, comparada contra el margen minimo de
   esa pagina, lo que permite que un parrafo continue a traves de un salto de
   pagina. Incluye tres ajustes: las **letras capitulares** (la letra grande que
   abre un parrafo) se reintegran a su palabra, tras un titulo hay unas lineas
   de gracia para que la capitular no dispare un corte falso, y las palabras
   partidas por **guion de corte de linea** se reconstruyen (`unir_linea`), lo
   que ademas descarta el corte de parrafo cuando la sangria era un falso
   positivo a mitad de palabra.
3. **`segmentar`** — separa narrativa de testimonio. Un bloque delimitado por
   `« ... »` se emite como unidad aparte y se marca `es_relato=true` si supera
   las 15 palabras. Los relatos que abarcan varios parrafos se acumulan: un `»`
   al inicio de parrafo se entiende como continuacion, no como cierre. Los
   titulos y subtitulos vistos en el camino quedan como contexto de las unidades
   que siguen.
4. **`construir_corpus`** — cruza cada unidad con el indice por numero de pagina
   para asignarle `parte` y `capitulo`.

Los umbrales tipograficos estan todos en el diccionario `CONFIG`, al inicio del
archivo. Fueron calibrados con la diagramacion de estos tomos; si se procesa un
libro con otra diagramacion, es lo primero que hay que revisar.

### Uso

```bash
pip install -r requirements.txt   # solo necesita pymupdf para este script
python segmentacion_libros.py
```

No recibe argumentos: itera sobre `LIBROS` y escribe un JSON por libro en
`corpus/`. Imprime el conteo de unidades, relatos y notas al pie de cada tomo y
un resumen final. Si un libro falla, lo reporta y continua con los demas.

### Limitaciones conocidas

- **Testimonios sin guillemets.** Algunos testimonios aparecen como bloque de
  cita indentado en 10pt, sin `« »` (por ejemplo la carta de Daniela Narvaez,
  pag. 53 de *Sufrir la guerra y rehacer la vida*). Al no estar delimitados, no
  se capturan como relato y se descartan.
- **Fuentes acopladas al diseño.** La clasificacion depende de nombres de fuente
  concretos (`AGaramondPro-Regular`, `Futura`). Un tomo diagramado distinto
  requiere ajustar `CONFIG`.
- **Guiones de corte de linea.** Resueltos: `unir_linea` reconstruye la palabra
  partida (`significa-` + `dos` -> `significados`), incluye el guion suave
  (U+00AD) e impide que una palabra cortada abra un parrafo nuevo. Quedan 13
  casos sin unir de 8.780, todos guiones legitimos (rangos, codigos, nombres
  compuestos).
