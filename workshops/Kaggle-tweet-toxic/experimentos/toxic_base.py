"""Pipeline común de TweetToxic, extraído de `TweetToxic_modelo.ipynb` (modelo base, Kaggle 0,79160).

Cada notebook de experimento (E0, E1, ...) importa este módulo y solo cambia la pieza que prueba.
Diferencias frente al notebook original:
- Validación cruzada repetida (varias semillas) para comparar configuraciones con media ± desviación.
- Caché en disco de las probabilidades OOF y de test por modelo (`oof/`), para que el stacking no reentrene todo.
- Registros extensibles de bloques de representación (`BLOQUES`) y modelos base (`MODELOS`).
"""
import os, re, html, json, hashlib, time, warnings
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import ComplementNB
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score

warnings.filterwarnings('ignore')

LABELS = ['HS', 'TR', 'AG']
SEEDS = (42, 43, 44)
N_FOLDS = 5
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
OOF_DIR = os.path.join(AQUI, 'oof')
SUB_DIR = os.path.join(AQUI, 'submissions')
SUB_BASE = os.path.join(RAIZ, 'toxic_submission.csv')        # stacking original, Kaggle público 0,79160
CANDIDATE_DIRS = [os.path.join(RAIZ, 'tweet-toxic-2026-puj'), os.path.join(RAIZ, 'data'), RAIZ,
                  '/kaggle/input/tweet-toxic-2026-puj']

# Configuración del notebook original
CFG_BASE = dict(
    C_LR=4.0, C_SVM=0.3, NB_ALPHA=1.0, PESO_LEX=0.3,
    WORD=dict(analyzer='word', ngram_range=(1, 2), min_df=2, sublinear_tf=True, token_pattern=r'(?u)\b\w+\b'),
    CHAR=dict(analyzer='char_wb', ngram_range=(2, 5), min_df=2, sublinear_tf=True),
    C_POR_ETIQUETA=None,      # p. ej. {'HS': 2.0, 'TR': 4.0, 'AG': 8.0} para la LR binaria (E7)
)
CLAVES_ORIGINALES = set(CFG_BASE) | {'_N_LEX'}

T0 = time.time()
def log(*m):
    print(f'[{time.time() - T0:6.0f}s]', *m, flush=True)


# ---------------------------------------------------------------------------------------------------
# Datos y normalización (idénticos al notebook original)
# ---------------------------------------------------------------------------------------------------
RE_ERROR_EXCEL = re.compile(r'^#\W*NOM(BRE|E)\?$')
RE_URL = re.compile(r'https?://\S+|www\.\S+')
RE_MENC = re.compile(r'@\w+')
RE_ALARG = re.compile(r'(.)\1{2,}')

def normalizar(s):
    s = html.unescape(str(s)).lower()
    s = RE_URL.sub(' xurl ', s)
    s = RE_MENC.sub(' xuser ', s)
    s = s.replace('"', ' ').replace('#', ' ')
    s = s.encode('ascii', 'ignore').decode()      # mismo borrado de tildes/ñ que sufrió el train
    s = RE_ALARG.sub(r'\1\1', s)
    return re.sub(r'\s+', ' ', s).strip()

