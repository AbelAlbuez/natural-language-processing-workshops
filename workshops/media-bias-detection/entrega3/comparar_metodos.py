"""Compara los cuatro modelos de tópicos y busca hallazgos que se repiten.

Modelos: LDA sobre el corpus completo (resultados/), y LDA, LDA de consenso y
BERTopic sobre el subcorpus de asuntos públicos (resultados_publico/…).

Salidas en resultados_publico/: comparacion_metodos.csv, hallazgos_coincidentes.csv
y figuras/17_comparacion_metodos.png.

Los tópicos de distintos modelos no son los mismos objetos: se agrupan en temas
por su etiqueta humana (TEMAS, expresiones regulares) y un hallazgo "se repite"
si al menos dos modelos dan un Δ relativo con control por sección significativo
(Holm < 0,05), fiable (tópico no inestable y mismo signo con otras semillas) y
del mismo signo para el mismo medio y tema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import figuras as F

HERE = Path(__file__).resolve().parent
MODELOS = {
    "LDA · corpus completo": HERE / "resultados",
    "LDA · asuntos públicos": HERE / "resultados_publico",
    "LDA de consenso · asuntos públicos": HERE / "resultados_publico" / "ensemble",
    "BERTopic · asuntos públicos": HERE / "resultados_publico" / "bertopic",
}
TEMAS = {
    "Inseguridad urbana y sucesos": r"sucesos|inseguridad|seguridad urbana|policía e",
    "Justicia y tribunales": r"^(?!.*transicional).*(?:justicia|tribunales|cortes)",
    "Geopolítica y guerras": r"guerras|geopolít",
    "Gobierno y presidente": r"gobierno, petro|gobierno y presidente|petro, campaña",
    "Conflicto armado": r"conflicto armado|combates|ataques de grupos|conflicto, víctimas",
    "Venezuela": r"venezuela",
    "Fútbol": r"fútbol",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def coherencia(res: Path) -> float:
    if (res / "bertopic.json").exists():
        return load(res / "bertopic.json")["coherence_cv"]
    if (res / "ensemble.json").exists():
        return load(res / "ensemble.json")["coherence_cv"]
    k = load(res / "compare.json")["k"]
    grid = pd.read_csv(res / "lda_optimization.csv")
    return float(grid.loc[grid["K"] == k, "coherence_cv"].iloc[0])


def fiable(d: pd.DataFrame) -> pd.Series:
    return d["robustez"].ne("inestable") & d["mismo_signo_otras_semillas"].astype(bool)


def metricas() -> pd.DataFrame:
    rows = []
    for nombre, res in MODELOS.items():
        comp, stab, rob = load(res / "compare.json"), load(res / "stability.json"), load(res / "robustness.json")
        d = pd.read_csv(res / "deltas.csv")
        ok = fiable(d)
        rows.append({
            "modelo": nombre, "K": comp["k"], "documentos": comp["documentos"],
            "coherencia_cv": coherencia(res),
            "jaccard_medio_semillas": stab["jaccard_medio_global"],
            "pct_topicos_robustos": 100 * stab["conteo"].get("robusto", 0) / comp["k"],
            "pct_topicos_parciales": 100 * stab["conteo"].get("parcial", 0) / comp["k"],
            "correlacion_delta_semillas": float(np.mean(list(rob["correlacion_base_vs_semillas"].values()))),
            "pares_medio_topico": len(d),
            "delta_fiables_sin_control": int(((d["delta_rel_p_holm"] < 0.05) & ok).sum()),
            "delta_fiables_con_control": int(((d["secc_delta_rel_p_holm"] < 0.05) & ok).sum()),
        })
    table = pd.DataFrame(rows)
    table["pct_delta_fiables_sin_control"] = 100 * table["delta_fiables_sin_control"] / table["pares_medio_topico"]
    table["pct_delta_fiables_con_control"] = 100 * table["delta_fiables_con_control"] / table["pares_medio_topico"]
    return table


def hallazgos() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for nombre, res in MODELOS.items():
        d = pd.read_csv(res / "deltas.csv")
        d = d.assign(fiable=fiable(d))
        for tema, patron in TEMAS.items():
            sel = d[d["etiqueta"].str.lower().str.contains(patron, regex=True)]
            for r in sel.itertuples():
                rows.append({
                    "tema": tema, "source_id": r.source_id, "modelo": nombre, "topico": r.etiqueta,
                    "robustez": r.robustez, "fiable": bool(r.fiable),
                    "delta_rel_pp": r.delta_rel_pp, "secc_delta_rel_pp": r.secc_delta_rel_pp,
                    "secc_p_holm": r.secc_delta_rel_p_holm,
                    "significativo_con_control": bool(r.fiable and r.secc_delta_rel_p_holm < 0.05),
                })
    detalle = pd.DataFrame(rows)
    sig = detalle[detalle["significativo_con_control"]].assign(signo=lambda x: np.sign(x["secc_delta_rel_pp"]))
    grupos = []
    for (tema, medio, signo), g in sig.groupby(["tema", "source_id", "signo"]):
        modelos = sorted(g["modelo"].unique())
        if len(modelos) >= 2:
            grupos.append({
                "tema": tema, "source_id": medio, "direccion": "más" if signo > 0 else "menos",
                "n_modelos": len(modelos), "modelos": " | ".join(modelos),
                "secc_delta_rel_pp_rango": f"{g['secc_delta_rel_pp'].min():+.2f} a {g['secc_delta_rel_pp'].max():+.2f}",
                "topicos": " | ".join(sorted(g["topico"].unique())),
            })
    return detalle, pd.DataFrame(grupos)


def figura(table: pd.DataFrame, out: Path) -> None:
    paneles = [
        ("coherencia_cv", "Coherencia c_v", "{:.3f}"),
        ("jaccard_medio_semillas", "Jaccard medio entre semillas", "{:.2f}"),
        ("pct_topicos_robustos", "% de tópicos robustos", "{:.0f} %"),
        ("correlacion_delta_semillas", "Correlación del Δ relativo entre semillas", "{:.2f}"),
        ("pct_delta_fiables_sin_control", "% de Δ fiables, sin control por sección", "{:.0f} %"),
        ("pct_delta_fiables_con_control", "% de Δ fiables, con control por sección", "{:.0f} %"),
    ]
    nombres = [n.replace(" · ", "\n") for n in table["modelo"]][::-1]
    fig, axes = plt.subplots(2, 3, figsize=(15, 6.8), sharey=True)
    for ax, (col, titulo, fmt) in zip(axes.flat, paneles):
        vals = table[col].to_numpy()[::-1]
        ax.barh(nombres, vals, color=F.BLUE, height=0.6)
        for y, v in enumerate(vals):
            ax.text(v, y, "  " + fmt.format(v).replace(".", ","), va="center", fontsize=8.5, color=F.INK)
        ax.set_xlim(0, max(vals.max() * 1.3, 1e-9))
        ax.set_title(titulo, fontsize=10)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", labelsize=8.5)
    fig.tight_layout()
    F._save(fig, out, "17_comparacion_metodos.png", "BERTopic es el único modelo estable entre semillas",
            "Δ fiable = Holm < 0,05, tópico no inestable y mismo signo con las otras semillas; en % de los pares "
            "medio × tópico de cada modelo. c_v calculada con los textos de la muestra de cada corpus (el corpus "
            f"completo y el subcorpus no son directamente comparables). {F.FUENTE}", note_y=-0.03)


def main() -> None:
    out = HERE / "resultados_publico"
    table = metricas()
    table.to_csv(out / "comparacion_metodos.csv", index=False)
    detalle, grupos = hallazgos()
    detalle.to_csv(out / "hallazgos_por_tema.csv", index=False)
    grupos.to_csv(out / "hallazgos_coincidentes.csv", index=False)
    figura(table, out)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(table.round(3).to_string(index=False))
        print()
        print(grupos.to_string(index=False) if len(grupos) else "(ningún hallazgo en ≥ 2 modelos)")


if __name__ == "__main__":
    main()
