# -*- coding: utf-8 -*-
"""
TweetAge v3 – NB-SVM + familias nuevas de variables + selector de variables en tres niveles
==========================================================================================
Curso de Procesamiento del Lenguaje Natural · Maestría en Inteligencia Artificial · PUJ

Sin modelos preentrenados: todo se aprende desde cero con age_train.csv.

Flujo
-----
1. Nivel base: NB-SVM sobre TF-IDF de palabras 1-3, caracteres 2-5 (char_wb) y 1-5 (char).
   Sus puntuaciones se calculan FUERA DE MUESTRA (validación cruzada) para usarlas como variables.
2. Diez familias de variables candidatas (G0-G9), cada una con su sustento bibliográfico (ver REFERENCIAS al final).
3. Selector de variables en tres niveles:
   - Nivel 1, filtro: varianza casi nula, información mutua y redundancia (|rho de Spearman| > 0,9).
   - Nivel 2, wrapper: selección secuencial hacia adelante por FAMILIAS; una familia entra solo si
     sube el F1 macro en al menos 0,001 en una partición interna.
   - Nivel 3: meta-modelo (gradient boosting) con NB-SVM + familias elegidas, evaluado una sola vez
     en la validación reservada, e importancia por permutación de cada familia.
4. Modelo final con todo el train y archivo de submission.

Resultados obtenidos en validación (holdout estratificado 80/20, semilla 42)
---------------------------------------------------------------------------
  NB-SVM solo ............................................. F1 macro 0,5810
  Meta regresión logística: NB-SVM + todas las familias .... 0,5973
  Meta regresión logística: NB-SVM + familias elegidas ...... 0,5965
  Meta gradient boosting: NB-SVM + familias elegidas ........ 0,6075   <- modelo final
  El wrapper eligió solo G6 (homofilia de red): +0,015 en la partición interna.
  Las demás familias aportaron < 0,001 cada una y quedaron fuera.

Uso
---
    python tweetage_v3_selector.py
Requisitos: numpy, pandas, scipy, scikit-learn (>= 1.2). Memoria recomendada: 8 GB o más.
Tiempo aproximado: 25-40 min con VALIDAR=True; 12-20 min con VALIDAR=False.
"""
import os, re, sys, math, zlib, html, time, json, gc, warnings
from collections import Counter
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import VarianceThreshold, mutual_info_classif
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score, classification_report

warnings.filterwarnings('ignore')

# =====================================================================================
# CONFIGURACIÓN
# =====================================================================================
VALIDAR       = True     # True: reporta el F1 en un holdout 80/20 antes del modelo final
SAMPLE_FRAC   = None     # p. ej. 0.1 para una prueba rápida del código
SEED          = 42
K_FOLDS       = 3        # particiones para las variables fuera de muestra
NB_ALPHA, SVM_C = 1.0, 0.3
MIN_GANANCIA  = 0.001    # ganancia mínima de F1 macro para que una familia entre (nivel 2)
OUT_PATH      = 'age_submission_v3.csv'

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
CANDIDATE_DIRS = [HERE, os.getcwd(), os.path.join(HERE, 'data'),
                  r'/kaggle/input/tweet-age-2026-puj', r'C:\Users\leonk\Documents\MINTA 2025-01\PLN']
DATA_DIR = next((d for d in CANDIDATE_DIRS if os.path.exists(os.path.join(d, 'age_train.csv'))), None)
if DATA_DIR is None:
    sys.exit('No encontré age_train.csv. Ponga los CSV junto a este script o agregue su carpeta a CANDIDATE_DIRS.')

GROUPS = ['13-17', '18-24', '25-34', '35-49', '50-64', '65-xx']
T0 = time.time()
def log(*m): print(f'[{time.time() - T0:6.0f}s]', *m, flush=True)

# =====================================================================================
# DATOS
# =====================================================================================
def load(path):
    df = pd.read_csv(path, sep=';', encoding='utf-8-sig', dtype=str, keep_default_na=False)
    df['text'] = df['text'].str.strip().map(html.unescape)
    return df

def is_junk(texts):
    t = pd.Series(texts)
    return ((t == '') | t.str.contains('#¿NOMBRE', regex=False)).values

# =====================================================================================
# NIVEL BASE: NB-SVM (Wang & Manning, 2012)
# =====================================================================================
def make_vectorizers():
    return [TfidfVectorizer(token_pattern=r'(?u)[@#]?\w+', ngram_range=(1, 3), min_df=2, sublinear_tf=True, dtype=np.float32),
            TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 5), min_df=3, lowercase=False, sublinear_tf=True, dtype=np.float32),
            TfidfVectorizer(analyzer='char', ngram_range=(1, 5), min_df=5, lowercase=False, sublinear_tf=True, dtype=np.float32)]