PATRONES = {
    'insulto_fem':        r'\b(puta|perra|zorra|guarra|putita|perrita|zorrita)s?\b',
    'puta_intensificador': r'\b(la|una|de|ni|hasta la|su|que) puta (boca|madre|vez|mierda|idea|polla|gracia|cama|ama)\b'
                           r'|puta madre|que (te|lo|la|me|los) pari',
    'hijo_de_puta':       r'\bhijos? de (la |tu |su )?(gran |mil |re mil |re )?(puta|perra)',
    'hija_de_puta':       r'\bhijas? de (la |tu |su )?(gran |mil )?(puta|perra)',
    'insulto_masc':       r'\b(pendejo|cabro?n|subnormal|cerdo|imbe?cil|gilipollas|marico?n|puto|culiao|perro|mamo?n'
                          r'|rata|hijueputa|hdp|pelotudo|boludo|forro|idiota|est(u)?pido|payaso|ladro?n)\b',
    'blanco_masc':        r'\b(eres|sos|es) (el|un)\b|\b(maldito|traidor|hijo|wey|bro|hermano|amigo|viejo|tio|man|cabro?n'
                          r'|pendejo|marica|culiao|pelotudo|boludo)\b',
    'blanco_fem':         r'\b(eres|sos|es) (la|una)\b|\b(maldita|traidora|hija|amiga|vieja|pendeja|gorda|sucia|asquerosa'
                          r'|estu?pida|loca|tonta|barata)\b',
    'callate':            r'\bc(a)?llate|\bte calles\b|\bcallese\b',
    'trato_directo':      r'\bt(u)? eres\b|\beres (una|la|mi|un|muy|bien)\b|\bsos (una|la|re|muy|mi)\b|\bvos\b',
    'merecer':            r'merec',
    'insulto_grupo':      r'sudac|sudak|\bmoros?\b|moromierd|negrat|\bnegros?\b|manter|panchit|frijoler',
    'putos_grupo':        r'\bputos? (moros|negros|inmigrantes|sudacas|sudakas|negratas|arabes|rabes|refugiados|indocumentados)',
    'migracion':          r'inmigra|migrant|subsahar|ilegal|sin papeles|indocumentad|refugiad|\bvalla\b|patera|frontera|extranjer',
    'invasion_expulsion': r'invas|invad|plagad|masiv|efecto llamada|avalancha|expuls|deport|\bfuera\b|a su pa(i)?s|a sus casa',
    'arabe':              r'\b(a)?rabes?\b',
    'arabe_benigno':      r'(tema|cancio?n|ecko|empanad|comida|bail|escuch|falafel|tacos?|lomito|pan|mu?sica|curso|emiratos|coalicio?n)'
                          r'\W+(\w+\W+)?(a)?rabes?\b|\b(a)?rabes?\W+(\w+\W+)?(tema|cancio?n|ecko|empanad|unidos|israel)',
    'guero':              r'\bg(u)?er[oa]s?\b|\bg(u)?erit[oa]s?\b',
    'noticia_violencia':  r'acos|violaci|abuso',
    'comemela_semen':     r'comemel|\bsemen\b',
    'mujer_generica':     r'\bmujer(es)?\b|\bellas\b|feminaz|feminis|\btodas\b',
    'chiste':             r'^\W*(-\s*)?(por ?que?\b|que? (es|se|tiene|hace|hacen)\b|en que? se parece|c(o)?mo se dice|cu(a)?ndo)',
    'risa':               r'jaja|jeje|ajaj|jsjs|haha',
    'de_mierda':          r'\bde mierda\b',
}
RE_PAT = {k: re.compile(p) for k, p in PATRONES.items()}
LEX_NOMBRES = list(PATRONES) + ['fem_sin_intensificador', 'callate_con_fem', 'callate_sin_fem', 'masc_sin_fem',
                                'chiste_mujer', 'arabe_no_benigno', 'mencion_inicial', 'n_menciones', 'tiene_url',
                                'n_hashtags', 'comillas', 'prop_mayusculas', 'log_longitud', 'n_exclamaciones',
                                'n_preguntas']

def variables_lexicas(raw, norm):
    c = {k: len(RE_PAT[k].findall(norm)) for k in PATRONES}
    f = list(c.values())
    f += [
        int(c['insulto_fem'] > 0 and c['puta_intensificador'] == 0),
        int(c['callate'] > 0 and c['insulto_fem'] > 0),
        int(c['callate'] > 0 and c['insulto_fem'] == 0),
        int(c['insulto_masc'] > 0 and c['insulto_fem'] == 0),
        int(c['chiste'] > 0 and c['mujer_generica'] > 0),
        int(c['arabe'] > 0 and c['arabe_benigno'] == 0),
        int(bool(re.match(r'^\W*@', raw))),
        raw.count('@'),
        int('http' in raw),
        raw.count('#'),
        int('"' in raw),
        sum(ch.isupper() for ch in raw) / max(1, sum(ch.isalpha() for ch in raw)),
        np.log1p(len(raw)),
        raw.count('!'),
        raw.count('?'),
    ]
    return f


