"""E13: variables H19-H23 (H18 y H21 se descartaron al verificarlas), diseñadas leyendo SOLO los errores de la partición de desarrollo (80 % del train).

El 20 % restante (`recursos/control_E13.npy`, StratifiedKFold(5, random_state=2026) por combinación, partición 0)
no se miró al diseñarlas y sirve para medir la ganancia sin sesgo de selección. El test no se miró.

Uso:
    import toxic_base as tb, ext_variables as ev, ext_variables2 as ev2
    d = tb.Datos(extra_lex=[ev.variables(generica=True), ev2.variables()])
"""
import re

PATRONES_E13 = {
    # H19: "perra" como mascota (contexto animal) -> menos HS/TR. Dev: n=5, P(HS)=0,20 (prevalencia 0,44)
    'perra_mascota':        r'\b(mi|la|una) perr(a|ita)\b.*\b(muerde|ladra|paseo|pasear|sacar|ronca|duerme|gato|pajaro'
                            r'|veterinari\w*|cachorr\w*|trucos|callada)\b'
                            r'|\b(muerde|ladra|paseo|pasear|sacar|ronca|gato|pajaro|veterinari\w*)\b.*\bperr(a|ita)\b',
    # H20: estereotipo sexista sin insulto (chistes sobre "la mujer"). Dev: n=9, P(HS)=1,00
    'estereotipo_sexista':  r'feminazi|todas ?putas|\ba fregar\b|\b(a|vete a|ve a|vuelve a) la cocina\b'
                            r'|\bhazme (la cena|de comer|un sandwich)\b|\bmujer(es)? al volante\b'
                            r'|\b(el cerebro|la logica|la mente) de (la|una) mujer\b',
    # H22: fórmula de chiste racista "racismo es que...". Dev: n=4, P(HS)=0,75
    'racismo_es':           r'\bracismo ?(es|es que)\b',
    # H23: "puta" aplicada a algo no humano (intensificador ampliado). Dev: n=106, P(HS)=0,14
    'puta_no_humano':       r'\bputa (serie|vida|gente|broma|mierda|madre|idea|guia|cosa|catalua|espaa)\b'
                            r'|\bni puta\b|\bhostia puta\b|\bputa que\b',
}
# Descartadas tras verificarlas en desarrollo: sexual explícito (P(HS)=0,20-0,41), "güero" (0,19), insulto +
# tono de broma/afecto (0,72: más odio, no menos), insulto + "soy" (0,57, igual al insulto solo).
RE_E13 = {k: re.compile(p) for k, p in PATRONES_E13.items()}
COLUMNAS = list(PATRONES_E13)


def variables(columnas=None, nombre=None):
    """Tuple (nombre, función, columnas) para `tb.Datos(extra_lex=[...])`."""
    cols = list(columnas or COLUMNAS)
    if nombre is None:
        nombre = 'h18' + ('' if cols == COLUMNAS else '-' + '-'.join(str(COLUMNAS.index(c)) for c in cols))
    def fn(raw, norm):
        return [int(bool(RE_E13[c].search(norm))) for c in cols]
    return (nombre, fn, cols)
