"""Análisis exploratorio del corpus del Taller 3 (actividad 2 del enunciado).

Cubre la parte de **frecuencia de términos y diversidad léxica**:

- Distribución rango-frecuencia (ley de Zipf) en escala log-log, para libros y
  entrevistas por separado, sobre el texto crudo y sobre el preprocesado.
- Ajuste del exponente de Zipf por mínimos cuadrados sobre log10(rango) vs
  log10(frecuencia), con su R².
- Vocabulario, TTR (type-token ratio), hapax legomena y longitud de documento.
- Solapamiento de vocabulario entre los dos corpus.
- Nubes de palabras y ranking de términos más frecuentes por corpus.
- Distribución de la longitud de los documentos.

Por qué se mide sobre las dos versiones del texto: la ley de Zipf se enuncia
sobre el texto tal cual, y el preprocesamiento le corta la cabeza a la
distribución (las stopwords son justamente los rangos más altos) y le fusiona
la cola (la lematización colapsa formas en un mismo lema). Reportar solo la
versión preprocesada daría un exponente que no es comparable con la literatura;
reportar solo la cruda no diría nada sobre el corpus que realmente se va a
indexar. Las dos juntas además sirven para decidir el corte de términos raros
al construir el índice TF-IDF de la actividad 3.

Entradas (las genera preprocesar_corpus.py):
    data/corpus_raw.json
    data/corpus_preprocesado.json

Salidas:
    data/analisis_exploratorio.json
    figuras/zipf_preprocesado.png
    figuras/zipf_crudo_vs_preprocesado.png
    figuras/longitud_documentos.png
    figuras/top_terminos.png
    figuras/nube_libros.png
    figuras/nube_entrevistas.png

Uso:
    .venv/bin/python analisis_exploratorio.py
    .venv/bin/python analisis_exploratorio.py --sin-figuras --top 50
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # el script corre sin display

import matplotlib.pyplot as plt
import numpy as np
from wordcloud import WordCloud

from vocabulario import ABREVIATURAS_TRANSCRIPCION, RUIDO_WEB, es_ruido_de_formato

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_PATH = DATA_DIR / "corpus_raw.json"
PREPROCESSED_PATH = DATA_DIR / "corpus_preprocesado.json"
SALIDA_PATH = DATA_DIR / "analisis_exploratorio.json"
DIR_FIGURAS = ROOT / "figuras"

TIPOS = ("libro", "entrevista")
ETIQUETAS = {"libro": "Libros CEV", "entrevista": "Entrevistas"}
VERSIONES = ("crudo", "preprocesado")

# Banda de rangos para el segundo ajuste. La cabeza (rangos 1-9) y la cola de
# hapax se desvían sistemáticamente de la recta; el tramo central es donde la
# ley de potencias se sostiene, así que se reporta el ajuste completo y este.
BANDA_AJUSTE = (10, 1000)

TOP_TERMINOS_POR_DEFECTO = 30
TOP_TERMINOS_EN_FIGURA = 15
PALABRAS_EN_NUBE = 120

# Las convenciones de transcripción y el resto del ruido de formato están en
# vocabulario.py, compartidas con el índice de recuperación.

# Paleta categórica validada (checks de CVD y contraste en modo claro).
COLOR_SERIE = {
    "libro": "#2a78d6",
    "entrevista": "#eb6834",
    "crudo": "#2a78d6",
    "preprocesado": "#eb6834",
}
# Rampa secuencial (un solo tono, claro->oscuro) para las nubes: en una nube el
# color codifica magnitud, no identidad.
RAMPA_SECUENCIAL = {"libro": "Blues", "entrevista": "Oranges"}
TINTA_PRIMARIA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
SUPERFICIE = "#fcfcfb"


# Mismo patrón que preprocesar_corpus.PATRON_URL: si el conteo crudo incluyera
# los fragmentos de URL y el preprocesado no, las dos columnas no serían
# comparables.
PATRON_URL = re.compile(r"https?://\S+|www\.\S+", flags=re.IGNORECASE)


def tokenizar(texto):
    """Misma regla que preprocesar_corpus.tokenizar_para_indice, más el filtro
    alfabético que ese módulo aplica al contar tokens originales."""
    return [
        palabra
        for palabra in re.findall(r"\b\w+\b", PATRON_URL.sub(" ", texto).lower(), flags=re.UNICODE)
        if palabra.isalpha()
    ]


def contar_corpus(documentos, campo, tokenizador):
    """Frecuencias de término y longitudes por documento, por tipo de corpus."""
    frecuencias = {tipo: Counter() for tipo in TIPOS}
    longitudes = {tipo: [] for tipo in TIPOS}
    for documento in documentos:
        tipo = documento["tipo"]
        if tipo not in frecuencias:
            continue
        tokens = tokenizador(documento[campo])
        frecuencias[tipo].update(tokens)
        longitudes[tipo].append(len(tokens))
    return frecuencias, longitudes


def ajustar_zipf(frecuencias_ordenadas, rango_min=1, rango_max=None):
    """Recta de mínimos cuadrados sobre log10(rango) vs log10(frecuencia).

    Devuelve el exponente de Zipf (la pendiente en valor absoluto: en un Zipf
    canónico vale ~1), el intercepto, el R² y cuántos puntos entraron.
    """
    total = len(frecuencias_ordenadas)
    inicio = max(1, rango_min)
    fin = total if rango_max is None else min(total, rango_max)
    if fin - inicio + 1 < 2:
        return None

    rangos = np.arange(inicio, fin + 1)
    valores = np.asarray(frecuencias_ordenadas[inicio - 1 : fin], dtype=float)
    x = np.log10(rangos)
    y = np.log10(valores)

    pendiente, intercepto = np.polyfit(x, y, 1)
    residuos = y - (pendiente * x + intercepto)
    ss_res = float(np.sum(residuos**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")

    return {
        "rango_min": int(inicio),
        "rango_max": int(fin),
        "puntos": int(fin - inicio + 1),
        "exponente": float(-pendiente),
        "intercepto": float(intercepto),
        "r2": float(r2),
    }


def describir(frecuencias, longitudes, top):
    """Estadísticas descriptivas + ajustes de Zipf de un (corpus, versión)."""
    ordenadas = sorted(frecuencias.values(), reverse=True)
    tokens = int(sum(ordenadas))
    tipos = len(ordenadas)
    hapax = sum(1 for f in ordenadas if f == 1)
    arreglo_longitudes = np.asarray(longitudes or [0], dtype=float)

    return {
        "documentos": len(longitudes),
        "tokens": tokens,
        "vocabulario": tipos,
        "ttr": tipos / tokens if tokens else 0.0,
        "hapax": hapax,
        "hapax_pct": hapax / tipos * 100 if tipos else 0.0,
        "longitud_documento": {
            "media": float(arreglo_longitudes.mean()),
            "mediana": float(np.median(arreglo_longitudes)),
            "p90": float(np.percentile(arreglo_longitudes, 90)),
            "min": int(arreglo_longitudes.min()),
            "max": int(arreglo_longitudes.max()),
            "vacios": int((arreglo_longitudes == 0).sum()),
        },
        "top_terminos": [list(item) for item in frecuencias.most_common(top)],
        "zipf_completo": ajustar_zipf(ordenadas),
        "zipf_banda_central": ajustar_zipf(ordenadas, *BANDA_AJUSTE),
    }


def comparar_vocabularios(frecuencias_por_tipo):
    vocabulario_libros = set(frecuencias_por_tipo["libro"])
    vocabulario_entrevistas = set(frecuencias_por_tipo["entrevista"])
    comunes = vocabulario_libros & vocabulario_entrevistas
    union = vocabulario_libros | vocabulario_entrevistas
    return {
        "vocabulario_libros": len(vocabulario_libros),
        "vocabulario_entrevistas": len(vocabulario_entrevistas),
        "vocabulario_compartido": len(comunes),
        "jaccard": len(comunes) / len(union) if union else 0.0,
        "solo_en_libros": len(vocabulario_libros - vocabulario_entrevistas),
        "solo_en_entrevistas": len(vocabulario_entrevistas - vocabulario_libros),
    }


def estilo_ejes(ax, titulo):
    ax.set_title(titulo, color=TINTA_PRIMARIA, fontsize=11, loc="left", pad=10)
    ax.set_xlabel("Rango del término (log)", color=TINTA_SECUNDARIA, fontsize=9)
    ax.set_ylabel("Frecuencia (log)", color=TINTA_SECUNDARIA, fontsize=9)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(True, which="major", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TINTA_SECUNDARIA, labelsize=8)
    for lado, spine in ax.spines.items():
        spine.set_visible(lado in ("left", "bottom"))
        spine.set_color("#d7d6d1")


def dibujar_curva(ax, frecuencias, color, etiqueta, ajuste):
    ordenadas = sorted(frecuencias.values(), reverse=True)
    rangos = np.arange(1, len(ordenadas) + 1)
    ax.plot(rangos, ordenadas, color=color, linewidth=2.0, label=etiqueta)
    if ajuste:
        x = np.array([ajuste["rango_min"], ajuste["rango_max"]], dtype=float)
        y = 10 ** (ajuste["intercepto"] - ajuste["exponente"] * np.log10(x))
        ax.plot(x, y, color=color, linewidth=1.2, linestyle="--", alpha=0.8)


def figura_zipf_preprocesado(conteos, resumen, path):
    """Libros vs entrevistas sobre el texto ya preprocesado."""
    fig, ax = plt.subplots(figsize=(7.2, 4.6), facecolor=SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    for tipo in TIPOS:
        ajuste = resumen[tipo]["preprocesado"]["zipf_banda_central"]
        etiqueta = ETIQUETAS[tipo]
        if ajuste:
            etiqueta += f"  (α = {ajuste['exponente']:.2f}, R² = {ajuste['r2']:.3f})"
        dibujar_curva(ax, conteos["preprocesado"][tipo], COLOR_SERIE[tipo], etiqueta, ajuste)
    estilo_ejes(ax, "Ley de Zipf sobre el corpus preprocesado")
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA_SECUNDARIA)
    fig.text(
        0.01, 0.02,
        f"Línea punteada: ajuste por mínimos cuadrados en los rangos "
        f"{BANDA_AJUSTE[0]}–{BANDA_AJUSTE[1]}.",
        color=TINTA_SECUNDARIA, fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=160, facecolor=SUPERFICIE)
    plt.close(fig)


def figura_crudo_vs_preprocesado(conteos, resumen, path):
    """Un panel por corpus: qué le hace el preprocesamiento a la distribución."""
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.6), facecolor=SUPERFICIE, sharey=True)
    for ax, tipo in zip(axes, TIPOS):
        ax.set_facecolor(SUPERFICIE)
        for version in VERSIONES:
            ajuste = resumen[tipo][version]["zipf_banda_central"]
            etiqueta = version.capitalize()
            if ajuste:
                etiqueta += f" (α = {ajuste['exponente']:.2f})"
            dibujar_curva(ax, conteos[version][tipo], COLOR_SERIE[version], etiqueta, ajuste)
        estilo_ejes(ax, ETIQUETAS[tipo])
        ax.legend(frameon=False, fontsize=9, labelcolor=TINTA_SECUNDARIA)
    axes[1].set_ylabel("")
    fig.suptitle(
        "Efecto del preprocesamiento en la distribución rango-frecuencia",
        color=TINTA_PRIMARIA, fontsize=12, x=0.01, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=160, facecolor=SUPERFICIE)
    plt.close(fig)


def terminos_de_contenido(frecuencias, cuantos):
    """Top de términos sin el ruido de formato de cada fuente."""
    filtradas = Counter(
        {
            palabra: conteo
            for palabra, conteo in frecuencias.items()
            if not es_ruido_de_formato(palabra)
        }
    )
    return filtradas.most_common(cuantos)


def resumir_ruido(frecuencias):
    """Cuánto pesa el ruido de formato en cada corpus (queda en el JSON)."""
    excluidos = {
        palabra: conteo
        for palabra, conteo in frecuencias.items()
        if es_ruido_de_formato(palabra)
    }
    total = sum(frecuencias.values())
    return {
        "tipos_excluidos": len(excluidos),
        "tokens_excluidos": sum(excluidos.values()),
        "pct_tokens": sum(excluidos.values()) / total * 100 if total else 0.0,
        "top": [list(item) for item in Counter(excluidos).most_common(10)],
    }


def figura_longitud_documentos(longitudes, path):
    """Distribución de la longitud de documento, un panel por corpus.

    Paneles separados y no un solo eje porque las dos escalas no son
    comparables: la mediana de una unidad de libro son 11 tokens y la de una
    entrevista, 4.133.
    """
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.2), facecolor=SUPERFICIE)
    for ax, tipo in zip(axes, TIPOS):
        ax.set_facecolor(SUPERFICIE)
        for version in VERSIONES:
            valores = np.asarray(longitudes[version][tipo], dtype=float)
            valores = valores[valores > 0]  # el eje es logarítmico
            # bordes enteros: con bins logarítmicos más angostos que un token
            # el histograma sale en forma de peine en los valores pequeños
            bordes = np.unique(np.floor(np.logspace(0, np.log10(valores.max()), 50)))
            ax.hist(
                valores, bins=bordes, histtype="step", linewidth=2.0,
                color=COLOR_SERIE[version], label=version.capitalize(),
            )
            mediana = float(np.median(valores))
            ax.axvline(mediana, color=COLOR_SERIE[version], linewidth=1.0, linestyle=":")
            ax.annotate(
                f"mediana {mediana:,.0f}".replace(",", "."),
                xy=(mediana, 0.94 - 0.08 * VERSIONES.index(version)),
                xycoords=("data", "axes fraction"), xytext=(5, 0),
                textcoords="offset points", fontsize=8, color=TINTA_SECUNDARIA,
            )
        ax.set_xscale("log")
        ax.set_title(ETIQUETAS[tipo], color=TINTA_PRIMARIA, fontsize=11, loc="left", pad=10)
        ax.set_xlabel("Tokens por documento (log)", color=TINTA_SECUNDARIA, fontsize=9)
        ax.set_ylabel("Documentos", color=TINTA_SECUNDARIA, fontsize=9)
        ax.grid(True, axis="y", color="#e4e3df", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(colors=TINTA_SECUNDARIA, labelsize=8)
        for lado, spine in ax.spines.items():
            spine.set_visible(lado in ("left", "bottom"))
            spine.set_color("#d7d6d1")
        ax.legend(frameon=False, fontsize=9, labelcolor=TINTA_SECUNDARIA)
    fig.suptitle(
        "Longitud de los documentos", color=TINTA_PRIMARIA, fontsize=12, x=0.01, ha="left",
    )
    fig.text(
        0.01, 0.01,
        "Escala logarítmica; se omiten los documentos que quedan en cero tokens.",
        color=TINTA_SECUNDARIA, fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, dpi=160, facecolor=SUPERFICIE)
    plt.close(fig)


def figura_top_terminos(frecuencias_preprocesadas, path):
    """Ranking de términos: la versión legible de la nube de palabras."""
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 5.2), facecolor=SUPERFICIE)
    for ax, tipo in zip(axes, TIPOS):
        ax.set_facecolor(SUPERFICIE)
        terminos = terminos_de_contenido(frecuencias_preprocesadas[tipo], TOP_TERMINOS_EN_FIGURA)
        etiquetas = [palabra for palabra, _ in terminos][::-1]
        valores = [conteo for _, conteo in terminos][::-1]
        posiciones = np.arange(len(etiquetas))
        ax.barh(posiciones, valores, color=COLOR_SERIE[tipo], height=0.62)
        ax.set_yticks(posiciones, etiquetas, fontsize=9)
        for posicion, valor in zip(posiciones, valores):
            ax.annotate(
                f"{valor:,}".replace(",", "."), xy=(valor, posicion),
                xytext=(4, 0), textcoords="offset points",
                va="center", fontsize=8, color=TINTA_SECUNDARIA,
            )
        ax.set_xlim(0, max(valores) * 1.18)
        ax.set_title(ETIQUETAS[tipo], color=TINTA_PRIMARIA, fontsize=11, loc="left", pad=10)
        ax.set_xlabel("Frecuencia en el corpus preprocesado", color=TINTA_SECUNDARIA, fontsize=9)
        ax.grid(True, axis="x", color="#e4e3df", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(colors=TINTA_SECUNDARIA, labelsize=8)
        for lado, spine in ax.spines.items():
            spine.set_visible(lado == "left")
            spine.set_color("#d7d6d1")
    fig.suptitle(
        f"Top {TOP_TERMINOS_EN_FIGURA} de términos por corpus",
        color=TINTA_PRIMARIA, fontsize=12, x=0.01, ha="left",
    )
    fig.text(
        0.01, 0.01,
        "Sobre el texto lematizado y sin stopwords; se excluye el ruido de "
        "formato (etiquetas de hablante, marcas [INTERRUP]/[INAD], dígitos y "
        "restos de URL).",
        color=TINTA_SECUNDARIA, fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, dpi=160, facecolor=SUPERFICIE)
    plt.close(fig)


def figura_nube(frecuencias, tipo, path):
    """Nube de palabras del corpus preprocesado (actividad 2 del enunciado).

    El tamaño codifica la frecuencia y el color la refuerza con una rampa de un
    solo tono: en una nube el color no distingue identidades, así que usarlo
    como paleta categórica solo agregaría ruido.
    """
    frecuencias_nube = dict(terminos_de_contenido(frecuencias, PALABRAS_EN_NUBE))
    mapa = plt.get_cmap(RAMPA_SECUENCIAL[tipo])
    maximo = max(frecuencias_nube.values())
    minimo = min(frecuencias_nube.values())

    def color_por_frecuencia(word, **kwargs):
        peso = frecuencias_nube[word]
        # log: sin ella las 2-3 palabras más frecuentes se llevan toda la rampa
        proporcion = (np.log10(peso) - np.log10(minimo)) / (np.log10(maximo) - np.log10(minimo))
        r, g, b, _ = mapa(0.45 + 0.5 * proporcion)
        return f"rgb({int(r * 255)}, {int(g * 255)}, {int(b * 255)})"

    nube = WordCloud(
        width=1600, height=900, background_color=SUPERFICIE,
        prefer_horizontal=0.9, relative_scaling=0.5, random_state=20250910,
        color_func=color_por_frecuencia,
    ).generate_from_frequencies(frecuencias_nube)

    fig, ax = plt.subplots(figsize=(8.0, 4.8), facecolor=SUPERFICIE)
    ax.imshow(nube, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(
        f"Términos más frecuentes — {ETIQUETAS[tipo]}",
        color=TINTA_PRIMARIA, fontsize=12, loc="left", pad=10,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SUPERFICIE)
    plt.close(fig)


def cargar(path, descripcion):
    if not path.exists():
        raise SystemExit(
            f"no se encontró {descripcion} en {path}.\n"
            "  Generalo primero con: .venv/bin/python preprocesar_corpus.py"
        )
    with path.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def imprimir_resumen(resumen, comparacion):
    print("\n=== Análisis exploratorio ===")
    for tipo in TIPOS:
        print(f"\n{ETIQUETAS[tipo]}")
        for version in VERSIONES:
            d = resumen[tipo][version]
            ajuste = d["zipf_banda_central"] or {}
            print(
                f"  {version:13s} docs={d['documentos']:6d}  tokens={d['tokens']:10d}  "
                f"vocab={d['vocabulario']:7d}  TTR={d['ttr']:.4f}  "
                f"hapax={d['hapax_pct']:.1f}%  "
                f"Zipf α={ajuste.get('exponente', float('nan')):.2f} "
                f"(R²={ajuste.get('r2', float('nan')):.3f})"
            )
    print("\nVocabulario preprocesado compartido:")
    print(
        f"  libros={comparacion['vocabulario_libros']}  "
        f"entrevistas={comparacion['vocabulario_entrevistas']}  "
        f"compartido={comparacion['vocabulario_compartido']}  "
        f"Jaccard={comparacion['jaccard']:.3f}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top", type=int, default=TOP_TERMINOS_POR_DEFECTO,
        help="cuántos términos más frecuentes guardar por corpus (%(default)s)",
    )
    parser.add_argument(
        "--sin-figuras", action="store_true",
        help="calcula las estadísticas sin generar los PNG",
    )
    args = parser.parse_args()

    raw = cargar(RAW_PATH, "el corpus raw")
    preprocesado = cargar(PREPROCESSED_PATH, "el corpus preprocesado")

    conteos, longitudes = {}, {}
    conteos["crudo"], longitudes["crudo"] = contar_corpus(
        raw["documentos"], "texto", tokenizar
    )
    del raw  # 245 MB: liberarlo antes de procesar el preprocesado
    conteos["preprocesado"], longitudes["preprocesado"] = contar_corpus(
        preprocesado["documentos"], "texto_preprocesado", str.split
    )
    entrevistas_incluidas = preprocesado.get("entrevistas_incluidas", True)
    modelo = preprocesado.get("modelo")
    del preprocesado

    resumen = {
        tipo: {
            version: describir(conteos[version][tipo], longitudes[version][tipo], args.top)
            for version in VERSIONES
        }
        for tipo in TIPOS
    }
    comparacion = comparar_vocabularios(conteos["preprocesado"])

    DIR_FIGURAS.mkdir(exist_ok=True)
    figuras = []
    if not args.sin_figuras:
        generadas = [
            ("zipf_preprocesado.png", lambda path: figura_zipf_preprocesado(conteos, resumen, path)),
            ("zipf_crudo_vs_preprocesado.png", lambda path: figura_crudo_vs_preprocesado(conteos, resumen, path)),
            ("longitud_documentos.png", lambda path: figura_longitud_documentos(longitudes, path)),
            ("top_terminos.png", lambda path: figura_top_terminos(conteos["preprocesado"], path)),
        ]
        generadas += [
            (f"nube_{tipo}s.png", lambda path, tipo=tipo: figura_nube(conteos["preprocesado"][tipo], tipo, path))
            for tipo in TIPOS
        ]
        for nombre, dibujar in generadas:
            dibujar(DIR_FIGURAS / nombre)
            figuras.append(f"figuras/{nombre}")

    salida = {
        "version": 1,
        "modelo": modelo,
        "entrevistas_incluidas": entrevistas_incluidas,
        "banda_ajuste_zipf": list(BANDA_AJUSTE),
        "corpus": resumen,
        "comparacion_vocabulario_preprocesado": comparacion,
        "ruido_de_formato": {
            "regla": (
                "etiquetas de hablante (ent/test con dígito opcional), "
                "abreviaturas de transcripción, restos de URL y tokens "
                "numéricos; excluidos solo de las figuras de contenido"
            ),
            "abreviaturas": sorted(ABREVIATURAS_TRANSCRIPCION | RUIDO_WEB),
            "por_corpus": {
                tipo: resumir_ruido(conteos["preprocesado"][tipo]) for tipo in TIPOS
            },
        },
        "figuras": figuras,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporal = SALIDA_PATH.with_suffix(".json.tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)
    temporal.replace(SALIDA_PATH)

    imprimir_resumen(resumen, comparacion)
    if not entrevistas_incluidas:
        print("\n[aviso] el corpus se generó sin entrevistas: la comparación está incompleta")
    print(f"\nEstadísticas: {SALIDA_PATH}")
    for figura in figuras:
        print(f"Figura: {ROOT / figura}")


if __name__ == "__main__":
    main()