class Datos:
    """Train, test y todo lo que se deriva de ellos sin ajustar nada (texto normalizado y variables de léxico).

    extra_lex: lista de (nombre, función(raw: str, norm: str) -> list[float], nombres de columnas) que se
    agregan al bloque de léxico (p. ej. HurtLex en E5). Cambia la etiqueta `tag` para separar la caché.
    """
    def __init__(self, extra_lex=None, normalizador=normalizar):
        data_dir = next((d for d in CANDIDATE_DIRS if os.path.exists(os.path.join(d, 'toxic_train.csv'))), None)
        assert data_dir is not None, 'No encontré toxic_train.csv'
        self.data_dir = data_dir
        self.train = pd.read_csv(os.path.join(data_dir, 'toxic_train.csv'), sep=';', encoding='latin-1')
        self.test = pd.read_csv(os.path.join(data_dir, 'toxic_test.csv'), sep=';', encoding='latin-1')
        self.sample = pd.read_csv(os.path.join(data_dir, 'submission.csv'))
        for df in (self.train, self.test):
            df['text'] = df['text'].astype(str)
        self.train['id'] = pd.to_numeric(self.train['id'].astype(str).str.strip('"'))
        self.Y = self.train[LABELS].values
        self.COMBO = self.train[LABELS].astype(str).agg(''.join, axis=1).values
        self.TXT_TR = self.train['text'].map(normalizador)
        self.TXT_TE = self.test['text'].map(normalizador)
        self.lex_nombres = list(LEX_NOMBRES)
        self.L_TR = np.array([variables_lexicas(r, n) for r, n in zip(self.train['text'], self.TXT_TR)], float)
        self.L_TE = np.array([variables_lexicas(r, n) for r, n in zip(self.test['text'], self.TXT_TE)], float)
        self.tag = 'base' if normalizador is normalizar else f'norm-{normalizador.__name__}'
        for nombre, fn, cols in (extra_lex or []):
            self.L_TR = np.hstack([self.L_TR, np.array([fn(r, n) for r, n in zip(self.train['text'], self.TXT_TR)], float)])
            self.L_TE = np.hstack([self.L_TE, np.array([fn(r, n) for r, n in zip(self.test['text'], self.TXT_TE)], float)])
            self.lex_nombres += cols
            self.tag += f'+{nombre}'
        self.comillas_te = self.test['text'].str.contains('"', regex=False).values
        self.err_excel_te = self.test['text'].str.strip().str.match(RE_ERROR_EXCEL).values
        self.n = len(self.train)

    def folds(self, seed):
        return list(StratifiedKFold(N_FOLDS, shuffle=True, random_state=seed).split(self.TXT_TR, self.COMBO))


# ---------------------------------------------------------------------------------------------------
# Bloques de representación. Cada constructor recibe (datos, idx_a, idx_b, cfg), donde idx_b es un array de
# índices del train (partición de validación) o la cadena 'test'. Se ajusta SOLO con idx_a.
# ---------------------------------------------------------------------------------------------------
def _textos(d, idx_a, idx_b):
    ta = d.TXT_TR.iloc[idx_a]
    tb = d.TXT_TE if isinstance(idx_b, str) else d.TXT_TR.iloc[idx_b]
    return ta, tb

def _lex(d, idx_a, idx_b):
    return d.L_TR[idx_a], (d.L_TE if isinstance(idx_b, str) else d.L_TR[idx_b])

def bloque_tfidf(clave):
    def construir(d, idx_a, idx_b, cfg):
        ta, tb = _textos(d, idx_a, idx_b)
        v = TfidfVectorizer(**cfg[clave])
        return v.fit_transform(ta), v.transform(tb)
    return construir

def bloque_lex(d, idx_a, idx_b, cfg):
    la, lb = _lex(d, idx_a, idx_b)
    sc = StandardScaler()
    return (sparse.csr_matrix(sc.fit_transform(la) * cfg['PESO_LEX']),
            sparse.csr_matrix(sc.transform(lb) * cfg['PESO_LEX']))

BLOQUES = {'word': bloque_tfidf('WORD'), 'char': bloque_tfidf('CHAR'), 'lex': bloque_lex}
TODOS = ['word', 'char', 'lex']


def _hash(obj):
    return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:8]

def _hash_cfg(cfg):
    """Hash de la configuración sin las claves añadidas por experimentos posteriores (E3, E4...) mientras
    conserven su valor por defecto: así agregar un bloque nuevo no invalida la caché de los modelos anteriores."""
    return _hash({k: v for k, v in cfg.items() if k in CLAVES_ORIGINALES or v != CFG_BASE.get(k)})

_CACHE_BLOQUES = {}
def bloques(d, idx_a, idx_b, nombres, cfg, clave_particion):
    """Devuelve (Xa, Xb) concatenando los bloques pedidos; cada bloque se calcula una vez por partición."""
    A, B = [], []
    for b in nombres:
        k = (d.tag, b, _hash_cfg(cfg), clave_particion)
        if k not in _CACHE_BLOQUES:
            _CACHE_BLOQUES[k] = BLOQUES[b](d, idx_a, idx_b, cfg)
        a, bb = _CACHE_BLOQUES[k]
        A.append(a); B.append(bb)
    return sparse.hstack(A).tocsr(), sparse.hstack(B).tocsr()