def nbsvm_scores(Xfit, yfit, Xapp):
    """Entrena un SVM binario por clase sobre columnas escaladas por el log-cociente de NB y devuelve puntuaciones."""
    D = np.zeros((Xapp.shape[0], len(GROUPS)), np.float32)
    for i, c in enumerate(GROUPS):
        pos = yfit == c
        p = np.asarray(Xfit[pos].sum(0)).ravel() + NB_ALPHA
        q = np.asarray(Xfit[~pos].sum(0)).ravel() + NB_ALPHA
        R = sparse.diags(np.log((p / p.sum()) / (q / q.sum())).astype(np.float32))
        D[:, i] = LinearSVC(C=SVM_C).fit(Xfit @ R, pos.astype(int)).decision_function(Xapp @ R)
    return D

# =====================================================================================
# FAMILIAS DE VARIABLES
# =====================================================================================
def _rx(words): return r'\b(?:' + '|'.join(sorted(words, key=len, reverse=True)) + r')\b'

# --- G0. Estilo y legibilidad de la versión 1 (Moreno-Sandoval et al., 2021; Szigriszt Pazos, 1993; Fernández Huerta, 1959)
PRON_V1 = {'p1s': r'\b(?:yo|me|mi|mis|conmigo)\b', 'p2s_tu': r'\b(?:tu|tus|te|ti|contigo)\b', 'p2s_vos': r'\bvos\b',
           'p2s_ud': r'\b(?:usted|ud|uds|ustedes)\b', 'p1p': r'\b(?:nosotros|nosotras|nos|nuestro|nuestra|nuestros|nuestras)\b',
           'p3s': r'\b(?:el|ella|le|lo|la|su|sus)\b', 'p3p': r'\b(?:ellos|ellas|les|los)\b'}
def g0_estilo(texts):
    s = pd.Series(texts).reset_index(drop=True); low = s.str.lower(); w = low.str.findall(r'[a-z]+'); f = pd.DataFrame(index=s.index)
    f['len'] = s.str.len(); f['n_words'] = s.str.split().str.len().fillna(0)
    f['avg_wlen'] = w.apply(lambda x: np.mean([len(t) for t in x]) if x else 0); f['truncado'] = (f['len'] >= 135).astype(int)
    for k, p in PRON_V1.items(): f[k] = low.str.count(p)
    f['n_hashtag'] = s.str.count(r'#\w+'); f['n_mention'] = s.str.count(r'@\w+'); f['n_url'] = s.str.count(r'https?://')
    f['rt'] = s.str.startswith('RT @').astype(int); f['respuesta'] = s.str.match(r'^@\w').astype(int)
    f['risa'] = low.str.contains(r'(?:ja){2,}|(?:je){2,}|jsjs|\bxd+\b').astype(int)
    f['alarg'] = low.str.contains(r'([a-z])\1{2,}').astype(int)
    f['mayus_ratio'] = s.apply(lambda x: sum(c.isupper() for c in x) / max(1, sum(c.isalpha() for c in x)))
    clean = s.str.replace(r'https?://\S+|@\w+|#\w+|^RT\b', ' ', regex=True); ws = clean.str.lower().str.findall(r'[a-z]+')
    syl = ws.apply(lambda x: sum(max(1, len(re.findall(r'[aeiouy]+', t))) for t in x)); nw = ws.str.len().clip(lower=1)
    nf = clean.str.count(r'[.!?]+').clip(lower=1)
    f['szigriszt'] = 206.835 - 62.3 * (syl / nw) - (nw / nf)
    f['fernandez_huerta'] = 206.84 - 0.60 * (syl / nw * 100) - 1.02 * (nf / nw * 100)
    f['pocas_palabras'] = (ws.str.len() < 3).astype(int)
    return f.astype(np.float32)

# --- G1. Etapa del ciclo vital (Eckert, 1997; Schler et al., 2006; Nguyen et al., 2013)
CICLO = {'cv_colegio': ['colegio','cole','profe','profes','tarea','tareas','examen','examenes','recreo','clase','clases','salon',
                        'bachillerato','icfes','grado','prom','mis papas','mi mama','mi papa'],
         'cv_univ': ['universidad','uni','semestre','parcial','parciales','tesis','carrera','facultad','pregrado','practicas','beca','matricula'],
         'cv_trabajo': ['trabajo','trabajar','oficina','jefe','reunion','cliente','clientes','empresa','sueldo','salario','contrato',
                        'empleo','turno','quincena','proyecto','gerente','negocio'],
         'cv_familia': ['mi hijo','mi hija','mis hijos','mis hijas','esposa','esposo','mi marido','mi mujer','bebe','embarazo','familia','hogar'],
         'cv_mayor': ['nietos','nieto','nieta','nietas','pension','pensionado','pensionados','jubilado','jubilacion','abuelo','abuela',
                      'medico','salud','tension','misa','rosario']}
