"""E10d — Modelos de lenguaje de n-gramas por clase (Kneser-Ney modificado interpolado), entrenados por el equipo.

Idea: para cada etiqueta (HS, TR, AG) se ajusta un modelo de lenguaje con los tweets de la clase 1 y otro con los
de la clase 0 (en caracteres y en palabras). La variable de cada tweet es el cociente de log-verosimilitudes
normalizado por longitud (LLR = log P(texto | clase 1)/n - log P(texto | clase 0)/n). Una regresión logística
pequeña convierte las LLR en probabilidad. Para que la LR no vea LLR "en muestra" (los LM ya vieron esos tweets),
sus datos de entrenamiento se obtienen con una CV interna de 5 particiones dentro del fold.
Variante powerset: un LM por combinación HS-TR-AG y LR multinomial sobre las puntuaciones.

Kneser-Ney modificado interpolado (Chen y Goodman, 1999): descuentos D1, D2, D3+ por orden estimados con los
conteos de conteos; el orden superior usa frecuencias y los inferiores, número de contextos izquierdos distintos.
Idea de codificar cada palabra como un carácter Unicode tomada de TweetAge v6 (misma carpeta del repo).

Uso:
    import toxic_base as tb, ext_lm
    tb.oof(d, 'LM-KN', 42)       # registra los modelos 'LM-KN', 'LM-KN-char', 'LM-KN-word', 'LM-KN-PS', 'LM-KN+lex'
"""
import math, re
from collections import Counter, defaultdict
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
import toxic_base as tb

BOS, EOS, UNK = '\x02', '\x03', '\x01'
CHAR_N, WORD_N = 6, 3                    # orden máximo; se puntúa con todos los órdenes 1..N en una pasada
RE_TOK = re.compile(r'\w+|[^\w\s]')
N_INTERNA = 5                            # particiones de la CV interna para las LLR de entrenamiento de la LR


# ---------------------------------------------------------------------------------------------------
# Kneser-Ney modificado interpolado sobre cadenas (cada símbolo es un carácter; las palabras se codifican)
# ---------------------------------------------------------------------------------------------------
def _descuentos(tabla):
    h = Counter(tabla.values())
    n1, n2, n3, n4 = (h.get(i, 0) for i in (1, 2, 3, 4))
    if not (n1 and n2 and n3 and n4):
        return (0.5, 1.0, 1.5) if n1 else (0.75, 0.75, 0.75)
    Y = n1 / (n1 + 2 * n2)
    D = (1 - 2 * Y * n2 / n1, 2 - 3 * Y * n3 / n2, 3 - 4 * Y * n4 / n3)
    return tuple(min(b - 1e-3, max(1e-3, v)) for b, v in zip((1, 2, 3), D))

def _preparar(tabla, k):
    """Devuelve (tabla, D, stats) con stats[historia] = (total, masa retirada)."""
    D = _descuentos(tabla)
    tot, rem = defaultdict(float), defaultdict(float)
    for g, c in tabla.items():
        h = g[:k - 1]
        tot[h] += c
        rem[h] += D[min(c, 3) - 1]
    return tabla, D, {h: (tot[h], rem[h]) for h in tot}


class KN:
    def __init__(self, N, V):
        self.N, self.V = N, V            # V: tamaño del vocabulario (incluye EOS y UNK)

    def fit(self, seqs):
        N = self.N
        raw = {k: Counter() for k in range(1, N + 1)}
        for s in seqs:
            p = BOS * (N - 1) + s + EOS
            for i in range(N - 1, len(p)):
                for k in range(1, N + 1):
                    raw[k][p[i - k + 1:i + 1]] += 1
        cont = {}
        for k in range(1, N):
            c = Counter()
            for g in raw[k + 1]:
                c[g[1:]] += 1
            cont[k] = c
        self.raw = {k: _preparar(raw[k], k) for k in raw}
        self.cont = {k: _preparar(cont[k], k) for k in cont}
        return self

    @staticmethod
    def _nivel(T, h, w, p):
        tabla, D, st = T
        s = st.get(h)
        if s is None:
            return p
        c = tabla.get(h + w, 0)
        return ((c - D[min(c, 3) - 1]) if c else 0.0) / s[0] + s[1] / s[0] * p

    def logprob(self, s):
        """Log-probabilidad media por símbolo con cada orden 1..N -> array (N,)."""
        N, out = self.N, np.zeros(self.N)
        p_ = BOS * (N - 1) + s + EOS
        u = 1.0 / self.V
        for i in range(N - 1, len(p_)):
            w = p_[i]
            q = u                                          # cadena de continuaciones (órdenes inferiores)
            for k in range(1, N + 1):
                h = p_[i - k + 1:i]
                out[k - 1] += math.log(self._nivel(self.raw[k], h, w, q))
                if k < N:
                    q = self._nivel(self.cont[k], h, w, q)
        return out / (len(s) + 1)


def _codificador(textos, nivel):
    if nivel == 'char':
        voc = sorted({ch for t in textos for ch in t})
        m = {ch: ch for ch in voc}
        return (lambda t: ''.join(m.get(ch, UNK) for ch in t)), len(voc) + 2
    f = Counter(w for t in textos for w in RE_TOK.findall(t))
    voc = sorted(w for w, c in f.items() if c >= 2)
    m = {w: chr(256 + i) for i, w in enumerate(voc)}
    return (lambda t: ''.join(m.get(w, UNK) for w in RE_TOK.findall(t))), len(voc) + 2


