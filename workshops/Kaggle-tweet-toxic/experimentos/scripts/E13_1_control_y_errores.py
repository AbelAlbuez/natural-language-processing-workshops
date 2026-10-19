"""E13 (paso 1): crea el 20 % de control (recursos/control_E13.npy) y vuelca los errores del stacking E11b
solo en el 80 % de desarrollo. Uso (desde experimentos/): python scripts/E13_1_control_y_errores.py errores_dev.txt"""
import sys, os; sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd, toxic_base as tb, ext_variables as ev, ext_formulaciones as ef
from sklearn.model_selection import StratifiedKFold
S5 = (42,43,44,45,46); B7 = tb.BASES_ORIGINALES + ['LGBM', 'LGBM-PS']
g = tb.Datos(extra_lex=[ev.variables(generica=True)])
hold = next(iter(StratifiedKFold(5, shuffle=True, random_state=2026).split(g.TXT_TR, g.COMBO)))[1]
np.save('recursos/control_E13.npy', hold)
P = np.mean([tb.stacking_bagged(g, B7, S5, s, con_test=False)[0] for s in tb.SEEDS], 0)
dev = np.setdiff1d(np.arange(g.n), hold)
Yp = tb.binarizar(P); Yp[:, 1] *= Yp[:, 0]
df = pd.DataFrame({'i': np.arange(g.n), 'norm': g.TXT_TR.values,
                   'real': g.COMBO, 'pred': [''.join(map(str, r)) for r in Yp],
                   'p': [' '.join(f'{x:.2f}' for x in r) for r in P]})
e = df.iloc[dev]; e = e[e.real != e.pred]
print('dev', len(dev), 'errores dev', len(e), 'control', len(hold))
with open(sys.argv[1], 'w') as f:
    for k, grp in e.groupby(['real', 'pred']):
        f.write(f'\n##### real {k[0]} pred {k[1]} ({len(grp)})\n')
        for r in grp.itertuples(): f.write(f'[{r.i}] {r.p} | {r.norm}\n')
