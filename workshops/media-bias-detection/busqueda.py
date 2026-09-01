"""Agente de búsqueda: encuentra noticias colombianas actuales sobre un tema.

Importante (decisión de diseño): este agente encuentra artículos del mismo
TEMA, no necesariamente del mismo EVENTO puntual. Por eso el resultado
siempre debe pasar por `agentes.verificar_mismo_evento` antes de analizarse;
el orquestador no debe saltarse ese paso.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import anthropic

from agentes import MODEL, RespuestaNoJSONError, _extraer_json

_client = anthropic.Anthropic()


class AgenteBusqueda(ABC):
    """Interfaz para agentes que traen artículos candidatos sobre un tema."""

    @abstractmethod
    def buscar(self, tema: str, n: int = 2) -> list[dict[str, Any]]:
        """Devuelve hasta `n` artículos de medios distintos sobre `tema`.

        Cada artículo debe tener el esquema:
        {"medio": str, "titulo": str, "texto": str, "fecha": str, "url": str}
        """
        raise NotImplementedError


_SYSTEM_BUSQUEDA = """\
Eres un agente de búsqueda de noticias colombianas actuales. Usa la \
herramienta de búsqueda web para encontrar cobertura reciente sobre el tema \
indicado, publicada por medios colombianos distintos entre sí.

Para cada medio encontrado, resume el contenido relevante del artículo \
(no copies el texto completo, sintetiza los hechos, declaraciones y \
términos usados) en un campo "texto" suficientemente detallado como para \
permitir un análisis de framing posterior.

Devuelve exactamente {n} artículos de {n} medios distintos, si están \
disponibles. Si encuentras menos, devuelve los que tengas.

Cuando termines de buscar, responde ÚNICAMENTE con un objeto JSON válido \
(en un bloque de texto final, sin markdown), con este esquema exacto:
{{
  "articulos": [
    {{"medio": "...", "titulo": "...", "texto": "...", "fecha": "YYYY-MM-DD", "url": "..."}}
  ]
}}
"""


class BusquedaWebAnthropic(AgenteBusqueda):
    """Implementación real usando la herramienta web_search_20250305 de Anthropic."""

    def buscar(self, tema: str, n: int = 2) -> list[dict[str, Any]]:
        return buscar_noticias_actuales(tema, n)


def buscar_noticias_actuales(tema: str, n: int = 2) -> list[dict[str, Any]]:
    """Busca noticias colombianas actuales sobre `tema` usando web search real.

    Devuelve una lista de hasta `n` artículos de medios distintos. El
    resultado NO está verificado como el mismo evento puntual: debe pasar
    por `agentes.verificar_mismo_evento` antes de analizarse.
    """
    system_prompt = _SYSTEM_BUSQUEDA.format(n=n)
    respuesta = _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[
            {
                "role": "user",
                "content": f"Tema: {tema}. Encuentra {n} medios colombianos distintos que cubran noticias actuales sobre este tema.",
            }
        ],
    )

    bloques_texto = [bloque.text for bloque in respuesta.content if bloque.type == "text"]
    if not bloques_texto:
        raise RespuestaNoJSONError("El modelo no devolvió texto tras la búsqueda web.")

    # El JSON final suele estar en el último bloque de texto de la respuesta.
    for texto in reversed(bloques_texto):
        try:
            datos = _extraer_json(texto)
            break
        except RespuestaNoJSONError:
            continue
    else:
        raise RespuestaNoJSONError(f"Ningún bloque de texto contenía JSON válido: {bloques_texto}")

    articulos = datos.get("articulos", [])
    return articulos[:n]
