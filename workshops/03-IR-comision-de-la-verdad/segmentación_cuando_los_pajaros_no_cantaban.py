"""
Extractor de corpus — variante título/subtítulo (para libros como
"Cuando los pájaros no cantaban" que NO usan « » para marcar relatos).

Segmenta el texto en unidades:
    {libro, parte, capitulo, titulo, subtitulo, es_relato, pie_de_pagina, texto}

REGLA DE ESTE FORMATO (distinta a extraer_corpus.py)
- NO se buscan comillas « ». En su lugar:
  - El texto que aparece bajo un TÍTULO, antes de que aparezca cualquier
    SUBTÍTULO, es introducción: es_relato = False.
  - El texto que aparece bajo un SUBTÍTULO es el relato en sí: es_relato = True.
  - Al aparecer un nuevo TÍTULO, se reinicia el subtítulo vigente (se vuelve
    a modo "introducción" hasta el siguiente subtítulo).
- pie_de_pagina siempre False — este libro no tiene notas al pie. Se deja el
  campo por consistencia con el resto del corpus.
- parte/capitulo se resuelven con indice.json, igual que en extraer_corpus.py.

FIRMA TIPOGRÁFICA (validada con datos reales del libro)
- Cuerpo: AGaramondPro-Regular / AGaramondPro-Italic, 11.0pt
- Letra capitular: AGaramondPro-Regular, >11.5pt, un solo carácter (se corrige)
- Subtítulo: FuturaBT-Bold, <15pt (ej. 13.0)
- Título: FuturaBT-Bold, 15–24.9pt (ej. 24.0)
- Encabezado de capítulo: FuturaBT-Bold, 25–29.9pt (se descarta, viene del índice)
- Encabezado de parte: FuturaBT-Bold, >=30pt (se descarta, viene del índice)
- Cualquier tamaño 9.0 puro-dígito es número de página (se descarta)
- La línea "Introducción a El libro de..." usa AGaramondPro-Semibold, una
  fuente distinta a la del cuerpo y a la de título/subtítulo — no matchea
  ninguna categoría y se descarta (su contenido ya queda reflejado en el
  campo `capitulo` del indice.json).

AJUSTA los tamaños en CONFIG si otro libro con este mismo formato usa una
firma tipográfica distinta — valida siempre con inspeccionar_fuentes.py primero.
"""

import argparse
import json

import fitz  # PyMuPDF

CONFIG = {
    "fuentes_cuerpo": ("AGaramondPro-Regular", "AGaramondPro-Italic"),
    "tamano_cuerpo_min": 10.5,
    "tamano_cuerpo_max": 11.5,
    "fuente_titulo_prefijo": "Futura",
    "tamano_subtitulo_max": 15.0,   # Futura < esto => "subtitulo"
    "tamano_titulo_min": 15.0,      # Futura en [titulo_min, capitulo_min) => "titulo"
    "tamano_capitulo_min": 25.0,    # Futura en [capitulo_min, parte_min) => encabezado de capítulo (se descarta)
    "tamano_parte_min": 30.0,       # Futura >= esto => encabezado de parte (se descarta)
    "indent_umbral_puntos": 8.0,
}


def detectar_pagina_impresa(page):
    data = page.get_text("dict")
    alto_pagina = page.rect.height
    candidatos = []
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                texto = span["text"].strip()
                if texto.isdigit() and span["bbox"][1] > alto_pagina * 0.85:
                    candidatos.append((span["bbox"][1], int(texto)))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: -c[0])
    return candidatos[0][1]


def clasificar_linea(spans):
    """'cuerpo' | 'titulo' | 'subtitulo' | 'capitulo_o_parte' | None."""
    texto_cuerpo = ""
    x0 = None
    tamano_futura_detectado = None

    for span in spans:
        texto = span["text"]
        texto_strip = texto.strip()
        fuente = span["font"]
        tamano = round(span["size"], 1)
        if not texto_strip:
            continue

        es_dropcap = len(texto_strip) == 1 and texto_strip.isalpha() and tamano > CONFIG["tamano_cuerpo_max"]
        es_cuerpo = (
            fuente in CONFIG["fuentes_cuerpo"]
            and CONFIG["tamano_cuerpo_min"] <= tamano <= CONFIG["tamano_cuerpo_max"]
        ) or es_dropcap
        es_futura = fuente.startswith(CONFIG["fuente_titulo_prefijo"])

        if es_cuerpo:
            texto_cuerpo += texto
            if x0 is None:
                x0 = span["bbox"][0]
        elif es_futura:
            texto_cuerpo += texto
            tamano_futura_detectado = tamano
        # cualquier otra cosa (encabezado corrido, num. de página, línea
        # "Introducción a..." en AGaramondPro-Semibold) se descarta

    if tamano_futura_detectado is not None:
        t = tamano_futura_detectado
        if t >= CONFIG["tamano_parte_min"] or t >= CONFIG["tamano_capitulo_min"]:
            return {"tipo": "capitulo_o_parte", "texto": "", "x0": None}
        if t >= CONFIG["tamano_titulo_min"]:
            return {"tipo": "titulo", "texto": texto_cuerpo.strip(), "x0": x0}
        return {"tipo": "subtitulo", "texto": texto_cuerpo.strip(), "x0": x0}
    if texto_cuerpo.strip():
        return {"tipo": "cuerpo", "texto": texto_cuerpo.strip(), "x0": x0}
    return None


