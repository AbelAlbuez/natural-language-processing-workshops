"""E10b: variables lingüísticas nuevas derivadas del análisis de errores del stacking E8b (hipótesis H12-H17).

Uso:
    import toxic_base as tb, ext_variables as ev
    d = tb.Datos(extra_lex=[ev.variables()])        # caché en oof/base+errores/

Todos los patrones se aplican sobre el texto normalizado por `tb.normalizar` (minúsculas, sin tildes ni ñ,
menciones -> xuser, URLs -> xurl). Se decidieron leyendo solo el train (OOF de E8b), nunca el test.
"""
import re
import toxic_base as tb

FEM = r'(puta|perra|zorra|guarra|putita|perrita|zorrita)s?'
GRUPO = (r'(inmigrantes|migrantes|subsaharianos|ilegales|indocumentados|refugiados|sudacas|sudakas|moros|negratas'
         r'|negros|manteros|(a)?rabes|extranjeros|invasores|africanos|musulmanes|venezolanos|peruanos|indios'
         r'|panchitos|menas)')
MIGRA = (r'inmigra|migrant|subsahar|ilegal|sin papeles|indocumentad|refugiad|sudac|sudak|\bmoros?\b|negrat|manter'
         r'|\b(a)?rabes?\b|extranjer|invasor|africano|musulm')

PATRONES_E10 = {
    # H12: posesivo + insulto femenino (mi perra = la mascota o trato afectuoso); "eres mi puta" se excluye
    'posesivo_fem':      rf'\b(mi|mis|su|sus) {FEM}\b',
    'eres_mi_fem':       rf'\beres mi {FEM}',
    # H13: negación o defensa frente al insulto ("no es una guarra por...", "ni puta ni zorra")
    'negacion_fem':      rf'\bno (es|eres|soy|son|somos|sea|seas|era) (una |un |ninguna |tu |la )?(\w+ )?{FEM}\b'
                         rf'|\bni {FEM} ni\b|\b{FEM} por (ir|hacer|llevar|ensear|vestir|hablar|subir|pensar)\b'
                         rf'|\bno (te|la|nos|las) (convierte|hace)\b|\bno hay mujer|\bno una {FEM}',
    # H14: "árabe" dentro de un estereotipo u hostilidad (en vez de música/comida/idioma)
    'arabe_hostil':      r'\b(estos|esos|malditos|los|odio a los|odio a estos)( \w+)? (a)?rabes\b'
                         r'|(a)?rabes? (de mierda|d mierda|hijos de|come mierda)'
                         r'|(a)?rabe.*(bomba|explot|atentad|terror|isis|yihad|delincuen|machis|flojo|miedo|lapid)'
                         r'|(bomba|explot|atentad|terror|isis|yihad)\w*.*\b(a)?rabes?\b',
    # H15: grupo migrante + deshumanización o llamado a expulsar/violentar
    '_deshumaniza':      r'escoria|lacra|plaga|basura|chusma|parasit|\bratas\b|salvajes|animales|bestias|invasor'
                         r'|delincuen|de mierda',
    '_expulsion_violencia': r'\b(fuera|largate|larguese|vuelvan|vete|vayan|vayanse|regresen|devuelv\w*|echad|echarlos'
                         r'|echenlos|patadas|que se vayan|que se larguen|expulsad\w*|extingan|muera|mueran|matar'
                         r'|matarlos|ahorcar|quemar|disparar|subfusil|ejercito|ejrcito)\b',
    '_migra':            MIGRA,
    # H16: demostrativo o "putos" + grupo en plural ("estos indocumentados", "esos moros")
    'demostrativo_grupo': rf'\b(estos|esos|malditos|putos|tus queridos|vuestros)( \w+)? {GRUPO}\b',
    # H17: demostrativo femenino singular: señala a una mujer concreta (TR) sin mención
    'demostrativo_fem':  rf'\b(esta|esa) (\w+ )?{FEM}\b|\bla {FEM} (esa|esta)\b'
                         r'|\b(esta|esa) (mina|vieja|tipa|mujer|nia|niita|chava|morra|tia|ta)\b',
}
# Versión "genérica": sin las palabras que se copiaron de tweets concretos mal clasificados (control del sesgo de
# selección: si la mejora viniera solo de memorizar esos tweets, esta versión no debería mejorar).
PATRONES_GENERICOS = dict(PATRONES_E10)
PATRONES_GENERICOS.update({
    'arabe_hostil':      r'\b(estos|esos|malditos)( \w+)? (a)?rabes\b|(a)?rabes? de mierda'
                         r'|(a)?rabe.*(bomba|terror)|(bomba|terror)\w*.*\b(a)?rabes?\b',
    '_deshumaniza':      r'escoria|lacra|plaga|basura|chusma|parasit|\bratas\b|salvajes|animales|bestias|de mierda',
    '_expulsion_violencia': r'\b(fuera|largate|vete|vayanse|que se vayan|expulsad\w*|mueran|matar|matarlos)\b',
    'demostrativo_grupo': rf'\b(estos|esos|malditos|putos)( \w+)? {GRUPO}\b',
    'demostrativo_fem':  rf'\b(esta|esa) (\w+ )?{FEM}\b|\b(esta|esa) (vieja|tipa|mujer)\b',
    'negacion_fem':      rf'\bno (es|eres|soy|son) (una |un |ninguna )?{FEM}\b|\bni {FEM} ni\b',
})
RE_E10 = {k: re.compile(p) for k, p in PATRONES_E10.items()}
RE_GEN = {k: re.compile(p) for k, p in PATRONES_GENERICOS.items()}
COLUMNAS = ['posesivo_fem_sin_eres', 'negacion_fem', 'arabe_hostil', 'hostilidad_migrante', 'expulsion_migrante',
            'demostrativo_grupo', 'demostrativo_fem']


