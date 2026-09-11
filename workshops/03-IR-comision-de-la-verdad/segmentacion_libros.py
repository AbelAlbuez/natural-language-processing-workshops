"""
Extractor de corpus CEV (v2).

Segmenta el texto de un libro en unidades:
    {id, libro, parte, capitulo, titulo, subtitulo, es_relato, pie_de_pagina, texto}

El `id` es `libro:<nombre>:<posicion>` con la posición de la unidad dentro del
libro en seis dígitos; es estable mientras no cambie la segmentación y permite
rastrear una unidad desde el corpus preprocesado o desde los resultados de
recuperación hasta este archivo.

NOVEDADES DE ESTA VERSIÓN
- Las notas al pie ya NO se descartan: se segmentan como unidades propias con
  pie_de_pagina=true (es_relato siempre false para estas).
- Umbral de palabras para es_relato bajado de 30 a 15.
- Corrige la letra capitular ("dropcap", ej. la "L" grande de "La mañana...")
  que antes se perdía por tener un tamaño de fuente mucho mayor al del cuerpo.
- Reconstruye las palabras partidas por el guion de corte de línea del PDF
  ("significa-" + "dos" -> "significados"), ver unir_linea().
- título/subtítulo/capítulo/parte comparten la familia de fuente "Futura" pero
  en tamaños distintos: >=20pt es encabezado de PARTE o CAPÍTULO (se descarta,
  porque esos vienen del indice.json), >=15pt y <20pt es TÍTULO, y por debajo
  de 15pt es SUBTÍTULO. Validado con datos reales del libro.

REGLAS QUE SE MANTIENEN
- Los párrafos de cuerpo se detectan por sangría de primera línea, de forma
  continua a través de saltos de página.
- Un bloque delimitado por « ... » se marca es_relato=True si supera el
  umbral de palabras. Un « » al INICIO de un párrafo no cierra el relato
  (es continuación de un relato multi-párrafo).
- parte/capitulo se resuelven con una tabla de rangos de página (indice.json).

LIMITACIÓN CONOCIDA (no cubierta por esta versión)
- Se detectó al menos un testimonio presentado como bloque de cita indentado
  SIN comillas « », en un tamaño de fuente distinto al cuerpo (10.0pt) en vez
  de con guillemets (ej. la carta de Daniela Narváez, pág. 53 del libro).
  Como no está delimitado por « », esta versión NO lo captura como relato y
  lo descarta igual que el resto de texto que no matchea ninguna firma
  conocida. Si te interesa capturarlo, hay que agregar esa firma (tamaño
  10.0, mismo font que el cuerpo) como una categoría adicional de "relato
  sin comillas" — decime si quieres que lo agregue.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

BASE_DIR = Path(__file__).resolve().parent
DIR_CONTENIDO = BASE_DIR / "Libros_CEV" / "contenido"
DIR_INDICES = BASE_DIR / "Libros_CEV" / "indices"
DIR_CORPUS = BASE_DIR / "corpus"

# Un nombre por libro: define las tres rutas
#   Libros_CEV/contenido/<nombre>.pdf
#   Libros_CEV/indices/<nombre>.json
#   corpus/<nombre>.json
LIBROS = [
    "SUFRIR_LA_GUERRA_Y_REHACER_LA_VIDA",
    "CONVOCATORIA_A_LA_PAZ_GRANDE",
    "HALLAZGOS_Y_RECOMENDACIONES",
    "HASTA_LA_GUERRA_TIENE_LIMITES",
    "LA_COLOMBIA_FUERA_DE_COLOMBIA",
    "MI_CUERPO_ES_LA_VERDAD",
    "NO_ES_UN_MAL_MENOR",
    "NO_MATARAS",
    "RESISTIR_NO_ES_AGUANTAR",
]

CONFIG = {
    "fuente_cuerpo": "AGaramondPro-Regular",
    "tamano_cuerpo_min": 10.5,
    "tamano_cuerpo_max": 11.5,
    "fuente_titulo_prefijo": "Futura",
    "tamano_titulo_min": 15.0,   # Futura >= esto (y < tamano_parte_min) => "titulo"
    "tamano_parte_min": 20.0,    # Futura >= esto => encabezado de parte/capítulo (se descarta)
    "tamano_pie_contenido": 9.0,
    "tamano_pie_marcador_max": 7.5,
    "umbral_palabras_relato": 15,
    "comilla_apertura": "«",
    "comilla_cierre": "»",
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
    """'cuerpo' | 'titulo' | 'subtitulo' | 'pie_inicio' | 'pie_continuacion' | None."""
    texto_cuerpo, texto_pie = "", ""
    x0 = None
    tamano_titulo_detectado = None
    tiene_marcador_pie, tiene_contenido_pie = False, False
    marcador_antes_del_contenido = False
    es_encabezado_parte = False

    for span in spans:
        texto = span["text"]
        texto_strip = texto.strip()
        fuente = span["font"]
        tamano = round(span["size"], 1)
        if not texto_strip:
            continue

        es_dropcap = len(texto_strip) == 1 and texto_strip.isalpha() and tamano > CONFIG["tamano_cuerpo_max"]
        es_cuerpo = (
            fuente == CONFIG["fuente_cuerpo"]
            and CONFIG["tamano_cuerpo_min"] <= tamano <= CONFIG["tamano_cuerpo_max"]
        ) or es_dropcap
        es_futura = fuente.startswith(CONFIG["fuente_titulo_prefijo"])
        es_marcador_pie = texto_strip.isdigit() and tamano < CONFIG["tamano_pie_marcador_max"]
        es_contenido_pie = tamano == CONFIG["tamano_pie_contenido"] and not texto_strip.isdigit()

        if es_cuerpo:
            texto_cuerpo += texto
            if x0 is None:
                x0 = span["bbox"][0]
        elif es_futura:
            if tamano >= CONFIG["tamano_parte_min"]:
                es_encabezado_parte = True
            else:
                texto_cuerpo += texto
                tamano_titulo_detectado = tamano
        elif es_marcador_pie:
            if tiene_contenido_pie:
                marcador_antes_del_contenido = False  # el marcador vino DESPUÉS de contenido: no es inicio real
            elif not tiene_marcador_pie:
                marcador_antes_del_contenido = True
            tiene_marcador_pie = True
        elif es_contenido_pie:
            tiene_contenido_pie = True
            texto_pie += texto

    if es_encabezado_parte:
        return {"tipo": "parte_capitulo", "texto": "", "x0": None}
    if tamano_titulo_detectado is not None:
        tipo = "titulo" if tamano_titulo_detectado >= CONFIG["tamano_titulo_min"] else "subtitulo"
        return {"tipo": tipo, "texto": texto_cuerpo.strip(), "x0": x0}
    if texto_cuerpo.strip():
        return {"tipo": "cuerpo", "texto": texto_cuerpo.strip(), "x0": x0}
    if tiene_marcador_pie and marcador_antes_del_contenido:
        return {"tipo": "pie_inicio", "texto": texto_pie.strip(), "x0": None}
    if tiene_contenido_pie:
        return {"tipo": "pie_continuacion", "texto": texto_pie.strip(), "x0": None}
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
                if clasificada["tipo"] != "parte_capitulo" and not clasificada["texto"]:
                    continue
                clasificada["pagina_impresa"] = pagina_impresa
                lineas.append(clasificada)
    doc.close()
    return lineas


GUION_SUAVE = "\u00ad"  # soft hyphen: invisible, pero parte la palabra al tokenizar
GUIONES_DE_CORTE = ("-", GUION_SUAVE)


def limpiar_guiones_suaves(texto):
    """Quita los guiones suaves que quedan dentro de una palabra.

    No son visibles pero no son caracteres de palabra, así que sin esto
    "huma\u00adnidades" se tokeniza como "huma" + "nidades"."""
    return texto.replace(GUION_SUAVE, "") if texto else texto


def unir_linea(acumulado, linea):
    """Pega una línea nueva al bloque que se está armando.

    El PDF parte palabras con guion al final de la línea ("significa-" +
    "dos"). Si no se reconstruyen, el índice termina con fragmentos como
    "significa" y "dos" en lugar de "significados" — y aparecen tokens
    inexistentes ("huma" de "huma- nos") entre los términos frecuentes.

    Solo se une cuando la línea siguiente arranca en minúscula: un guion
    seguido de mayúscula o de dígito no es corte silábico. La contrapartida
    conocida es que una palabra compuesta partida justo en su propio guion
    ("político-" + "militar") pierde el guion; en una muestra de 25
    ocurrencias reales del corpus, las 25 eran cortes silábicos.
    """
    acumulado, linea = acumulado.rstrip(), linea.lstrip()
    if acumulado.endswith(GUIONES_DE_CORTE) and linea[:1].islower():
        return acumulado[:-1] + linea
    return acumulado + " " + linea


def unir_partes(partes):
    """unir_linea aplicada en cadena: un relato puede abarcar varios bloques y
    el corte silábico también ocurre en la frontera entre ellos."""
    texto = partes[0]
    for parte in partes[1:]:
        texto = unir_linea(texto, parte)
    return texto


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
    lineas_de_gracia = 0  # suprime el corte por sangría justo después de un título (por letra capitular)

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

            # una palabra partida por guion no puede empezar un párrafo nuevo:
            # la sangría que disparó el corte es un falso positivo
            if (
                es_nuevo
                and actual is not None
                and actual["tipo"] == "cuerpo"
                and actual["texto"].rstrip().endswith(GUIONES_DE_CORTE)
                and l["texto"][:1].islower()
            ):
                es_nuevo = False

            if es_nuevo:
                if actual:
                    bloques.append(actual)
                actual = {"tipo": "cuerpo", "texto": l["texto"], "pagina_impresa": l["pagina_impresa"]}
            elif len(actual["texto"]) == 1 and actual["texto"].isalpha():
                actual["texto"] += l["texto"]  # letra capitular pegada a la palabra siguiente
            else:
                actual["texto"] = unir_linea(actual["texto"], l["texto"])

        elif tipo in ("titulo", "subtitulo"):
            es_nuevo = actual is None or actual["tipo"] != tipo
            if es_nuevo:
                if actual:
                    bloques.append(actual)
                actual = {"tipo": tipo, "texto": l["texto"], "pagina_impresa": l["pagina_impresa"]}
            else:
                actual["texto"] = unir_linea(actual["texto"], l["texto"])
            lineas_de_gracia = 4  # el párrafo que sigue a un título puede abrir con letra capitular

        elif tipo == "parte_capitulo":
            lineas_de_gracia = 4  # el párrafo que sigue puede abrir con letra capitular

        elif tipo == "pie_inicio":
            if actual:
                bloques.append(actual)
            actual = {"tipo": "pie", "texto": l["texto"], "pagina_impresa": l["pagina_impresa"]}

        elif tipo == "pie_continuacion":
            if actual and actual["tipo"] == "pie":
                actual["texto"] = unir_linea(actual["texto"], l["texto"])
            # si no hay una nota abierta, este texto tamaño-nota sin marcador
            # es probablemente una leyenda de foto (misma fuente/tamaño) — se descarta

    if actual:
        bloques.append(actual)
    return bloques


def segmentar(bloques):
    ap, ci = CONFIG["comilla_apertura"], CONFIG["comilla_cierre"]
    umbral = CONFIG["umbral_palabras_relato"]

    unidades = []
    titulo_actual, subtitulo_actual = None, None
    estado, buffer_relato, pagina_inicio_relato = "narrativa", [], None

    def emitir(texto, es_relato, pagina, pie_de_pagina=False):
        texto = texto.strip().lstrip(",;: ").strip()
        if unidades and not any(c.isalnum() for c in texto):
            unidades[-1]["texto"] = unidades[-1]["texto"].rstrip() + texto
            return
        unidades.append({
            "titulo": titulo_actual, "subtitulo": subtitulo_actual,
            "es_relato": es_relato, "pie_de_pagina": pie_de_pagina,
            "texto": texto, "pagina_impresa": pagina,
        })

    def cerrar_relato():
        nonlocal buffer_relato, estado
        texto_relato = unir_partes(buffer_relato).strip()
        emitir(texto_relato, len(texto_relato.split()) > umbral, pagina_inicio_relato)
        buffer_relato = []
        estado = "narrativa"

    for b in bloques:
        if b["tipo"] == "titulo":
            if estado == "relato":
                cerrar_relato()
            titulo_actual, subtitulo_actual = b["texto"], None
            continue
        if b["tipo"] == "subtitulo":
            if estado == "relato":
                cerrar_relato()
            subtitulo_actual = b["texto"]
            continue
        if b["tipo"] == "pie":
            emitir(b["texto"], False, b["pagina_impresa"], pie_de_pagina=True)
            continue

        texto = b["texto"]

        if estado == "narrativa":
            if ap not in texto:
                emitir(texto, False, b["pagina_impresa"])
                continue

            idx = texto.index(ap)
            antes = texto[:idx].strip()
            if antes:
                emitir(antes, False, b["pagina_impresa"])

            resto = texto[idx:]
            pos_cierre = resto.find(ci, 1)
            if pos_cierre != -1:
                bloque = resto[:pos_cierre + 1]
                emitir(bloque, len(bloque.split()) > umbral, b["pagina_impresa"])
                sobra = resto[pos_cierre + 1:].strip()
                if sobra:
                    emitir(sobra, False, b["pagina_impresa"])
            else:
                buffer_relato = [resto]
                pagina_inicio_relato = b["pagina_impresa"]
                estado = "relato"

        elif estado == "relato":
            texto_l = texto.lstrip()
            if texto_l.startswith(ci):
                buffer_relato.append(texto_l[1:])
                continue

            if ci in texto:
                pos = texto.index(ci)
                buffer_relato.append(texto[:pos + 1])
                cerrar_relato()
                sobra = texto[pos + 1:].strip()
                if sobra:
                    emitir(sobra, False, b["pagina_impresa"])
            else:
                buffer_relato.append(texto)

    if estado == "relato" and buffer_relato:
        cerrar_relato()

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
    for posicion, u in enumerate(unidades):
        parte, capitulo = (
            resolver_parte_capitulo(u["pagina_impresa"], tabla_indice)
            if tabla_indice else (None, None)
        )
        corpus.append({
            "id": f"libro:{libro}:{posicion:06d}",
            "libro": libro,
            "parte": parte,
            "capitulo": capitulo,
            "titulo": limpiar_guiones_suaves(u["titulo"]),
            "subtitulo": limpiar_guiones_suaves(u["subtitulo"]),
            "es_relato": u["es_relato"],
            "pie_de_pagina": u["pie_de_pagina"],
            "texto": limpiar_guiones_suaves(u["texto"]),
        })
    return corpus


def procesar_libro(nombre):
    """Procesa un libro de la lista y devuelve (unidades, relatos, pies)."""
    pdf_path = DIR_CONTENIDO / f"{nombre}.pdf"
    indice_path = DIR_INDICES / f"{nombre}.json"
    salida_path = DIR_CORPUS / f"{nombre}.json"

    if not pdf_path.exists():
        raise FileNotFoundError(f"No existe el PDF: {pdf_path}")
    if not indice_path.exists():
        print(f"  [aviso] sin índice ({indice_path.name}): parte/capitulo quedarán en null")
        indice_path = None

    corpus = construir_corpus(str(pdf_path), nombre, str(indice_path) if indice_path else None)

    salida_path.parent.mkdir(parents=True, exist_ok=True)
    salida_temporal = salida_path.with_suffix(".json.tmp")
    with open(salida_temporal, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
    salida_temporal.replace(salida_path)

    n_relatos = sum(1 for u in corpus if u["es_relato"])
    n_pies = sum(1 for u in corpus if u["pie_de_pagina"])
    print(f"  Unidades totales: {len(corpus)}")
    print(f"  Relatos (es_relato=True): {n_relatos}")
    print(f"  Notas al pie (pie_de_pagina=True): {n_pies}")
    print(f"  Guardado en: {salida_path}")
    return len(corpus), n_relatos, n_pies


if __name__ == "__main__":
    total_unidades = total_relatos = total_pies = 0
    fallidos = []
    manifiesto = {
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "libros": {},
    }

    for i, nombre in enumerate(LIBROS, 1):
        print(f"[{i}/{len(LIBROS)}] {nombre}")
        try:
            unidades, relatos, pies = procesar_libro(nombre)
            manifiesto["libros"][nombre] = {
                "estado": "ok",
                "archivo": f"{nombre}.json",
                "unidades": unidades,
                "relatos": relatos,
                "notas_al_pie": pies,
            }
        except Exception as e:  # un libro roto no debe detener el lote
            print(f"  [error] {e}")
            salida_fallida = DIR_CORPUS / f"{nombre}.json"
            if salida_fallida.exists():
                salida_fallida.unlink()
            manifiesto["libros"][nombre] = {
                "estado": "fallido",
                "archivo": None,
                "error": f"{type(e).__name__}: {e}",
            }
            fallidos.append(nombre)
            continue
        total_unidades += unidades
        total_relatos += relatos
        total_pies += pies

    print("\n=== Resumen ===")
    print(f"Libros procesados: {len(LIBROS) - len(fallidos)}/{len(LIBROS)}")
    print(f"Unidades totales: {total_unidades}")
    print(f"Relatos (es_relato=True): {total_relatos}")
    print(f"Notas al pie (pie_de_pagina=True): {total_pies}")
    if fallidos:
        print("Fallidos: " + ", ".join(fallidos))

    manifiesto_path = DIR_CORPUS / "_manifiesto.json"
    manifiesto_temporal = manifiesto_path.with_suffix(".json.tmp")
    with open(manifiesto_temporal, "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, ensure_ascii=False, indent=2)
    manifiesto_temporal.replace(manifiesto_path)
    print(f"Manifiesto: {manifiesto_path}")