# --- G2. Categorías psicológicas tipo LIWC (Pennebaker et al., 2015; Ramírez-Esparza et al., 2007; Schwartz et al., 2013)
PSICO = {'ps_pos': ['feliz','felices','alegria','amo','amor','genial','gracias','bonito','bonita','hermoso','hermosa','lindo','linda',
                    'excelente','mejor','encanta','increible','buenisimo','divino'],
         'ps_neg': ['triste','odio','miedo','rabia','dolor','llorar','lloro','mal','peor','horrible','asco','cansado','cansada',
                    'aburrido','aburrida','depre','estres','muerte'],
         'ps_religion': ['dios','bendiciones','bendicion','amen','senor','jesus','virgen','iglesia','fe','orar','oracion','cristo'],
         'ps_politica': ['gobierno','presidente','paz','farc','eln','santos','uribe','maduro','chavez','petro','congreso','senado',
                         'corrupcion','elecciones','votar','oposicion','pueblo','patria','regimen','dictadura','ley'],
         'ps_dinero': ['plata','dinero','pesos','precio','pagar','compra','comprar','venta','vender','dolar','bolivares','impuestos'],
         'ps_deporte': ['gol','partido','futbol','seleccion','equipo','nacional','millonarios','junior','barcelona','madrid','messi','liga','mundial'],
         'ps_ocio': ['cancion','musica','concierto','video','serie','pelicula','peli','fiesta','rumba','album','netflix','juego','jugar','fan','fans','tour'],
         'ps_groseria': ['marica','gonorrea','hp','hpta','mierda','puta','puto','verga','carajo','joda','jueputa','malparido','culo']}
# --- G3. Jerga generacional e informalidad (Rao et al., 2010; Eisenstein, 2013)
JERGA = ['parce','parcero','ome','bro','wey','we','ahre','nmms','alv','lol','omg','omfg','bae','crush','stan','ship','tqm','tkm','ntp',
         'xfa','plis','pls','porfa','obvio','literal','cringe','random','fail','oki','okis','chimba','bacano','bacana','gomelo','severo',
         'berraco','mor','amix','amigui']
RISAS = {'r_jaja': r'\b(?:j+a+){2,}j*\b', 'r_jsjs': r'\b(?:js){2,}j?\b|\bjsj\w*', 'r_jeje': r'\b(?:j+e+){2,}j*\b',
         'r_xd': r'\bx+d+\b', 'r_haha': r'\b(?:h+a+){2,}h*\b|\blo+l\b', 'r_jiji': r'\b(?:j+i+){2,}j*\b'}
# --- G4. Morfología y formalidad (Biber, 1988; Heylighen & Dewaele, 2002; Argamon et al., 2009)
ARTIC = ['el','la','los','las','un','una','unos','unas','lo','al','del']
PREP  = ['a','ante','bajo','con','contra','de','desde','durante','en','entre','hacia','hasta','mediante','para','por','segun','sin','sobre','tras']
PRON  = ['yo','tu','vos','usted','el','ella','nosotros','ellos','ellas','me','te','se','nos','le','les','mi','mis','ti','conmigo','contigo','uds','ud','ustedes']
INTERJ= ['ay','uy','oh','ah','eh','wow','guau','uf','bah','ojala','hola','chao','vale','ok','okay','si','no']

def _entropy(seq):
    if not seq: return 0.0
    c = Counter(seq); n = len(seq)
    return -sum(v / n * math.log2(v / n) for v in c.values())