# ---------------------------------------------------------------------------------------------------
# Modelos base. Cada modelo es dict(bloques=[...], fit_predict=fn(Xa, Ya, combo_a, Xb, cfg) -> P (n_b, 3)).
# ---------------------------------------------------------------------------------------------------
class NBLogReg(BaseEstimator, ClassifierMixin):
    """Regresión logística sobre n-gramas reponderados por el log-cociente de Naive Bayes (Wang & Manning, 2012).
    Las últimas n_lex columnas (bloque de léxico) no se reponderan."""
    def __init__(self, alpha=1.0, C=4.0, n_lex=0):
        self.alpha, self.C, self.n_lex = alpha, C, n_lex

    def fit(self, X, y):
        d = X.shape[1] - self.n_lex
        Xb = (X[:, :d] > 0).astype(float)
        p = self.alpha + Xb[y == 1].sum(0).A1
        q = self.alpha + Xb[y == 0].sum(0).A1
        r = np.log((p / p.sum()) / (q / q.sum()))
        self.r_ = np.concatenate([r, np.ones(self.n_lex)])
        self.clf_ = LogisticRegression(C=self.C, max_iter=5000, class_weight='balanced')
        self.clf_.fit(X.multiply(self.r_).tocsr(), y)
        self.classes_ = self.clf_.classes_
        return self

    def predict_proba(self, X):
        return self.clf_.predict_proba(X.multiply(self.r_).tocsr())


def por_etiqueta(fabrica):
    """Ajusta un clasificador binario por etiqueta; fabrica(cfg, j) devuelve un estimador nuevo."""
    def fp(Xa, Ya, combo_a, Xb, cfg):
        return np.column_stack([fabrica(cfg, j).fit(Xa, Ya[:, j]).predict_proba(Xb)[:, 1] for j in range(3)])
    return fp

def marginales(P_combo, clases):
    return np.column_stack([P_combo[:, [k for k, c in enumerate(clases) if c[j] == '1']].sum(1) for j in range(3)])

def powerset(Xa, Ya, combo_a, Xb, cfg):
    m = LogisticRegression(C=cfg['C_LR'], max_iter=5000).fit(Xa, combo_a)
    return marginales(m.predict_proba(Xb), m.classes_)

def _c_lr(cfg, j):
    return (cfg['C_POR_ETIQUETA'] or {}).get(LABELS[j], cfg['C_LR'])

MODELOS = {
    'CNB':      dict(bloques=['word', 'char'], fit_predict=por_etiqueta(lambda cfg, j: ComplementNB(alpha=0.3))),
    'LR':       dict(bloques=TODOS, fit_predict=por_etiqueta(
                    lambda cfg, j: LogisticRegression(C=_c_lr(cfg, j), max_iter=5000, class_weight='balanced'))),
    'SVM':      dict(bloques=TODOS, fit_predict=por_etiqueta(
                    lambda cfg, j: CalibratedClassifierCV(LinearSVC(C=cfg['C_SVM'], class_weight='balanced'),
                                                          cv=3, method='sigmoid'))),
    'NB-LR':    dict(bloques=TODOS, fit_predict=None),   # se completa abajo: necesita el número de columnas de léxico
    'Powerset': dict(bloques=TODOS, fit_predict=powerset),
}
def _nblr(Xa, Ya, combo_a, Xb, cfg, n_lex=None):
    return np.column_stack([NBLogReg(alpha=cfg['NB_ALPHA'], C=_c_lr(cfg, j), n_lex=cfg['_N_LEX'])
                            .fit(Xa, Ya[:, j]).predict_proba(Xb)[:, 1] for j in range(3)])
MODELOS['NB-LR']['fit_predict'] = _nblr
BASES_ORIGINALES = ['CNB', 'LR', 'SVM', 'NB-LR', 'Powerset']


def _cfg(d, cfg):
    c = dict(CFG_BASE if cfg is None else cfg)
    c['_N_LEX'] = d.L_TR.shape[1]
    return c

def _ruta(d, nombre, cfg, sufijo):
    carpeta = os.path.join(OOF_DIR, d.tag)
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, f'{nombre}_{_hash_cfg(cfg)}_{sufijo}.npy')

