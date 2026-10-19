"""E12: bases extra sobre el stacking con H12-H17 genérica (desde experimentos/)."""
import sys, os; sys.path.insert(0, os.getcwd())
import numpy as np, toxic_base as tb, ext_variables as ev, ext_formulaciones as ef
S5 = (42,43,44,45,46); B7 = tb.BASES_ORIGINALES + ['LGBM', 'LGBM-PS']
d = tb.Datos(); g = tb.Datos(extra_lex=[ev.variables(generica=True)])
f = lambda bs: np.mean([tb.metricas(d.Y, tb.binarizar(tb.stacking_bagged(g, bs, S5, s, con_test=False)[0]))['F1 medio'] for s in tb.SEEDS])
print('gen B7', round(f(B7), 4))
for e in ['Jerarq-LR', 'ExtraTrees', 'BNB', 'LGBM-chi2']:
    print('gen +', e, round(f(B7 + [e]), 4), flush=True)