def label_free_families(texts):
    """G0-G5: variables que no usan etiquetas."""
    s = pd.Series(texts).reset_index(drop=True).fillna(''); low = s.str.lower()
    clean = low.str.replace(r'https?://\S+', ' ', regex=True)
    words = clean.str.replace(r'[@#]\w+', ' ', regex=True).str.findall(r'[a-z]+'); nw = words.str.len().clip(lower=1)
    G = {'G0_estilo_base': g0_estilo(s)}
    G['G1_ciclo_vital'] = pd.DataFrame({k: clean.str.count(_rx(v)) / nw for k, v in CICLO.items()})
    G['G2_psicologicas'] = pd.DataFrame({k: clean.str.count(_rx(v)) / nw for k, v in PSICO.items()})
    g3 = pd.DataFrame({'jerga': clean.str.count(_rx(JERGA)) / nw})
    for k, p in RISAS.items(): g3[k] = clean.str.contains(p, regex=True).astype(np.float32)
    g3['k_por_qu'] = clean.str.count(r'\bk\b|\bke\b|\bkien\b|\bkiero\w*') / nw
    g3['x_por_por'] = clean.str.count(r'\bx\b|\bxq\b|\bxfa\b') / nw
    g3['hashtag_camel'] = s.str.count(r'#[A-Z][a-z]+[A-Z]\w*'); g3['hashtag_mayus'] = s.str.count(r'#[A-Z0-9]{3,}\b')
    g3['corazon'] = s.str.count(r'<3+'); g3['repite_signo'] = s.str.count(r'([!?.])\1{2,}')
    G['G3_jerga_informalidad'] = g3
    def ratio(pat): return words.apply(lambda w: sum(bool(re.search(pat, x)) for x in w)) / nw
    g4 = pd.DataFrame({'suf_cion': ratio(r'(?:cion|sion)(?:es)?$'), 'suf_dad': ratio(r'dad(?:es)?$'), 'suf_mente': ratio(r'mente$'),
                       'gerundio': ratio(r'(?:ando|iendo|yendo)$'), 'participio': ratio(r'(?:ado|ido|ada|ida)s?$'),
                       'diminutivo': ratio(r'(?:it|ic|ill)[oa]s?$'), 'superlat': ratio(r'isim[oa]s?$'), 'infinitivo': ratio(r'[aei]r$')})
    art, prep = clean.str.count(_rx(ARTIC)) / nw, clean.str.count(_rx(PREP)) / nw
    pron, inter = clean.str.count(_rx(PRON)) / nw, clean.str.count(_rx(INTERJ)) / nw
    g4['articulos'], g4['preposiciones'], g4['pronombres'], g4['interjecciones'] = art, prep, pron, inter
    g4['formalidad_F'] = (art + prep - pron - inter + 1) / 2
    G['G4_morfologia_formalidad'] = g4
    joined = words.str.join(' ')
    G['G5_complejidad'] = pd.DataFrame({
        'entropia_car': s.map(_entropy), 'entropia_pal': words.map(lambda w: _entropy(w) if w else 0.0),
        'compresion': s.map(lambda x: len(zlib.compress(x.encode())) / max(1, len(x.encode())) if x else 0.0),
        'pal_largas': words.apply(lambda w: sum(len(x) >= 7 for x in w)) / nw,
        'ttr_car': s.map(lambda x: len(set(x)) / max(1, len(x))),
        'vocales_ratio': joined.map(lambda x: sum(c in 'aeiou' for c in x) / max(1, len(x.replace(' ', ''))))})
    return {k: v.astype(np.float32).reset_index(drop=True) for k, v in G.items()}

# --- G6. Homofilia de red: edad típica de quienes mencionan cada @cuenta o #hashtag
#         (McPherson et al., 2001; Al Zamal et al., 2012; Micci-Barreca, 2001)
def target_encoding(tok_pat, prefix, Tfit, yfit, Tapp, prior=10.0):
    cv = CountVectorizer(token_pattern=tok_pat, lowercase=True, binary=True)
    Xf, Xp = cv.fit_transform(Tfit), cv.transform(Tapp)
    Y = (np.asarray(yfit)[:, None] == np.array(GROUPS)[None, :]).astype(np.float32)
    C = Xf.T @ Y; glob = Y.mean(0); S = np.asarray(Xp @ C); n = S.sum(1, keepdims=True)
    P = (S + prior * glob) / (n + prior)                       # distribución suavizada hacia la global
    out = pd.DataFrame(P, columns=[f'{prefix}_p_{c}' for c in GROUPS])
    out[f'{prefix}_edad_media'] = P @ np.arange(len(GROUPS))
    out[f'{prefix}_soporte'] = np.log1p(n.ravel())
    out[f'{prefix}_conocidas'] = np.asarray(Xp @ (np.asarray(C.sum(1)).ravel() > 0).astype(np.float32)).ravel()
    return out.astype(np.float32)

def g6_homofilia(Tfit, yfit, Tapp):
    return pd.concat([target_encoding(r'@\w+', 'cta', Tfit, yfit, Tapp),
                      target_encoding(r'#\w+', 'hsh', Tfit, yfit, Tapp)], axis=1)