def oof(d, nombre, seed, cfg=None, cache=True):
    """Probabilidades fuera de muestra (n_train, 3) del modelo `nombre` con las particiones de `seed`."""
    cfg = _cfg(d, cfg)
    ruta = _ruta(d, nombre, cfg, f's{seed}')
    if cache and os.path.exists(ruta):
        return np.load(ruta)
    m = MODELOS[nombre]
    P = np.zeros((d.n, 3))
    for k, (tr, te) in enumerate(d.folds(seed)):
        Xa, Xb = bloques(d, tr, te, m['bloques'], cfg, (seed, k))
        P[te] = m['fit_predict'](Xa, d.Y[tr], d.COMBO[tr], Xb, cfg)
    if cache:
        np.save(ruta, P)
    return P

def pred_test(d, nombre, cfg=None, cache=True):
    """Probabilidades (n_test, 3) del modelo entrenado con TODO el train. El test solo se transforma."""
    cfg = _cfg(d, cfg)
    ruta = _ruta(d, nombre, cfg, 'test')
    if cache and os.path.exists(ruta):
        return np.load(ruta)
    m = MODELOS[nombre]
    Xa, Xb = bloques(d, np.arange(d.n), 'test', m['bloques'], cfg, 'test')
    P = m['fit_predict'](Xa, d.Y, d.COMBO, Xb, cfg)
    if cache:
        np.save(ruta, P)
    return P


# ---------------------------------------------------------------------------------------------------
# Stacking: metamodelo por etiqueta sobre las probabilidades OOF de los modelos base.
# ---------------------------------------------------------------------------------------------------
def meta_lr():
    return LogisticRegression(C=1.0, max_iter=3000, class_weight='balanced')

def stacking(d, bases, seed, cfg=None, meta=meta_lr, extra_tr=None, extra_te=None, cfgs=None, con_test=True):
    """Devuelve (P_oof, P_test). P_oof se evalúa con otra CV (semilla seed+1) sobre los OOF de los modelos base.

    cfgs: dict opcional nombre_base -> cfg propia. extra_tr/extra_te: variables adicionales para el metamodelo.
    """
    cfgs = cfgs or {}
    Z = np.hstack([oof(d, b, seed, cfgs.get(b, cfg)) for b in bases])
    if extra_tr is not None:
        sc = StandardScaler().fit(extra_tr)
        Z = np.hstack([Z, sc.transform(extra_tr)])
    P = np.zeros((d.n, 3))
    for tr, te in StratifiedKFold(N_FOLDS, shuffle=True, random_state=seed + 1).split(Z, d.COMBO):
        for j in range(3):
            P[te, j] = meta().fit(Z[tr], d.Y[tr, j]).predict_proba(Z[te])[:, 1]
    if not con_test:
        return P, None
    Zt = np.hstack([pred_test(d, b, cfgs.get(b, cfg)) for b in bases])
    if extra_te is not None:
        Zt = np.hstack([Zt, sc.transform(extra_te)])
    Pt = np.column_stack([meta().fit(Z, d.Y[:, j]).predict_proba(Zt)[:, 1] for j in range(3)])
    return P, Pt


# ---------------------------------------------------------------------------------------------------
# Métricas, umbrales y reporte
# ---------------------------------------------------------------------------------------------------
UMBRAL_GRID = np.round(np.arange(0.20, 0.701, 0.02), 2)

def binarizar(P, umbrales=(0.5, 0.5, 0.5)):
    Yp = (P >= np.asarray(umbrales)).astype(int)
    Yp[:, 1] *= Yp[:, 0]                       # restricción jerárquica TR ⊂ HS
    return Yp

def metricas(Y, Yp):
    f1b = [f1_score(Y[:, j], Yp[:, j]) for j in range(3)]
    f1m = [f1_score(Y[:, j], Yp[:, j], average='macro') for j in range(3)]
    return {**{f'F1 {l}': v for l, v in zip(LABELS, f1b)}, 'F1 medio': np.mean(f1b),
            'F1 micro': f1_score(Y, Yp, average='micro'), 'F1-macro 2 clases': np.mean(f1m),
            'EMR': (Yp == Y).all(1).mean()}

def umbrales_optimos(Y, P, idx, grid=UMBRAL_GRID):
    return np.array([max(grid, key=lambda t: f1_score(Y[idx, j], (P[idx, j] >= t).astype(int))) for j in range(3)])

