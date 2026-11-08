"""Resume por qué fallaron las corridas de /ask en un archivo del experimento.
Uso: python data/diagnostico_errores.py data/exp_completo2.jsonl
"""
import collections, json, sys
c, t = collections.Counter(), collections.defaultdict(list)
for linea in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(linea)
    if r.get("fase") != "ask":
        continue
    clave = (r["modelo"], r.get("http"), json.dumps(r.get("error"), ensure_ascii=False)[:170] if r.get("http") != 200 else "")
    c[clave] += 1
    t[clave].append(r.get("segundos", 0))
print(f"{'modelo':14}{'http':>6} {'n':>4} {'seg medio':>10}  error")
for (m, h, e), n in sorted(c.items(), key=lambda x: (x[0][0], str(x[0][1]))):
    print(f"{m:14}{str(h):>6} {n:>4} {sum(t[(m,h,e)])/n:>10.1f}  {e}")
