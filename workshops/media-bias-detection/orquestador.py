"""Orquestador del pipeline de detección de sesgo mediático.

Flujo:
  1. Obtiene artículos: desde `corpus_ejemplo.json` (curado, ya trae
     `evento_id`) o, si se pasa un tema por CLI, vía
     `busqueda.buscar_noticias_actuales(tema, n)`.
  2. Agrupa por evento y corre el verificador de evento.
  3. Descarta los medios que el verificador marque como `medios_descartados`
     (no se fuerza el análisis con fuentes no verificadas).
  4. Corre los tres analistas (léxico/framing, actores/citas, estilo/énfasis)
     sobre cada medio confirmado.
  5. Corre el agente de síntesis y imprime cada resultado en JSON.

Uso:
    python orquestador.py                  # usa corpus_ejemplo.json
    python orquestador.py "tema a buscar"   # busca noticias reales del tema
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from typing import Any

from agentes import (
    analizar_actores_citas,
    analizar_estilo_enfasis,
    analizar_lexico_framing,
    sintetizar_reporte,
    verificar_mismo_evento,
)
from busqueda import buscar_noticias_actuales

CORPUS_PATH = "corpus_ejemplo.json"
N_MEDIOS_BUSQUEDA = 2


def _imprimir(etiqueta: str, datos: Any) -> None:
    print(f"\n=== {etiqueta} ===")
    print(json.dumps(datos, ensure_ascii=False, indent=2))


def cargar_articulos_por_evento(tema: str | None) -> dict[str, list[dict[str, Any]]]:
    """Devuelve un dict evento_id -> lista de artículos.

    Si `tema` es None, carga el corpus curado (ya trae evento_id por
    artículo). Si se da un tema, busca noticias reales; como aún no están
    verificadas como el mismo evento puntual, se agrupan bajo un único
    evento_id derivado del tema, pendiente de que el verificador confirme
    o descarte cada medio.
    """
    if tema is None:
        with open(CORPUS_PATH, encoding="utf-8") as f:
            articulos = json.load(f)
        por_evento: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for articulo in articulos:
            por_evento[articulo["evento_id"]].append(articulo)
        return dict(por_evento)

    articulos = buscar_noticias_actuales(tema, N_MEDIOS_BUSQUEDA)
    evento_id = f"busqueda:{tema}"
    return {evento_id: articulos}


def procesar_evento(evento_id: str, articulos: list[dict[str, Any]]) -> None:
    _imprimir(f"Evento: {evento_id} (artículos recibidos)", articulos)

    verificacion = verificar_mismo_evento(articulos)
    _imprimir("Verificación de evento", verificacion)

    medios_confirmados = set(verificacion.get("medios_confirmados", []))
    articulos_confirmados = [a for a in articulos if a["medio"] in medios_confirmados]

    if not articulos_confirmados:
        print(f"\nEvento {evento_id}: ningún medio confirmado por el verificador. Se omite el análisis.")
        return

    analisis_lexico = [analizar_lexico_framing(a) for a in articulos_confirmados]
    analisis_actores = [analizar_actores_citas(a) for a in articulos_confirmados]
    analisis_estilo = [analizar_estilo_enfasis(a) for a in articulos_confirmados]

    _imprimir("Análisis léxico/framing", analisis_lexico)
    _imprimir("Análisis actores/citas", analisis_actores)
    _imprimir("Análisis estilo/énfasis", analisis_estilo)

    reporte = sintetizar_reporte(
        evento_id, verificacion, analisis_lexico, analisis_actores, analisis_estilo
    )
    _imprimir("Reporte de síntesis", reporte)


def main() -> None:
    tema = sys.argv[1] if len(sys.argv) > 1 else None
    por_evento = cargar_articulos_por_evento(tema)
    for evento_id, articulos in por_evento.items():
        procesar_evento(evento_id, articulos)


if __name__ == "__main__":
    main()