def umbrales_anidados(d, P, seed, grid=UMBRAL_GRID):
    """Predicciones con umbrales elegidos en las otras particiones (estimación honesta)."""
    Yp = np.zeros_like(d.Y)
    for tr, te in d.folds(seed):
        Yp[te] = binarizar(P[te], umbrales_optimos(d.Y, P, tr, grid))
    return Yp

def resumir(filas_por_seed):
    """filas_por_seed: lista de dicts de `metricas` (una por semilla) -> dict con media y desviación."""
    df = pd.DataFrame(filas_por_seed)
    out = {}
    for c in df.columns:
        out[c] = df[c].mean()
        out[c + ' ±'] = df[c].std(ddof=0)
    out['por semilla'] = ' / '.join(f'{v:.3f}' for v in df['F1 medio'])
    return out

def tabla(resultados):
    """resultados: dict nombre -> dict de `resumir`. Muestra F1 por etiqueta, F1 medio ± desviación y EMR."""
    filas = []
    for nombre, r in resultados.items():
        filas.append({'Configuración': nombre, 'F1 HS': r['F1 HS'], 'F1 TR': r['F1 TR'], 'F1 AG': r['F1 AG'],
                      'F1 medio': r['F1 medio'], '±': r['F1 medio ±'], 'EMR': r['EMR'],
                      'F1 medio por semilla': r['por semilla']})
    return pd.DataFrame(filas).set_index('Configuración').round(4)

def evaluar(d, P_por_seed, umbrales=(0.5, 0.5, 0.5), post=None):
    """P_por_seed: dict seed -> P_oof. post(Yp) opcional para reglas posteriores sobre el train."""
    filas = []
    for s, P in P_por_seed.items():
        Yp = binarizar(P, umbrales)
        if post is not None:
            Yp = post(Yp)
        filas.append(metricas(d.Y, Yp))
    return resumir(filas)

def evaluar_anidado(d, P_por_seed, grid=UMBRAL_GRID):
    return resumir([metricas(d.Y, umbrales_anidados(d, P, s, grid)) for s, P in P_por_seed.items()])


# ---------------------------------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------------------------------
def guardar_submission(d, Y_test, nombre):
    """Aplica las reglas fijas (TR ⊂ HS, #¿NOMBRE? -> 000), valida el formato y compara con la base 0,79160."""
    Y_test = Y_test.copy()
    Y_test[:, 1] *= Y_test[:, 0]
    Y_test[d.err_excel_te] = 0
    pred = pd.DataFrame(Y_test, columns=LABELS)
    pred.insert(0, 'id', d.test['id'].values)
    sub = d.sample[['id']].merge(pred, on='id', how='left')
    assert list(sub.columns) == list(d.sample.columns) == ['id', 'HS', 'TR', 'AG']
    assert len(sub) == len(d.sample) == len(d.test)
    assert set(sub['id']) == set(d.test['id'])
    assert sub[LABELS].notna().all().all() and sub[LABELS].isin([0, 1]).all().all()
    assert not ((sub.TR == 1) & (sub.HS == 0)).any()
    sub[LABELS] = sub[LABELS].astype(int)
    os.makedirs(SUB_DIR, exist_ok=True)
    ruta = os.path.join(SUB_DIR, nombre)
    sub.to_csv(ruta, index=False)
    base = pd.read_csv(SUB_BASE).set_index('id').loc[sub['id']]
    cambios = {l: int((base[l].values != sub[l].values).sum()) for l in LABELS}
    filas_cambiadas = int((base[LABELS].values != sub[LABELS].values).any(1).sum())
    log(f'Guardada {ruta}')
    print('Prevalencia train :', dict(zip(LABELS, d.Y.mean(0).round(3))))
    print('Prevalencia pred. :', dict(zip(LABELS, sub[LABELS].mean().round(3).values)))
    print(f'Cambios frente a la base 0,79160: {filas_cambiadas} filas ({cambios})')
    return sub


# ===================================================================================================
# E3 — Modelos base nuevos para dar diversidad al stacking
# ===================================================================================================
from sklearn.decomposition import TruncatedSVD
from sklearn.multioutput import ClassifierChain

CFG_BASE['CHAR_C'] = dict(analyzer='char', ngram_range=(2, 6), min_df=2, sublinear_tf=True, max_features=60000)
BLOQUES['charc'] = bloque_tfidf('CHAR_C')      # n-gramas de caracteres que cruzan palabras ('xuser callate p')