def extraer_lineas(pdf_path):
    doc = fitz.open(pdf_path)
    lineas = []
    for num_pagina, page in enumerate(doc):
        pagina_impresa = detectar_pagina_impresa(page) or (num_pagina + 1)
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                clasificada = clasificar_linea(line.get("spans", []))
                if clasificada is None:
                    continue
                if clasificada["tipo"] != "capitulo_o_parte" and not clasificada["texto"]:
                    continue
                clasificada["pagina_impresa"] = pagina_impresa
                lineas.append(clasificada)
    doc.close()
    return lineas


def agrupar_en_bloques(lineas):
    if not lineas:
        return []

    margenes_por_pagina = {}
    for l in lineas:
        if l["tipo"] == "cuerpo":
            pag = l["pagina_impresa"]
            margenes_por_pagina[pag] = min(margenes_por_pagina.get(pag, l["x0"]), l["x0"])

    bloques = []
    actual = None
    lineas_de_gracia = 0  # suprime el corte por sangría tras un encabezado (letra capitular)

    for l in lineas:
        tipo = l["tipo"]

        if tipo == "cuerpo":
            margen = margenes_por_pagina.get(l["pagina_impresa"], l["x0"])
            indentada = (l["x0"] - margen) > CONFIG["indent_umbral_puntos"]

            if lineas_de_gracia > 0:
                es_nuevo = actual is None or actual["tipo"] != "cuerpo"
                lineas_de_gracia -= 1
            else:
                es_nuevo = actual is None or actual["tipo"] != "cuerpo" or indentada

            if es_nuevo:
                if actual:
                    bloques.append(actual)
                actual = {"tipo": "cuerpo", "texto": l["texto"], "pagina_impresa": l["pagina_impresa"]}
            elif len(actual["texto"]) == 1 and actual["texto"].isalpha():
                actual["texto"] += l["texto"]
            else:
                actual["texto"] += " " + l["texto"]

        elif tipo in ("titulo", "subtitulo"):
            es_nuevo = actual is None or actual["tipo"] != tipo
            if es_nuevo:
                if actual:
                    bloques.append(actual)
                actual = {"tipo": tipo, "texto": l["texto"], "pagina_impresa": l["pagina_impresa"]}
            else:
                actual["texto"] += " " + l["texto"]
            lineas_de_gracia = 4

        elif tipo == "capitulo_o_parte":
            lineas_de_gracia = 4

    if actual:
        bloques.append(actual)
    return bloques


def segmentar(bloques):
    unidades = []
    titulo_actual, subtitulo_actual = None, None

    for b in bloques:
        if b["tipo"] == "titulo":
            titulo_actual = b["texto"]
            subtitulo_actual = None  # vuelve a modo introducción
            continue
        if b["tipo"] == "subtitulo":
            subtitulo_actual = b["texto"]
            continue

        # tipo == "cuerpo"
        es_relato = subtitulo_actual is not None
        unidades.append({
            "titulo": titulo_actual,
            "subtitulo": subtitulo_actual,
            "es_relato": es_relato,
            "pie_de_pagina": False,
            "texto": b["texto"].strip(),
            "pagina_impresa": b["pagina_impresa"],
        })

    return unidades


def cargar_indice(path):
    with open(path, encoding="utf-8") as f:
        tabla = json.load(f)
    return sorted(tabla, key=lambda n: n["pagina_inicio"])


def resolver_parte_capitulo(pagina_impresa, tabla):
    parte, capitulo = None, None
    for nodo in tabla:
        if nodo["pagina_inicio"] > pagina_impresa:
            break
        parte = nodo.get("parte", parte)
        capitulo = nodo.get("capitulo", capitulo)
    return parte, capitulo


def construir_corpus(pdf_path, libro, indice_path):
    lineas = extraer_lineas(pdf_path)
    bloques = agrupar_en_bloques(lineas)
    unidades = segmentar(bloques)
    tabla_indice = cargar_indice(indice_path) if indice_path else []

    corpus = []
    for u in unidades:
        parte, capitulo = (
            resolver_parte_capitulo(u["pagina_impresa"], tabla_indice)
            if tabla_indice else (None, None)
        )
        corpus.append({
            "libro": libro,
            "parte": parte,
            "capitulo": capitulo,
            "titulo": u["titulo"],
            "subtitulo": u["subtitulo"],
            "es_relato": u["es_relato"],
            "pie_de_pagina": u["pie_de_pagina"],
            "texto": u["texto"],
        })
    return corpus


if __name__ == "__main__":
    nombre = "CUANDO_LOS_PAJAROS_NO_CANTABAN"
    corpus = construir_corpus(f"Libros_CEV/contenido/{nombre}.pdf", nombre, f"Libros_CEV/indices/{nombre}.json")

    with open(f"corpus/{nombre}2.json", "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)

    n_relatos = sum(1 for u in corpus if u["es_relato"])
    print(f"Unidades totales: {len(corpus)}")
    print(f"Relatos (es_relato=True): {n_relatos}")
    print(f"Guardado en: corpus/{nombre}.json")