# =====================================================================================
# CONSTRUCCIÓN DE VARIABLES: fuera de muestra en 'fit', ajustadas con todo 'fit' en 'app'
# =====================================================================================
def build_all(T_fit, y_fit, T_app):
    T_fit, T_app = T_fit.reset_index(drop=True), T_app.reset_index(drop=True); y_fit = np.asarray(y_fit)
    order = np.array([GROUPS.index(c) for c in y_fit], np.float32)
    folds = list(StratifiedKFold(K_FOLDS, shuffle=True, random_state=0).split(np.zeros(len(y_fit)), y_fit))
    FA, FB = {}, {}

    log('TF-IDF (palabras 1-3, char_wb 2-5, char 1-5)...')
    vecs = make_vectorizers()
    Xf = sparse.hstack([v.fit_transform(T_fit) for v in vecs]).tocsr()
    Xa = sparse.hstack([v.transform(T_app) for v in vecs]).tocsr()
    n_wc = len(vecs[0].vocabulary_) + len(vecs[1].vocabulary_)
    log('  dimensiones', [len(v.vocabulary_) for v in vecs])

    log('NB-SVM fuera de muestra...')
    O = np.zeros((len(y_fit), len(GROUPS)), np.float32)
    for k, (i, j) in enumerate(folds):
        O[j] = nbsvm_scores(Xf[i], y_fit[i], Xf[j]); log(f'  partición {k + 1}/{K_FOLDS}')
    FA['NB'] = pd.DataFrame(O, columns=[f'nb_{c}' for c in GROUPS])
    FB['NB'] = pd.DataFrame(nbsvm_scores(Xf, y_fit, Xa), columns=FA['NB'].columns); log('  NB-SVM completo')

    log('G7 regresión ordinal (Ridge sobre palabras + char_wb)...')
    Xf7, Xa7 = Xf[:, :n_wc], Xa[:, :n_wc]; r = np.zeros(len(y_fit), np.float32)
    for i, j in folds: r[j] = Ridge(alpha=3.0, solver='sparse_cg', max_iter=200).fit(Xf7[i], order[i]).predict(Xf7[j])
    FA['G7_regresion_ordinal'] = pd.DataFrame({'edad_ridge': r})
    FB['G7_regresion_ordinal'] = pd.DataFrame({'edad_ridge': Ridge(alpha=3.0, solver='sparse_cg', max_iter=200)
                                               .fit(Xf7, order).predict(Xa7).astype(np.float32)})
    del Xf, Xa, Xf7, Xa7; gc.collect()

    log('G0-G5 (estilo, ciclo vital, psicológicas, jerga, morfología, complejidad)...')
    FA.update(label_free_families(T_fit)); FB.update(label_free_families(T_app))

    log('G6 homofilia de red (fuera de muestra)...')
    parts = []
    for i, j in folds:
        f = g6_homofilia(T_fit.iloc[i], y_fit[i], T_fit.iloc[j]); f.index = j; parts.append(f)
    FA['G6_homofilia_red'] = pd.concat(parts).sort_index().reset_index(drop=True)
    FB['G6_homofilia_red'] = g6_homofilia(T_fit, y_fit, T_app)

    log('G8 temas NMF y G9 LSA...')
    tv = TfidfVectorizer(token_pattern=r'(?u)[@#]?\w\w+', min_df=20, max_df=0.5, max_features=20000, sublinear_tf=True)
    Uf, Ua = tv.fit_transform(T_fit), tv.transform(T_app)
    nmf = NMF(n_components=30, init='nndsvda', max_iter=150, random_state=0)
    FA['G8_temas_nmf'] = pd.DataFrame(nmf.fit_transform(Uf), columns=[f'tema_{k}' for k in range(30)]).astype(np.float32)
    FB['G8_temas_nmf'] = pd.DataFrame(nmf.transform(Ua), columns=FA['G8_temas_nmf'].columns).astype(np.float32)
    svd = TruncatedSVD(n_components=100, random_state=0)
    FA['G9_lsa'] = pd.DataFrame(svd.fit_transform(Uf), columns=[f'lsa_{k}' for k in range(100)]).astype(np.float32)
    FB['G9_lsa'] = pd.DataFrame(svd.transform(Ua), columns=FA['G9_lsa'].columns).astype(np.float32)
    terms = np.array(tv.get_feature_names_out())
    topics = {f'tema_{k}': ' '.join(terms[np.argsort(-nmf.components_[k])[:6]]) for k in range(30)}
    return FA, FB, topics

