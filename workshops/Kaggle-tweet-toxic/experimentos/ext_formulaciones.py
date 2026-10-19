"""E10c — Otras formulaciones del problema y modelos base de familias distintas (hipótesis C).

Importar después de `toxic_base`: `import ext_formulaciones` registra en `tb.MODELOS` los modelos nuevos.
No modifica nada de lo existente; solo agrega entradas a `tb.MODELOS` y `tb.BLOQUES`.

Modelos registrados:
- 'Jerarq-LR'  : formulación condicional. HS con LR sobre todo el train; TR y AG con LR entrenadas SOLO con los
                 tweets HS=1; AG para HS=0 con una LR aparte entrenada con los HS=0 (casi siempre comillas).
                 P(TR) = P(HS)·P(TR|HS=1);  P(AG) = P(HS)·P(AG|HS=1) + (1-P(HS))·P(AG|HS=0).
- 'ExtraTrees' : ExtraTreesClassifier sobre SVD(300) + léxico crudo (otra familia de árboles: bagging, no boosting).
- 'kNN'        : k vecinos más cercanos por similitud coseno en TF-IDF de palabras + caracteres (k=25, ponderado).
- 'BNB'        : Bernoulli Naive Bayes sobre presencia/ausencia de palabras (1-2 gramas).
- 'LGBM-PS'    : LightGBM *Label Powerset* (multiclase sobre las 6 combinaciones) sobre SVD + léxico crudo.
- 'LGBM-chi2'  : LightGBM sobre TF-IDF disperso (palabras + caracteres) filtrado con chi² (2000 columnas, ajustado solo
                 con la partición de entrenamiento) + léxico crudo.
"""
import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.naive_bayes import BernoulliNB
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.preprocessing import normalize

import toxic_base as tb

N_JOBS = 3


# ---------------------------------------------------------------------------------------------------
# Jerárquica / condicional
# ---------------------------------------------------------------------------------------------------
def _lr(cfg, C=None):
    return LogisticRegression(C=cfg['C_LR'] if C is None else C, max_iter=5000, class_weight='balanced')

def jerarquica_fp(Xa, Ya, combo_a, Xb, cfg):
    hs = Ya[:, 0] == 1
    p_hs = _lr(cfg).fit(Xa, Ya[:, 0]).predict_proba(Xb)[:, 1]
    p_tr1 = _lr(cfg).fit(Xa[hs], Ya[hs, 1]).predict_proba(Xb)[:, 1]
    p_ag1 = _lr(cfg).fit(Xa[hs], Ya[hs, 2]).predict_proba(Xb)[:, 1]
    # AG con HS=0 es raro (~1,5 %): LR más regularizada y sin balancear, para no inflar la probabilidad
    p_ag0 = LogisticRegression(C=1.0, max_iter=5000).fit(Xa[~hs], Ya[~hs, 2]).predict_proba(Xb)[:, 1]
    return np.column_stack([p_hs, p_hs * p_tr1, p_hs * p_ag1 + (1 - p_hs) * p_ag0])

tb.MODELOS['Jerarq-LR'] = dict(bloques=tb.TODOS, fit_predict=jerarquica_fp)


# ---------------------------------------------------------------------------------------------------
# ExtraTrees sobre SVD + léxico
# ---------------------------------------------------------------------------------------------------
def extratrees_fp(Xa, Ya, combo_a, Xb, cfg):
    Xa, Xb = Xa.toarray(), Xb.toarray()
    out = []
    for j in range(3):
        m = ExtraTreesClassifier(n_estimators=500, max_features=0.3, min_samples_leaf=2, class_weight='balanced',
                                 n_jobs=N_JOBS, random_state=0)
        out.append(m.fit(Xa, Ya[:, j]).predict_proba(Xb)[:, 1])
    return np.column_stack(out)

tb.MODELOS['ExtraTrees'] = dict(bloques=['svd', 'lexraw'], fit_predict=extratrees_fp)