def bloque_svd(d, idx_a, idx_b, cfg):
    """TF-IDF de palabras + caracteres reducido a 300 dimensiones (denso), para modelos de árboles."""
    ta, tb_ = _textos(d, idx_a, idx_b)
    vw, vc = TfidfVectorizer(**cfg['WORD']), TfidfVectorizer(**cfg['CHAR'])
    Xa = sparse.hstack([vw.fit_transform(ta), vc.fit_transform(ta)]).tocsr()
    Xb = sparse.hstack([vw.transform(tb_), vc.transform(tb_)]).tocsr()
    svd = TruncatedSVD(300, random_state=0)
    return sparse.csr_matrix(svd.fit_transform(Xa)), sparse.csr_matrix(svd.transform(Xb))
BLOQUES['svd'] = bloque_svd

def bloque_lex_crudo(d, idx_a, idx_b, cfg):
    la, lb = _lex(d, idx_a, idx_b)
    return sparse.csr_matrix(la), sparse.csr_matrix(lb)
BLOQUES['lexraw'] = bloque_lex_crudo

def _lgbm(seed=0):
    import lightgbm as lgb
    return lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=10,
                              subsample=0.8, subsample_freq=1, colsample_bytree=0.5, reg_lambda=1.0,
                              class_weight='balanced', random_state=seed, verbose=-1)

def lgbm_fp(Xa, Ya, combo_a, Xb, cfg):
    Xa, Xb = Xa.toarray(), Xb.toarray()
    return np.column_stack([_lgbm().fit(Xa, Ya[:, j]).predict_proba(Xb)[:, 1] for j in range(3)])

def cadena_fp(Xa, Ya, combo_a, Xb, cfg):
    """Cadena HS -> AG -> TR: cada etiqueta usa las anteriores como variables (reales al entrenar, predichas al predecir)."""
    cc = ClassifierChain(LogisticRegression(C=cfg['C_LR'], max_iter=5000, class_weight='balanced'), order=[0, 2, 1])
    return cc.fit(Xa, Ya).predict_proba(Xb)

MODELOS['NB-LR-charc'] = dict(bloques=['word', 'charc', 'lex'], fit_predict=_nblr)
MODELOS['LR-charc'] = dict(bloques=['word', 'charc', 'lex'], fit_predict=MODELOS['LR']['fit_predict'])
MODELOS['LGBM'] = dict(bloques=['svd', 'lexraw'], fit_predict=lgbm_fp)
MODELOS['Cadena'] = dict(bloques=TODOS, fit_predict=cadena_fp)


# ===================================================================================================
# E5 — Variables del léxico HurtLex (Bassignana, Basile y Patti, 2018), español v1.2, licencia CC BY-NC-SA 4.0
# https://github.com/valeriobasile/hurtlex
# ===================================================================================================
HURTLEX_CATEGORIAS = {
    'ps': 'estereotipos étnicos', 'rci': 'lugares y gentilicios', 'pa': 'profesiones', 'ddf': 'discapacidad física',
    'ddp': 'discapacidad cognitiva', 'dmc': 'defectos morales', 'is': 'desventaja social', 'or': 'plantas',
    'an': 'animales', 'asm': 'genitales masculinos', 'asf': 'genitales femeninos', 'pr': 'prostitución',
    'om': 'homosexualidad', 'qas': 'connotación negativa', 'cds': 'despectivos', 're': 'delitos',
    'svp': 'pecados capitales',
}

def hurtlex_variables(ruta=os.path.join(AQUI, 'recursos', 'hurtlex_ES.tsv')):
    """Devuelve el tuple (nombre, función, columnas) que espera `Datos(extra_lex=[...])`.

    Las entradas del léxico pasan por la misma `normalizar` que los tweets: así 'cállate' en HurtLex se
    convierte en 'cllate', igual que en el corpus (donde se borraron los caracteres no ASCII).
    Se cuentan apariciones por categoría (con plural opcional) y el total del nivel 'conservative'.
    """
    lx = pd.read_csv(ruta, sep='\t')
    lx['norm'] = lx['lemma'].map(normalizar)
    lx = lx[lx['norm'].str.len() >= 3].drop_duplicates(['norm', 'category'])
    def regex(palabras):
        alt = '|'.join(sorted({re.escape(p) for p in palabras}, key=len, reverse=True))
        return re.compile(rf'\b(?:{alt})(?:s|es)?\b')
    re_cat = {c: regex(lx.loc[lx.category == c, 'norm']) for c in HURTLEX_CATEGORIAS}
    re_cons = regex(lx.loc[lx.level == 'conservative', 'norm'])
    cols = [f'hurtlex_{c}' for c in HURTLEX_CATEGORIAS] + ['hurtlex_conservador']
    def fn(raw, norm):
        return [len(re_cat[c].findall(norm)) for c in HURTLEX_CATEGORIAS] + [len(re_cons.findall(norm))]
    return ('hurtlex', fn, cols)


