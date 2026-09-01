"""Agentes de análisis para el prototipo de detección de sesgo mediático.

Fundamento académico:
  - Hamborg (2020), ACL SRW: bias by word choice and labeling (WCL).
    https://aclanthology.org/2020.acl-srw.12/
  - Hamborg (2023), Springer: person-oriented framing analysis.
    https://link.springer.com/book/10.1007/978-3-031-17693-7
  - Media Bias Detector (CHI 2025): comparación LLM-driven por publisher.
    https://arxiv.org/html/2502.06009v2

Cada agente llama al modelo con un system prompt que exige una respuesta en
JSON estricto (sin texto adicional, sin markdown) y valida el resultado con
json.loads antes de devolverlo.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

MODEL = "claude-sonnet-5"

_client = anthropic.Anthropic()


class RespuestaNoJSONError(RuntimeError):
    """El modelo no devolvió un JSON válido."""


def _extraer_json(texto: str) -> dict[str, Any]:
    """Limpia fences de markdown si el modelo los agrega y parsea JSON."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[1] if "\n" in limpio else limpio
        if limpio.endswith("```"):
            limpio = limpio.rsplit("```", 1)[0]
        limpio = limpio.strip()
        if limpio.startswith("json"):
            limpio = limpio[4:].strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError as exc:
        raise RespuestaNoJSONError(f"Respuesta no parseable como JSON: {texto[:300]!r}") from exc


def _llamar_agente(system_prompt: str, contenido_usuario: str, max_tokens: int = 2048) -> dict[str, Any]:
    respuesta = _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": contenido_usuario}],
    )
    texto = "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")
    return _extraer_json(texto)


# ---------------------------------------------------------------------------
# 1. Agente verificador de evento
# ---------------------------------------------------------------------------

_SYSTEM_VERIFICADOR = """\
Eres un verificador de eventos noticiosos. Recibes artículos de distintos \
medios y debes determinar si todos cubren el MISMO evento puntual (mismo \
hecho, misma fecha/contexto), no solo el mismo tema general.

Si un artículo trata un evento distinto o insuficientemente relacionado, \
debes descartarlo explícitamente con una razón concreta.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin \
markdown, con este esquema exacto:
{
  "mismo_evento": true|false,
  "resumen_evento": "resumen neutral del hecho verificado, 2-3 frases",
  "medios_confirmados": ["nombre_medio", ...],
  "medios_descartados": [{"medio": "nombre_medio", "razon": "..."}]
}
"""


def verificar_mismo_evento(articulos: list[dict[str, Any]]) -> dict[str, Any]:
    """Confirma si los artículos dados cubren el mismo evento y descarta los que no."""
    contenido = json.dumps(articulos, ensure_ascii=False, indent=2)
    return _llamar_agente(_SYSTEM_VERIFICADOR, contenido)


# ---------------------------------------------------------------------------
# 2. Agente léxico / framing (Hamborg 2020 - WCL)
# ---------------------------------------------------------------------------

_SYSTEM_LEXICO = """\
Eres un analista de sesgo mediático especializado en bias by word choice \
and labeling (Hamborg, 2020). NO analizas sentimiento ni tono; analizas \
selección léxica: cómo un mismo concepto o entidad se nombra con términos \
distintos que cargan connotaciones distintas (ej. "reforma" vs "impuestazo", \
"manifestantes" vs "vándalos").

Recibes un único artículo. Identifica los términos clave con carga de \
framing y a qué concepto/entidad se refieren.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin \
markdown, con este esquema exacto:
{
  "medio": "nombre_medio",
  "terminos_clave": [
    {
      "termino": "...",
      "concepto_referido": "...",
      "connotacion": "positiva|negativa|neutra",
      "justificacion": "..."
    }
  ],
  "resumen_framing": "1-2 frases sobre el patrón léxico dominante"
}
"""


def analizar_lexico_framing(articulo: dict[str, Any]) -> dict[str, Any]:
    """Identifica bias by word choice and labeling en un artículo."""
    contenido = json.dumps(articulo, ensure_ascii=False, indent=2)
    return _llamar_agente(_SYSTEM_LEXICO, contenido)


# ---------------------------------------------------------------------------
# 3. Agente actores / citas (Hamborg 2023 - person-oriented framing)
# ---------------------------------------------------------------------------

