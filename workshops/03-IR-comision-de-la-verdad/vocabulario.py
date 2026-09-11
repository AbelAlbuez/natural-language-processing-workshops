"""Reglas de vocabulario compartidas por el análisis exploratorio y el índice.

Aquí vive una sola definición de qué tokens vienen del **formato** de la fuente
en lugar del contenido. La usan `analisis_exploratorio.py` (para que las nubes y
el ranking muestren vocabulario del dominio) y `modelo_ir.py` (para que no
entren al índice). Si las dos tuvieran su propia copia, el corpus analizado y el
corpus recuperado dejarían de ser el mismo.
"""

import re

# Etiquetas de turno de las transcripciones: "TEST:", "ENT:", "ENT1:", "TEST2:"
PATRON_ETIQUETA_HABLANTE = re.compile(r"^(?:ent|test)\d*$")

# Marcas entre corchetes de las transcripciones, con sus erratas reales:
# [INTERRUP] (interrupción), [INAD] (inaudible), [CONT] (continuación), [DUD].
ABREVIATURAS_TRANSCRIPCION = {
    "interrup", "interrump", "interrupt", "interup", "interrrup",
    "interrp", "interurp", "inerrup", "nterrup", "inad", "cont", "dud",
}

# Restos de las URL de las notas al pie: el tokenizador parte
# "https://www.comisiondelaverdad.co/..." y "https"/"www" entran como términos.
RUIDO_WEB = {"http", "https", "www"}

# Quedan fuera de estas listas a propósito [RISAS], [LLANTO] y [CORTE]: "risas",
# "llanto" y "corte" también son palabras corrientes del español y, sin los
# corchetes —que el tokenizador ya eliminó—, no hay forma de distinguir la marca
# del uso real sin descartar contenido legítimo.


def es_ruido_de_formato(palabra):
    """Token que viene del formato de la fuente, no del contenido."""
    return (
        palabra.isdigit()
        or palabra in ABREVIATURAS_TRANSCRIPCION
        or palabra in RUIDO_WEB
        or bool(PATRON_ETIQUETA_HABLANTE.match(palabra))
    )