# ---------------------------------------------------------------------------------------------------
# kNN coseno sobre TF-IDF
# ---------------------------------------------------------------------------------------------------
def knn_fp(Xa, Ya, combo_a, Xb, cfg, k=25):
    """Probabilidad = promedio de las etiquetas de los k vecinos, ponderado por la similitud coseno.
    Se suaviza con la prevalencia (pseudo-conteo 1) para no dar 0/1 exactos."""
    A, B = normalize(Xa), normalize(Xb)
    S = (B @ A.T).toarray()                               # (n_b, n_a) similitudes coseno
    idx = np.argpartition(-S, k, axis=1)[:, :k]
    w = np.take_along_axis(S, idx, 1) + 1e-6
    prev = Ya.mean(0)
    P = np.column_stack([((w * Ya[idx, j]).sum(1) + prev[j]) / (w.sum(1) + 1) for j in range(3)])
    return P

tb.MODELOS['kNN'] = dict(bloques=['word', 'char'], fit_predict=knn_fp)


# ---------------------------------------------------------------------------------------------------
# Bernoulli NB sobre presencia de palabras
# ---------------------------------------------------------------------------------------------------
def bnb_fp(Xa, Ya, combo_a, Xb, cfg):
    Xa, Xb = (Xa > 0).astype(float), (Xb > 0).astype(float)
    return np.column_stack([BernoulliNB(alpha=0.5).fit(Xa, Ya[:, j]).predict_proba(Xb)[:, 1] for j in range(3)])

tb.MODELOS['BNB'] = dict(bloques=['word'], fit_predict=bnb_fp)


# ---------------------------------------------------------------------------------------------------
# LightGBM Powerset y LightGBM sobre TF-IDF disperso con chi²
# ---------------------------------------------------------------------------------------------------
def _lgbm_multi(seed=0):
    import lightgbm as lgb
    return lgb.LGBMClassifier(objective='multiclass', n_estimators=300, learning_rate=0.03, num_leaves=15,
                              min_child_samples=10, subsample=0.8, subsample_freq=1, colsample_bytree=0.5,
                              reg_lambda=1.0, class_weight='balanced', random_state=seed, verbose=-1, n_jobs=N_JOBS)

def lgbm_ps_fp(Xa, Ya, combo_a, Xb, cfg):
    m = _lgbm_multi().fit(Xa.toarray(), combo_a)
    return tb.marginales(m.predict_proba(Xb.toarray()), m.classes_)

tb.MODELOS['LGBM-PS'] = dict(bloques=['svd', 'lexraw'], fit_predict=lgbm_ps_fp)

N_LEX = len(tb.LEX_NOMBRES)

def lgbm_chi2_fp(Xa, Ya, combo_a, Xb, cfg, k=2000):
    """Las últimas N_LEX columnas son el léxico crudo y siempre se conservan; chi² filtra los n-gramas
    por etiqueta, ajustado solo con Xa."""
    d = Xa.shape[1] - N_LEX
    out = []
    for j in range(3):
        sel = SelectKBest(chi2, k=min(k, d)).fit(Xa[:, :d], Ya[:, j])
        A = sparse.hstack([sel.transform(Xa[:, :d]), Xa[:, d:]]).tocsr().astype(np.float32)
        B = sparse.hstack([sel.transform(Xb[:, :d]), Xb[:, d:]]).tocsr().astype(np.float32)
        m = tb._lgbm()
        m.set_params(n_jobs=N_JOBS)
        out.append(m.fit(A, Ya[:, j]).predict_proba(B)[:, 1])
    return np.column_stack(out)

tb.MODELOS['LGBM-chi2'] = dict(bloques=['word', 'char', 'lexraw'], fit_predict=lgbm_chi2_fp)

NUEVOS = ['Jerarq-LR', 'ExtraTrees', 'kNN', 'BNB', 'LGBM-PS', 'LGBM-chi2']