# =====================================================================================
# SELECTOR DE VARIABLES EN TRES NIVELES
# =====================================================================================
def nivel1_filtro(FA, FB, y_fit):
    """Elimina varianza casi nula y variables redundantes (|rho| > 0,9), conservando la de mayor información mutua."""
    fams = [g for g in FA if g != 'NB']; allA = pd.concat([FA[g] for g in fams], axis=1)
    owner = {c: g for g in fams for c in FA[g].columns}
    vt = VarianceThreshold(1e-6).fit(allA); keep = list(allA.columns[vt.get_support()])
    smp = np.random.RandomState(0).choice(len(y_fit), min(30000, len(y_fit)), replace=False)
    mi = pd.Series(mutual_info_classif(allA[keep].values[smp], np.asarray(y_fit)[smp], random_state=0), index=keep)
    rho = pd.DataFrame(np.nan_to_num(spearmanr(allA[keep].values[smp]).correlation), index=keep, columns=keep)
    kept = []
    for c in mi.sort_values(ascending=False).index:
        if all(abs(rho.loc[c, k]) <= 0.9 for k in kept): kept.append(c)
    ks = set(kept)
    FA = {g: (v if g == 'NB' else v[[c for c in v.columns if c in ks]]) for g, v in FA.items()}
    FB = {g: (v if g == 'NB' else v[[c for c in v.columns if c in ks]]) for g, v in FB.items()}
    tab = pd.DataFrame({'familia': [owner[c] for c in mi.index], 'MI': mi.values}, index=mi.index)
    log(f'Nivel 1: {len(kept)} de {allA.shape[1]} variables superan el filtro')
    print(tab.groupby('familia').MI.agg(['count', 'mean', 'max']).round(4).sort_values('max', ascending=False).to_string())
    print('Top 15 por información mutua:'); print(mi.sort_values(ascending=False).head(15).round(4).to_string())
    return FA, FB

def design(F, fams): return pd.concat([F['NB']] + [F[g] for g in fams], axis=1).values.astype(np.float32)

def nivel2_wrapper(FA, y_fit):
    """Selección secuencial hacia adelante por familias con regresión logística y F1 macro en partición interna."""
    y_fit = np.asarray(y_fit)
    i1, i2 = train_test_split(np.arange(len(y_fit)), test_size=0.3, stratify=y_fit, random_state=1)
    def score(fams):
        M = design(FA, fams); sc = StandardScaler().fit(M[i1])
        m = LogisticRegression(C=1.0, max_iter=400).fit(sc.transform(M[i1]), y_fit[i1])
        return f1_score(y_fit[i2], m.predict(sc.transform(M[i2])), average='macro')
    cands = [g for g in FA if g != 'NB' and FA[g].shape[1] > 0]; sel = []; cur = score([])
    log(f'Nivel 2: base NB-SVM = {cur:.4f}')
    while cands:
        res = {g: score(sel + [g]) for g in cands}
        for g, s in sorted(res.items(), key=lambda kv: -kv[1]): print(f'    + {g:28s} {s:.4f} ({s - cur:+.4f})')
        g, s = max(res.items(), key=lambda kv: kv[1])
        if s - cur < MIN_GANANCIA: log(f'  se detiene: la mejor familia suma {s - cur:+.4f}'); break
        sel.append(g); cands.remove(g); cur = s; log(f'  entra {g} -> {cur:.4f}')
    return sel

def meta_model():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, l2_regularization=1.0, random_state=0)

def nivel3_evaluar(FA, FB, sel, y_fit, y_app):
    y_fit, y_app = np.asarray(y_fit), np.asarray(y_app); res = {}
    res['NB-SVM solo'] = f1_score(y_app, np.array(GROUPS)[FB['NB'].values.argmax(1)], average='macro')
    for name, fams, kind in [('Meta LR: todas las familias', [g for g in FA if g != 'NB' and FA[g].shape[1] > 0], 'lr'),
                             ('Meta LR: familias elegidas', sel, 'lr'), ('Meta HGB: familias elegidas', sel, 'hgb')]:
        A, B = design(FA, fams), design(FB, fams); sc = StandardScaler().fit(A)
        m = LogisticRegression(C=1.0, max_iter=400) if kind == 'lr' else meta_model()
        m.fit(sc.transform(A), y_fit); pred = m.predict(sc.transform(B))
        res[name] = f1_score(y_app, pred, average='macro')
    log('Nivel 3 (validación reservada):'); [print(f'    {k:32s} {v:.4f}') for k, v in res.items()]
    print(classification_report(y_app, pred, labels=GROUPS, digits=3))
    # importancia por permutación de cada familia en el meta-modelo final
    cols = list(FB['NB'].columns) + [c for g in sel for c in FB[g].columns]; Bs = sc.transform(B); base = res[name]
    for g in ['NB'] + sel:
        idx = [cols.index(c) for c in FB[g].columns]; drops = []
        for r in range(3):
            P = Bs.copy(); P[:, idx] = P[np.random.RandomState(r).permutation(len(P))][:, idx]
            drops.append(base - f1_score(y_app, m.predict(P), average='macro'))
        print(f'    permutar {g:28s} baja el F1 en {np.mean(drops):.4f}')
    return res

