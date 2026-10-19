"""E13 (paso 3): CV completa, desarrollo y control para base / genérica / con H19-H23."""
import sys, os; sys.path.insert(0, os.getcwd())
import numpy as np, toxic_base as tb, ext_variables as ev, ext_variables2 as ev2, ext_formulaciones as ef
S5 = (42,43,44,45,46); B7 = tb.BASES_ORIGINALES + ['LGBM', 'LGBM-PS']
hold = np.load('recursos/control_E13.npy'); dev = np.setdiff1d(np.arange(1731), hold)
D = {'base': tb.Datos(), 'gen': tb.Datos(extra_lex=[ev.variables(generica=True)]),
     'base+H19-23': tb.Datos(extra_lex=[ev2.variables()]),
     'gen+H19-23': tb.Datos(extra_lex=[ev.variables(generica=True), ev2.variables()])}
for k, dd in D.items():
    for s in S5:
        for b in B7: tb.oof(dd, b, s); tb.pred_test_folds(dd, b, s)
    tb.log('listo', k)
Y = D['base'].Y
for k, dd in D.items():
    ST = [tb.stacking_bagged(dd, B7, S5, s, con_test=False)[0] for s in tb.SEEDS]
    f = lambda idx: [tb.metricas(Y[idx], tb.binarizar(P)[idx])['F1 medio'] for P in ST]
    a, h, dv = f(np.arange(1731)), f(hold), f(dev)
    print(f'{k:14s} CV {np.mean(a):.4f} ({" / ".join(f"{x:.3f}" for x in a)}) | dev {np.mean(dv):.4f} | CONTROL {np.mean(h):.4f} ({" / ".join(f"{x:.3f}" for x in h)})', flush=True)