# ===================================================================================================
# E4 — Word2Vec entrenado por el equipo (gensim), solo con los textos de la partición de entrenamiento
# ===================================================================================================
CFG_BASE['W2V'] = dict(vector_size=100, window=5, min_count=2, sg=1, epochs=40, seed=0, workers=1)
RE_TOKEN = re.compile(r'\b\w+\b')

def bloque_w2v(d, idx_a, idx_b, cfg):
    """Promedio y máximo de los vectores de las palabras de cada tweet (200 dims, estandarizado).
    El Word2Vec se ajusta con idx_a únicamente (sin test ni partición de validación)."""
    from gensim.models import Word2Vec
    ta, tb_ = _textos(d, idx_a, idx_b)
    toks_a = [RE_TOKEN.findall(t) for t in ta]
    toks_b = [RE_TOKEN.findall(t) for t in tb_]
    w2v = Word2Vec(sentences=toks_a, **cfg['W2V'])
    kv, dim = w2v.wv, cfg['W2V']['vector_size']
    def emb(toks):
        V = [kv[w] for w in toks if w in kv]
        if not V:
            return np.zeros(2 * dim)
        V = np.array(V)
        return np.concatenate([V.mean(0), V.max(0)])
    Ea = np.array([emb(t) for t in toks_a]); Eb = np.array([emb(t) for t in toks_b])
    sc = StandardScaler().fit(Ea)
    return sparse.csr_matrix(sc.transform(Ea)), sparse.csr_matrix(sc.transform(Eb))
BLOQUES['w2v'] = bloque_w2v

MODELOS['LR-w2v'] = dict(bloques=['w2v', 'lex'], fit_predict=por_etiqueta(
    lambda cfg, j: LogisticRegression(C=0.1, max_iter=5000, class_weight='balanced')))
MODELOS['LR-w2v+tfidf'] = dict(bloques=['word', 'char', 'lex', 'w2v'], fit_predict=MODELOS['LR']['fit_predict'])


# ===================================================================================================
# E6 — Seed bagging: promediar los modelos base de varias particiones antes del stacking
# ===================================================================================================
def pred_test_folds(d, nombre, seed, cfg=None, cache=True):
    """Promedio de las predicciones sobre el test de los 5 modelos de partición de `seed` (cada uno entrenado
    con 4/5 del train). Es la contraparte en test de los OOF: misma cantidad de datos por modelo."""
    cfg = _cfg(d, cfg)
    ruta = _ruta(d, nombre, cfg, f'testfolds_s{seed}')
    if cache and os.path.exists(ruta):
        return np.load(ruta)
    m = MODELOS[nombre]
    Ps = []
    for k, (tr, te) in enumerate(d.folds(seed)):
        Xa, Xt = bloques(d, tr, 'test', m['bloques'], cfg, (seed, k, 'test'))
        Ps.append(m['fit_predict'](Xa, d.Y[tr], d.COMBO[tr], Xt, cfg))
    P = np.mean(Ps, 0)
    if cache:
        np.save(ruta, P)
    return P

def stacking_bagged(d, bases, seeds_bases, seed_meta, meta=meta_lr, cfg=None, con_test=True):
    """Stacking sobre los OOF promediados en `seeds_bases`. El metamodelo se evalúa con la CV de `seed_meta`+1.
    En test, cada base aporta el promedio de sus modelos de partición (5 × len(seeds_bases) modelos)."""
    Z = np.hstack([np.mean([oof(d, b, s, cfg) for s in seeds_bases], 0) for b in bases])
    P = np.zeros((d.n, 3))
    for tr, te in StratifiedKFold(N_FOLDS, shuffle=True, random_state=seed_meta + 1).split(Z, d.COMBO):
        for j in range(3):
            P[te, j] = meta().fit(Z[tr], d.Y[tr, j]).predict_proba(Z[te])[:, 1]
    if not con_test:
        return P, None
    Zt = np.hstack([np.mean([pred_test_folds(d, b, s, cfg) for s in seeds_bases], 0) for b in bases])
    Pt = np.column_stack([meta().fit(Z, d.Y[:, j]).predict_proba(Zt)[:, 1] for j in range(3)])
    return P, Pt