# =====================================================================================
# EJECUCIÓN
# =====================================================================================
if __name__ == '__main__':
    log('Datos en:', DATA_DIR)
    train_raw = load(os.path.join(DATA_DIR, 'age_train.csv')); test = load(os.path.join(DATA_DIR, 'age_test.csv'))
    if SAMPLE_FRAC:
        train_raw = train_raw.groupby('age_range', group_keys=False).sample(frac=SAMPLE_FRAC, random_state=SEED)
    train = train_raw[~is_junk(train_raw.text)].reset_index(drop=True)
    log(f'train {train.shape} | test {test.shape}')

    selected = None
    if VALIDAR:
        log('================ VALIDACIÓN 80/20 ================')
        a, b = train_test_split(np.arange(len(train)), test_size=0.2, stratify=train.age_range, random_state=SEED)
        FA, FB, topics = build_all(train.text.iloc[a], train.age_range.values[a], train.text.iloc[b])
        print('Temas NMF (primeras palabras):'); [print('   ', k, '->', v) for k, v in list(topics.items())[:10]]
        FA, FB = nivel1_filtro(FA, FB, train.age_range.values[a])
        selected = nivel2_wrapper(FA, train.age_range.values[a])
        nivel3_evaluar(FA, FB, selected, train.age_range.values[a], train.age_range.values[b])
        del FA, FB; gc.collect()

    log('================ MODELO FINAL (todo el train) ================')
    FA, FB, _ = build_all(train.text, train.age_range.values, test.text)
    FA, FB = nivel1_filtro(FA, FB, train.age_range.values)
    if selected is None:
        selected = nivel2_wrapper(FA, train.age_range.values)
    selected = [g for g in selected if g in FA and FA[g].shape[1] > 0]
    log('Familias del modelo final:', selected)
    A, B = design(FA, selected), design(FB, selected); sc = StandardScaler().fit(A)
    meta = meta_model().fit(sc.transform(A), train.age_range.values)
    test['age_range'] = meta.predict(sc.transform(B))

    # Reglas validadas en la versión 2: duplicados exactos con etiqueta unánime y textos vacíos
    lab = train.groupby('text').age_range.agg(['nunique', 'first']); lookup = lab.loc[lab['nunique'] == 1, 'first']
    hit = test.text.isin(lookup.index) & (test.text != '')
    test.loc[hit, 'age_range'] = test.loc[hit, 'text'].map(lookup)
    jt = is_junk(train_raw.text); default = train_raw.age_range[jt].mode().iloc[0] if jt.any() else train.age_range.mode().iloc[0]
    test.loc[is_junk(test.text), 'age_range'] = default
    log(f'duplicados reemplazados: {int(hit.sum())} | vacíos: {int(is_junk(test.text).sum())} -> {default}')

    sp = os.path.join(DATA_DIR, 'age_sample_submission.csv')
    cols = (pd.read_csv(sp, nrows=0, sep=None, engine='python', encoding='utf-8-sig').columns.tolist()
            if os.path.exists(sp) else ['id', 'age_range'])
    sub = pd.DataFrame({cols[0]: test['id'].astype(int), cols[1]: test['age_range']})
    assert sub[cols[1]].isin(GROUPS).all()
    sub.to_csv(os.path.join(HERE, OUT_PATH), index=False)
    log('Guardado:', os.path.join(HERE, OUT_PATH), sub.shape)
    print(sub[cols[1]].value_counts(normalize=True).reindex(GROUPS).round(3).to_string())

