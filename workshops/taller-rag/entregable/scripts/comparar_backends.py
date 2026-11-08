"""Compara Milvus y Solr a partir de los dos resúmenes que escribe ejecutar_experimento_robusto.py.

Uso:
  python scripts/ejecutar_experimento_robusto.py --gold docs/gold_standard.csv data/gold/gold.jsonl --backend milvus --solo-retrieve --salida reports/crudos/exp_milvus.jsonl
  python scripts/ejecutar_experimento_robusto.py --gold docs/gold_standard.csv data/gold/gold.jsonl --backend solr   --solo-retrieve --salida reports/crudos/exp_solr.jsonl
  python scripts/comparar_backends.py reports/crudos/exp_milvus.jsonl.resumen.json reports/crudos/exp_solr.jsonl.resumen.json

Imprime la tabla lado a lado, escribe reports/comparacion_milvus_solr.md y un fragmento LaTeX (reports/comparacion_milvus_solr.tex)
listo para pegar en el informe. Solo compara recuperación; la abstención de Solr (BM25) no es comparable con la de coseno.
"""
import json
import os
import sys

METRICAS = ["R@1", "R@5", "R@10", "MRR", "nDCG@10"]


def f(x, tex=False):
    if x is None:
        return "–"
    s = f"{x:.3f}"
    return s.replace(".", ",") if tex else s


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:])
    for r, p in ((a, sys.argv[1]), (b, sys.argv[2])):
        if "recuperacion" not in r:
            sys.exit(f"{p} no tiene 'recuperacion'.")
    if (a.get("backend"), b.get("backend")) != ("milvus", "solr"):
        print(f"AVISO: se esperaba (milvus, solr) y los resúmenes dicen ({a.get('backend')}, {b.get('backend')}).")
    if (a.get("split"), a.get("k_retrieve")) != (b.get("split"), b.get("k_retrieve")):
        print("AVISO: los dos resúmenes usan distinta partición o k; la comparación no es válida.")
    tipos = sorted(set(a["recuperacion"]) | set(b["recuperacion"]), key=lambda t: (t != "GLOBAL", t))
    lineas = ["| Tipo | n | " + " | ".join(f"{m} Milvus | {m} Solr" for m in ("R@1", "R@10", "MRR")) + " |",
              "|---|---|" + "---|" * 6]
    tex = [r"\begin{table}[ht]", r"\centering",
           r"\caption{Milvus (denso) frente a Solr (BM25): recuperación en la partición de %s, $k=%s$, nivel de documento.}" % (a.get("split"), a.get("k_retrieve")),
           r"\label{tab:milvus_solr}", r"\setlength{\tabcolsep}{3pt}", r"\begin{tabular}{lrrrrrrr}", r"\toprule",
           r" & & \multicolumn{2}{c}{R@1} & \multicolumn{2}{c}{R@10} & \multicolumn{2}{c}{MRR} \\",
           r"Tipo & $n$ & Milvus & Solr & Milvus & Solr & Milvus & Solr \\", r"\midrule"]
    print(f"{'tipo':16}{'n':>4}  " + "  ".join(f"{m:>6}M {m:>6}S" for m in ("R@1", "R@10", "MRR")))
    for t in tipos:
        x, y = a["recuperacion"].get(t, {}), b["recuperacion"].get(t, {})
        n = x.get("n", y.get("n", 0))
        vals = [(x.get(m), y.get(m)) for m in ("R@1", "R@10", "MRR")]
        print(f"{t:16}{n:>4}  " + "  ".join(f"{f(p):>7} {f(q):>7}" for p, q in vals))
        lineas.append(f"| {t} | {n} | " + " | ".join(f"{f(p)} | {f(q)}" for p, q in vals) + " |")
        tex.append(f"{t.replace('_', ' ')} & {n} & " + " & ".join(f"{f(p, True)} & {f(q, True)}" for p, q in vals) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    os.makedirs("reports", exist_ok=True)
    open("reports/comparacion_milvus_solr.md", "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    open("reports/comparacion_milvus_solr.tex", "w", encoding="utf-8").write("\n".join(tex) + "\n")
    print("\nEscrito: reports/comparacion_milvus_solr.md y reports/comparacion_milvus_solr.tex")


if __name__ == "__main__":
    main()
