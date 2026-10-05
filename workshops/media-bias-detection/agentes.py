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
# 4. Métricas de estilo / énfasis
# ---------------------------------------------------------------------------


def analizar_estilo_enfasis(articulo: dict[str, Any]) -> dict[str, Any]:
    """Calcula métricas cuantitativas de estilo y legibilidad en español."""
    import textstat

    texto = articulo.get("texto", "")
    palabras = texto.split()
    if len(palabras) < 5:
        return {
            "medio": articulo.get("medio", "desconocido"),
            "error": "Texto muy corto o ausente",
            "palabras_totales": len(palabras),
        }

    textstat.set_lang("es")
    num_oraciones = max(textstat.sentence_count(texto), 1)
    flesch = textstat.flesch_reading_ease(texto)
    gunning = textstat.gunning_fog(texto)

    return {
        "medio": articulo.get("medio", "desconocido"),
        "metricas": {
            "flesch_reading_ease": round(flesch, 2),
            "gunning_fog": round(gunning, 2),
            "palabras_totales": len(palabras),
            "oraciones_totales": num_oraciones,
            "promedio_palabras_por_oracion": round(len(palabras) / num_oraciones, 2),
            "longitud_texto_caracteres": len(texto),
        },
        "interpretacion_legibilidad": (
            "alta (accesible)"
            if flesch > 60
            else "media (requiere atención)"
            if flesch > 40
            else "baja (complejo)"
        ),
    }


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