# =====================================================================================
# REFERENCIAS (APA 7)
# =====================================================================================
# Al Zamal, F., Liu, W., & Ruths, D. (2012). Homophily and latent attribute inference: Inferring latent attributes of
#     Twitter users from neighbors. Proceedings of the International AAAI Conference on Web and Social Media, 6(1), 387-390.
# Argamon, S., Koppel, M., Pennebaker, J. W., & Schler, J. (2009). Automatically profiling the author of an anonymous
#     text. Communications of the ACM, 52(2), 119-123.
# Benedetto, D., Caglioti, E., & Loreto, V. (2002). Language trees and zipping. Physical Review Letters, 88(4), 048702.
# Biber, D. (1988). Variation across speech and writing. Cambridge University Press.
# Deerwester, S., Dumais, S. T., Furnas, G. W., Landauer, T. K., & Harshman, R. (1990). Indexing by latent semantic
#     analysis. Journal of the American Society for Information Science, 41(6), 391-407.
# Eckert, P. (1997). Age as a sociolinguistic variable. En F. Coulmas (Ed.), The handbook of sociolinguistics
#     (pp. 151-167). Blackwell.
# Eisenstein, J. (2013). What to do about bad language on the internet. Proceedings of NAACL-HLT 2013 (pp. 359-369).
# Fernández Huerta, J. (1959). Medidas sencillas de lecturabilidad. Consigna, 214, 29-32.
# Frank, E., & Hall, M. (2001). A simple approach to ordinal classification. En Machine Learning: ECML 2001 (pp. 145-156). Springer.
# Guyon, I., & Elisseeff, A. (2003). An introduction to variable and feature selection. Journal of Machine Learning
#     Research, 3, 1157-1182.
# Heylighen, F., & Dewaele, J.-M. (2002). Variation in the contextuality of language: An empirical measure.
#     Foundations of Science, 7(3), 293-340.
# Kohavi, R., & John, G. H. (1997). Wrappers for feature subset selection. Artificial Intelligence, 97(1-2), 273-324.
# Lee, D. D., & Seung, H. S. (1999). Learning the parts of objects by non-negative matrix factorization. Nature, 401, 788-791.
# McPherson, M., Smith-Lovin, L., & Cook, J. M. (2001). Birds of a feather: Homophily in social networks.
#     Annual Review of Sociology, 27, 415-444.
# Micci-Barreca, D. (2001). A preprocessing scheme for high-cardinality categorical attributes in classification and
#     prediction problems. ACM SIGKDD Explorations Newsletter, 3(1), 27-32.
# Moreno-Sandoval, L. G., Pomares-Quimbaya, A., & Alvarado-Valencia, J. A. (2021). Celebrity profiling through
#     linguistic analysis of digital social networks. Computational Social Networks, 8, 16.
# Nguyen, D., Gravel, R., Trieschnigg, D., & Meder, T. (2013). "How old do you think I am?": A study of language and age
#     in Twitter. Proceedings of ICWSM 2013 (pp. 439-448).
# Nguyen, D., Smith, N. A., & Rosé, C. P. (2011). Author age prediction from text using linear regression.
#     Proceedings of the 5th ACL-HLT Workshop on Language Technology for Cultural Heritage (pp. 115-123).
# Pennebaker, J. W., Boyd, R. L., Jordan, K., & Blackburn, K. (2015). The development and psychometric properties of
#     LIWC2015. University of Texas at Austin.
# Pennebaker, J. W., & Stone, L. D. (2003). Words of wisdom: Language use over the life span. Journal of Personality
#     and Social Psychology, 85(2), 291-301.
# Peng, H., Long, F., & Ding, C. (2005). Feature selection based on mutual information: Criteria of max-dependency,
#     max-relevance, and min-redundancy. IEEE TPAMI, 27(8), 1226-1238.
# Ramírez-Esparza, N., Pennebaker, J. W., García, F. A., & Suriá, R. (2007). La psicología del uso de las palabras:
#     Un programa de computadora que analiza textos en español. Revista Mexicana de Psicología, 24(1), 85-99.
# Rao, D., Yarowsky, D., Shreevats, A., & Gupta, M. (2010). Classifying latent user attributes in Twitter.
#     Proceedings of SMUC '10 (pp. 37-44). ACM.
# Schler, J., Koppel, M., Argamon, S., & Pennebaker, J. W. (2006). Effects of age and gender on blogging.
#     AAAI Spring Symposium: Computational Approaches to Analyzing Weblogs (pp. 199-205).
# Schwartz, H. A., et al. (2013). Personality, gender, and age in the language of social media: The open-vocabulary
#     approach. PLoS ONE, 8(9), e73791.
# Shannon, C. E. (1948). A mathematical theory of communication. Bell System Technical Journal, 27(3), 379-423.
# Szigriszt Pazos, F. (1993). Sistemas predictivos de legibilidad del mensaje escrito: Fórmula de perspicuidad
#     [Tesis doctoral, Universidad Complutense de Madrid].
# Wang, S., & Manning, C. D. (2012). Baselines and bigrams: Simple, good sentiment and topic classification.
#     Proceedings of the 50th Annual Meeting of the ACL (Vol. 2, pp. 90-94).
