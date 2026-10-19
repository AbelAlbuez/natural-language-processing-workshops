"""E13 (paso 2): P(HS, TR, AG | patrón) en desarrollo. Uso: python scripts/E13_2_verificar_patron.py 'regex' ..."""
import sys, os, re; sys.path.insert(0, os.getcwd())
import numpy as np, toxic_base as tb
d = tb.Datos(); hold = np.load('recursos/control_E13.npy'); dev = np.setdiff1d(np.arange(d.n), hold)
T = d.TXT_TR.values[dev]; Y = d.Y[dev]
for p in sys.argv[1:]:
    m = np.array([bool(re.search(p, t)) for t in T])
    print(f'{p:45s} n={m.sum():3d} P={Y[m].mean(0).round(2) if m.sum() else "-"}')