def puntuaciones(ta, grupos_a, tb_, n_grupos, nivel):
    """ta: textos de ajuste; grupos_a: array (n_a, G) de enteros (grupo de cada texto para cada una de G
    agrupaciones, p. ej. etiqueta 0/1); tb_: textos a puntuar. Devuelve (n_b, G, n_grupos, N)."""
    enc, V = _codificador(ta, nivel)
    N = CHAR_N if nivel == 'char' else WORD_N
    ea, eb = [enc(t) for t in ta], [enc(t) for t in tb_]
    G = grupos_a.shape[1]
    S = np.full((len(eb), G, n_grupos, N), np.nan)
    for g in range(G):
        for c in range(n_grupos):
            sel = [e for e, v in zip(ea, grupos_a[:, g]) if v == c]
            if not sel:
                continue
            lm = KN(N, V).fit(sel)
            S[:, g, c] = [lm.logprob(e) for e in eb]
    return S


# ---------------------------------------------------------------------------------------------------
# Variables (LLR) con CV interna y modelos para toxic_base
# ---------------------------------------------------------------------------------------------------
_D = {}

def bloque_idx(d, idx_a, idx_b, cfg):
    """Columna con el número de fila: +i+1 para el train, -(i+1) para el test. Solo transporta índices."""
    _D['d'] = d
    ib = -(np.arange(len(d.TXT_TE)) + 1) if isinstance(idx_b, str) else np.asarray(idx_b) + 1
    return sparse.csr_matrix((np.asarray(idx_a) + 1).reshape(-1, 1).astype(float)), \
           sparse.csr_matrix(ib.reshape(-1, 1).astype(float))
tb.BLOQUES['idx'] = bloque_idx

def _textos_de(X):
    d = _D['d']
    ids = X[:, 0].toarray().ravel().astype(int)
    tr, te = d.TXT_TR.values, d.TXT_TE.values
    return [tr[i - 1] if i > 0 else te[-i - 1] for i in ids]


COMBOS = ['000', '001', '100', '101', '110', '111']
ORD_CHAR = (3, 4, 5, 6)      # órdenes usados como variables (índice = orden)
ORD_WORD = (1, 2, 3)

def _variables(ta, Ya, combo_a, tb_, modo, niveles):
    """Variables de los textos tb_ con LMs ajustados en ta. modo 'bin': LLR por etiqueta -> (n_b, 3, F);
    modo 'ps': puntuación centrada por combinación -> (n_b, 6*F)."""
    bloques = []
    for nivel in niveles:
        ords = ORD_CHAR if nivel == 'char' else ORD_WORD
        sel = [o - 1 for o in ords]
        if modo == 'bin':
            S = puntuaciones(ta, Ya, tb_, 2, nivel)[..., sel]            # (n, 3, 2, F)
            bloques.append(S[:, :, 1] - S[:, :, 0])                      # (n, 3, F)
        else:
            g = np.array([COMBOS.index(c) for c in combo_a])[:, None]
            S = puntuaciones(ta, g, tb_, len(COMBOS), nivel)[:, 0][..., sel]   # (n, 6, F)
            S = np.nan_to_num(S - np.nanmean(S, 1, keepdims=True), nan=-5.0)
            bloques.append(S.reshape(len(tb_), -1))
    return np.concatenate(bloques, -1)

def _variables_entrenamiento(ta, Ya, combo_a, modo, niveles):
    """Variables de los propios textos de ajuste, cada uno puntuado por LMs que no lo vieron (CV interna)."""
    out = None
    ta = np.asarray(ta, dtype=object)
    for itr, ite in StratifiedKFold(N_INTERNA, shuffle=True, random_state=0).split(ta, combo_a):
        F = _variables(list(ta[itr]), Ya[itr], combo_a[itr], list(ta[ite]), modo, niveles)
        if out is None:
            out = np.zeros((len(ta),) + F.shape[1:])
        out[ite] = F
    return out

def _lr():
    return LogisticRegression(C=1.0, max_iter=3000, class_weight='balanced')

def lm_fp(modo='bin', niveles=('char', 'word'), con_lex=False):
    def fp(Xa, Ya, combo_a, Xb, cfg):
        ta, tb_ = _textos_de(Xa), _textos_de(Xb)
        Fa = _variables_entrenamiento(ta, Ya, combo_a, modo, niveles)
        Fb = _variables(ta, Ya, combo_a, tb_, modo, niveles)
        if modo == 'bin':
            P = []
            for j in range(3):
                A, B = Fa[:, j], Fb[:, j]
                if con_lex:
                    A = np.hstack([A, Xa[:, 1:].toarray()]); B = np.hstack([B, Xb[:, 1:].toarray()])
                sc = StandardScaler().fit(A)
                P.append(_lr().fit(sc.transform(A), Ya[:, j]).predict_proba(sc.transform(B))[:, 1])
            return np.column_stack(P)
        sc = StandardScaler().fit(Fa)
        m = LogisticRegression(C=1.0, max_iter=3000).fit(sc.transform(Fa), combo_a)
        return tb.marginales(m.predict_proba(sc.transform(Fb)), m.classes_)
    return fp

tb.MODELOS['LM-KN'] = dict(bloques=['idx'], fit_predict=lm_fp('bin', ('char', 'word')))
tb.MODELOS['LM-KN-char'] = dict(bloques=['idx'], fit_predict=lm_fp('bin', ('char',)))
tb.MODELOS['LM-KN-word'] = dict(bloques=['idx'], fit_predict=lm_fp('bin', ('word',)))
tb.MODELOS['LM-KN-PS'] = dict(bloques=['idx'], fit_predict=lm_fp('ps', ('char', 'word')))
tb.MODELOS['LM-KN+lex'] = dict(bloques=['idx', 'lex'], fit_predict=lm_fp('bin', ('char', 'word'), con_lex=True))
