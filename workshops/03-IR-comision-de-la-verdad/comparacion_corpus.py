"""Construye el cuadro entrevista-libro y el heatmap del Taller 3.

La fuente es el ranking TF-IDF oficial de pasajes. Los puntajes agregados son
la suma de las diez mejores unidades de cada libro; para visualizar entrevistas
con escalas distintas se normalizan por el máximo de cada entrevista, sin
alterar el ranking persistido.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FIGURAS_DIR = ROOT / "figuras"
RANKING_PATH = DATA_DIR / "ranking_tfidf.json"
CUADRO_PATH = DATA_DIR / "cuadro_vinculos.json"
HEATMAP_PATH = FIGURAS_DIR / "heatmap_vinculos_tfidf.png"


def construir_cuadro(ranking):
    libros = ranking["corpus"]["libros"]
    filas = []
    matriz = []
    for resultado in ranking["resultados"]:
        scores = np.asarray([resultado["libros"].get(libro, 0.0) for libro in libros])
        orden = np.argsort(-scores, kind="stable")
        filas.append({
            "entrevista": resultado["consulta"],
            "libros_top3": [
                {"libro": libros[posicion], "score": float(scores[posicion])}
                for posicion in orden[:3]
            ],
            "libros_scores": {
                libro: float(score) for libro, score in zip(libros, scores)
            },
        })
        maximo = scores.max()
        matriz.append(scores / maximo if maximo else scores)
    return libros, filas, np.asarray(matriz, dtype=np.float64)


def main():
    with RANKING_PATH.open(encoding="utf-8") as archivo:
        ranking = json.load(archivo)
    libros, filas, matriz_entrevistas = construir_cuadro(ranking)
    cuadro = {
        "version": 1,
        "fuente": "data/ranking_tfidf.json",
        "criterio": "TF-IDF oficial por pasajes; suma de las 10 mejores unidades por libro",
        "normalizacion_heatmap": "cada entrevista se divide por su máximo entre libros; solo para visualización",
        "libros": libros,
        "entrevistas": filas,
    }
    DATA_DIR.mkdir(exist_ok=True)
    FIGURAS_DIR.mkdir(exist_ok=True)
    with CUADRO_PATH.open("w", encoding="utf-8") as archivo:
        json.dump(cuadro, archivo, ensure_ascii=False, indent=2)

    matriz = matriz_entrevistas.T
    fig, ax = plt.subplots(figsize=(18, 5.5), facecolor="#fcfcfb")
    imagen = ax.imshow(
        matriz,
        aspect="auto",
        interpolation="nearest",
        cmap="YlOrRd",
        vmin=0,
        vmax=1,
    )
    ax.set_yticks(np.arange(len(libros)), libros, fontsize=8)
    ax.set_xlabel("Entrevistas ordenadas por el archivo ranking_tfidf.json", fontsize=9)
    ax.set_ylabel("Libro ganador o vinculado", fontsize=9)
    ax.set_title("Relacionamiento entrevista-libro — TF-IDF oficial", loc="left", fontsize=12)
    ax.set_xticks([])
    fig.colorbar(imagen, ax=ax, label="Puntaje agregado relativo por entrevista", fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(HEATMAP_PATH, dpi=180, facecolor="#fcfcfb")
    plt.close(fig)

    ganadores = {}
    for fila in filas:
        libro = fila["libros_top3"][0]["libro"]
        ganadores[libro] = ganadores.get(libro, 0) + 1
    print(f"Entrevistas: {len(filas)}")
    print(f"Libros: {len(libros)}")
    print(f"Cuadro: {CUADRO_PATH}")
    print(f"Heatmap: {HEATMAP_PATH}")
    print("Ganadores:", sorted(ganadores.items(), key=lambda item: (-item[1], item[0])))


if __name__ == "__main__":
    main()