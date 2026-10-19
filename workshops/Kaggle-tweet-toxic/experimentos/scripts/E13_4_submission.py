"""E13a: genera la submission con H12-H17 genérica + H19-H23 (ejecutar desde experimentos/)."""
import sys, os; sys.path.insert(0, os.getcwd())
import toxic_base as tb, ext_variables as ev, ext_variables2 as ev2, ext_formulaciones as ef
S5 = (42, 43, 44, 45, 46); B7 = tb.BASES_ORIGINALES + ['LGBM', 'LGBM-PS']
dd = tb.Datos(extra_lex=[ev.variables(generica=True), ev2.variables()])
_, Pt = tb.stacking_bagged(dd, B7, S5, 42)
tb.guardar_submission(dd, tb.binarizar(Pt), 'toxic_submission_E13a_generica_h19_23.csv')