_SYSTEM_ACTORES = """\
Eres un analista de person-oriented framing (Hamborg, 2023). Analizas cómo \
un artículo retrata a las personas/instituciones involucradas en un evento: \
qué rol les atribuye, qué citas usa (directas e indirectas) y con qué \
encuadre (ej. protagonista, víctima, responsable, obstáculo).

Recibes un único artículo. NO analices tono; analiza atribución de roles y \
uso de voces.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin \
markdown, con este esquema exacto:
{
  "medio": "nombre_medio",
  "actores": [
    {
      "nombre": "...",
      "rol_atribuido": "...",
      "encuadre": "...",
      "citas_directas": ["..."],
      "citas_indirectas": ["..."]
    }
  ],
  "resumen_actores": "1-2 frases sobre a quién favorece el encuadre de actores"
}
"""


def analizar_actores_citas(articulo: dict[str, Any]) -> dict[str, Any]:
    """Identifica person-oriented framing en un artículo."""
    contenido = json.dumps(articulo, ensure_ascii=False, indent=2)
    return _llamar_agente(_SYSTEM_ACTORES, contenido)


# ---------------------------------------------------------------------------
# 4. Agente estilo / énfasis (extensión propia, ligada a Taller 1)
# ---------------------------------------------------------------------------

# NOTA (simplificación temporal, decisión ya tomada): este agente hoy pide una
# estimación CUALITATIVA al modelo. La versión correcta debe reemplazar esta
# llamada por métricas cuantitativas reales (textstat, textdescriptives) sobre
# el texto del artículo, reutilizando el pipeline del Taller 1, en vez de
# preguntarle al LLM. No cambiar esto sin justificación explícita.

_SYSTEM_ESTILO = """\
Eres un analista de estilo y énfasis temático en cobertura noticiosa. \
Recibes un único artículo. Estima, de forma cualitativa, qué tan extenso/ \
detallado es el tratamiento de cada subtema del evento (énfasis temático) \
y describe rasgos de estilo relevantes (longitud relativa, uso de \
titulares alarmistas, presencia de contexto/antecedentes).

Esta es una estimación cualitativa temporal: NO calcules métricas exactas, \
solo describe patrones observables en el texto.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin \
markdown, con este esquema exacto:
{
  "medio": "nombre_medio",
  "enfasis_tematico": [
    {"subtema": "...", "grado_enfasis": "alto|medio|bajo", "evidencia": "..."}
  ],
  "estimacion_cualitativa": {
    "extension_relativa": "alta|media|baja",
    "titular_alarmista": true|false,
    "incluye_contexto_antecedentes": true|false
  },
  "nota": "simplificación temporal: pendiente reemplazar por métricas cuantitativas (textstat/textdescriptives) del Taller 1"
}
"""


def analizar_estilo_enfasis(articulo: dict[str, Any]) -> dict[str, Any]:
    """Estimación cualitativa temporal de estilo/énfasis (ver nota arriba)."""
    contenido = json.dumps(articulo, ensure_ascii=False, indent=2)
    return _llamar_agente(_SYSTEM_ESTILO, contenido)


# ---------------------------------------------------------------------------
# 5. Agente de síntesis
# ---------------------------------------------------------------------------

_SYSTEM_SINTESIS = """\
Eres un agente de síntesis. Recibes el resultado de verificación de evento \
y los tres análisis (léxico/framing, actores/citas, estilo/énfasis) de cada \
medio confirmado. Debes consolidar un reporte comparativo único que \
resalte las diferencias de framing entre medios sobre el MISMO evento.

No repitas los datos crudos: sintetiza comparativamente. No emitas juicio \
sobre qué medio es "mejor"; describe diferencias, no las valores.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin \
markdown, con este esquema exacto:
{
  "evento_id": "...",
  "resumen_evento": "...",
  "medios_analizados": ["..."],
  "medios_descartados": ["..."],
  "diferencias_lexico_framing": "...",
  "diferencias_actores_citas": "...",
  "diferencias_estilo_enfasis": "...",
  "conclusion_comparativa": "2-4 frases"
}
"""


def sintetizar_reporte(
    evento_id: str,
    verificacion: dict[str, Any],
    analisis_lexico: list[dict[str, Any]],
    analisis_actores: list[dict[str, Any]],
    analisis_estilo: list[dict[str, Any]],
) -> dict[str, Any]:
    """Consolida los tres análisis por medio en un reporte comparativo único."""
    entrada = {
        "evento_id": evento_id,
        "verificacion": verificacion,
        "analisis_lexico_framing": analisis_lexico,
        "analisis_actores_citas": analisis_actores,
        "analisis_estilo_enfasis": analisis_estilo,
    }
    contenido = json.dumps(entrada, ensure_ascii=False, indent=2)
    return _llamar_agente(_SYSTEM_SINTESIS, contenido, max_tokens=3072)