def marcas(norm, generica=False):
    """Diccionario patrón -> bool sobre un texto ya normalizado (útil para las tablas de verificación)."""
    return {k: bool(r.search(norm)) for k, r in (RE_GEN if generica else RE_E10).items()}


def fila(norm, generica=False):
    c = marcas(norm, generica)
    migra = c['_migra']
    return {
        'posesivo_fem_sin_eres': int(c['posesivo_fem'] and not c['eres_mi_fem']),
        'negacion_fem':          int(c['negacion_fem']),
        'arabe_hostil':          int(c['arabe_hostil']),
        'hostilidad_migrante':   int(migra and (c['_deshumaniza'] or c['_expulsion_violencia'])),
        'expulsion_migrante':    int(migra and c['_expulsion_violencia']),
        'demostrativo_grupo':    int(c['demostrativo_grupo']),
        'demostrativo_fem':      int(c['demostrativo_fem']),
    }


def variables(columnas=None, generica=False, nombre=None):
    """Tuple (nombre, función, columnas) para `tb.Datos(extra_lex=[...])`.

    columnas: subconjunto de COLUMNAS (para ablaciones); generica: usar PATRONES_GENERICOS.
    Por defecto (todas las columnas, versión completa) la caché queda en oof/base+errores/.
    """
    cols = list(columnas or COLUMNAS)
    if nombre is None:
        nombre = 'errores' + ('-gen' if generica else '')
        if cols != COLUMNAS:
            nombre += '-' + '-'.join(str(COLUMNAS.index(c)) for c in cols)
    def fn(raw, norm):
        f = fila(norm, generica)
        return [f[c] for c in cols]
    return (nombre, fn, cols)


# ===================================================================================================
# Opcional: normalización que repara palabras a las que el corpus les borró la vocal acentuada
# ('cllate' -> 'callate', 'imbcil' -> 'imbecil'). El mapeo se aprende SOLO con los textos del train.
# ===================================================================================================
import collections, os
import pandas as pd

_ONSET = {'bl', 'br', 'cl', 'cr', 'dr', 'fl', 'fr', 'gl', 'gr', 'pl', 'pr', 'tr', 'ch', 'll', 'rr', 'qu', 'gu', 'ps', 'tl'}
_CLUSTER_OK = re.compile(r'[nmlrsb]?(bl|br|cl|cr|dr|fl|fr|gl|gr|pl|pr|tr|ch|ll|rr)|ns[tcp]|bs[tc]|[nr]s')

def _imposible(w):
    """True si la palabra no puede existir en español escrito (le falta una vocal): 'cmo', 'vdeo', 'cllate'."""
    m = re.match(r'^[^aeiouy]{2,}', w)
    if m and (len(m.group()) > 2 or m.group() not in _ONSET):
        return True
    if len(w) > 3 and re.search(r'[^aeiouy]{2,}$', w) and not re.search(r'(ns|rs|ls|ds|ch)$', w):
        return True
    if w[-1] not in 'aeiouynsrldzjx':
        return True
    return any(not _CLUSTER_OK.fullmatch(c[-3:]) for c in re.findall(r'[^aeiouy]{3,}', w[1:]))

def aprender_mapeo_tildes(textos_norm, min_frec=2):
    cnt = collections.Counter(w for t in textos_norm for w in re.findall(r'\b[a-z]+\b', t))
    mapeo = {}
    for w in cnt:
        if len(w) < 3 or not _imposible(w):
            continue
        cands = [w[:i] + v + w[i:] for i in range(1, len(w)) for v in 'aeioun']
        cands = [c for c in cands if cnt.get(c, 0) >= min_frec and not _imposible(c)]
        if cands:
            mapeo[w] = max(cands, key=cnt.get)
    return mapeo

_MAPEO = None
def normalizar_tildes(s):
    """tb.normalizar + reemplazo de palabras sin vocal acentuada por su forma escrita sin tilde (aprendida del train)."""
    global _MAPEO
    if _MAPEO is None:
        d = next(x for x in tb.CANDIDATE_DIRS if os.path.exists(os.path.join(x, 'toxic_train.csv')))
        tr = pd.read_csv(os.path.join(d, 'toxic_train.csv'), sep=';', encoding='latin-1')
        _MAPEO = aprender_mapeo_tildes(tr['text'].astype(str).map(tb.normalizar))
    return re.sub(r'\b[a-z]+\b', lambda m: _MAPEO.get(m.group(), m.group()), tb.normalizar(s))
