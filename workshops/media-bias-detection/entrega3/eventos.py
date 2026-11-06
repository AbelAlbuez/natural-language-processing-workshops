"""Emparejamiento de titulares del mismo hecho entre medios (pasos 1 y 3).

Sobre el subcorpus de asuntos públicos (`resultados_publico`), con los
embeddings de BERTopic (paraphrase-multilingual-MiniLM-L12-v2, normalizados) y
sólo titulares con fecha al día.

    candidatos  para cada titular, los titulares de OTROS medios en ±ventana días,
                por similitud coseno; guarda las aristas ≥ --sim-min y el más
                parecido de cada medio (para la reciprocidad)
    eventos     agrupa en eventos: aristas recíprocas ≥ --umbral, componentes
                conexas, partición de las componentes encadenadas, núcleo de un
                titular por medio y notas de seguimiento del mismo medio

El umbral (0,80) está calibrado con 270 anotaciones manuales (paso 2,
calibracion.py): precisión ponderada 81 % (IC 95 % 72–90 %), kappa 0,77.
`eventos` corre también con --umbrales para la tabla de sensibilidad y deja las
salidas completas sólo para --umbral.

Uso: SCRIPT=eventos.py ./run.sh - --output resultados_publico --stage all
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

import figuras
from topics import MEDIA, load_json, save_json

HERE = Path(__file__).resolve().parent
UMBRALES_REPORTE = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85)


# ── paso 1: candidatos ───────────────────────────────────────────────────────


def template_mask(emb: np.ndarray, day: np.ndarray, media: np.ndarray, sim: float = 0.9,
                  min_group: int = 10) -> np.ndarray:
    """Titulares de plantilla masiva: del mismo medio y el mismo día, con ≥ `min_group` − 1
    casi idénticos (similitud ≥ `sim`). Caso real: el 31-may-2026 El Tiempo publicó más de
    mil páginas "En vivo elecciones presidenciales siga la jornada de votación en
    <municipio>"; como seguimiento, se pegaban todas a un mismo evento."""
    mask = np.zeros(len(emb), dtype=bool)
    keys = day.astype(np.int64) * 16 + media
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    starts = np.flatnonzero(np.r_[True, sorted_keys[1:] != sorted_keys[:-1]])
    ends = np.r_[starts[1:], len(order)]
    for a, b in zip(starts, ends):
        if b - a < min_group:
            continue
        idx = order[a:b]
        near = (emb[idx] @ emb[idx].T >= sim).sum(axis=1) - 1
        mask[idx[near >= min_group - 1]] = True
    return mask



def candidate_edges(emb: np.ndarray, day: np.ndarray, media: np.ndarray, ventana: int, sim_min: float):
    """Vecinos de otros medios dentro de ±`ventana` días.

    Procesa un día a la vez: los titulares de ese día contra todos los de la
    ventana (un producto matricial por día). Devuelve las aristas i < j con
    similitud ≥ `sim_min` y, para cada titular y cada medio, su titular más
    parecido (índice y similitud; -1 / NaN para su propio medio o sin candidatos).
    """
    n, n_media = len(emb), int(media.max()) + 1
    order = np.argsort(day, kind="stable")
    sorted_day = day[order]
    best_sim = np.full((n, n_media), np.nan, dtype=np.float32)
    best_idx = np.full((n, n_media), -1, dtype=np.int64)
    ei, ej, es = [], [], []
    for d in np.unique(sorted_day):
        q0, q1 = np.searchsorted(sorted_day, [d, d + 1])
        c0, c1 = np.searchsorted(sorted_day, [d - ventana, d + ventana + 1])
        q, c = order[q0:q1], order[c0:c1]
        sims = emb[q] @ emb[c].T
        sims[media[q][:, None] == media[c][None, :]] = -np.inf  # sólo otros medios (y nunca él mismo)
        media_c = media[c]
        for m in range(n_media):
            cols = np.flatnonzero(media_c == m)
            if not len(cols):
                continue
            sub = sims[:, cols]
            arg = sub.argmax(axis=1)
            val = sub[np.arange(len(q)), arg]
            ok = np.isfinite(val)
            best_sim[q[ok], m] = val[ok]
            best_idx[q[ok], m] = c[cols[arg[ok]]]
        r, k = np.nonzero(sims >= sim_min)
        gi, gj = q[r], c[k]
        keep = gi < gj  # cada pareja aparece desde los dos lados: se guarda una vez
        ei.append(gi[keep])
        ej.append(gj[keep])
        es.append(sims[r, k][keep])
    i, j, s = (np.concatenate(x) if x else np.array([]) for x in (ei, ej, es))
    return i.astype(np.int64), j.astype(np.int64), s.astype(np.float32), best_sim, best_idx


def reciprocal_pairs(best_idx: np.ndarray, best_sim: np.ndarray, media: np.ndarray):
    """Parejas (i, j), i < j, en las que cada uno es el más parecido del medio del otro."""
    rows, cols = np.nonzero(best_idx >= 0)
    j = best_idx[rows, cols]
    back = best_idx[j, media[rows]]
    ok = (back == rows) & (rows < j)
    return rows[ok], j[ok], best_sim[rows[ok], cols[ok]]


# ── paso 3: eventos ──────────────────────────────────────────────────────────


def _normalize(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def build_events(emb, day, media, pi, pj, psim, umbral, max_dias=5, margen=0.10):
    """Eventos a partir de las parejas recíprocas con similitud ≥ `umbral`.

    Las componentes conexas se aceptan tal cual si tienen un titular por medio y
    duran ≤ `max_dias`. Si no (encadenamiento: A~B~C… con dos titulares del mismo
    medio o una duración larga), se parten con enlace completo sobre la distancia
    coseno, cortando en 1 − (umbral − margen): dentro de cada parte todos los
    pares quedan por encima de umbral − margen, así que una cadena no une dos
    hechos distintos. Núcleo = el titular más cercano al centroide de cada medio;
    los demás titulares de la parte quedan libres para ser seguimiento.
    """
    sel = psim >= umbral
    n = len(emb)
    graph = coo_matrix((np.ones(sel.sum()), (pi[sel], pj[sel])), shape=(n, n))
    n_comp, comp = connected_components(graph, directed=False)
    sizes = np.bincount(comp)
    multi = np.flatnonzero(sizes >= 2)
    order = np.argsort(comp, kind="stable")
    bounds = np.searchsorted(comp[order], np.arange(n_comp + 1))
    events, stats = [], {"componentes": int(len(multi)), "componente_mas_grande": int(sizes.max()) if n else 0,
                         "componentes_partidas": 0}
    for c in multi:
        members = order[bounds[c]:bounds[c + 1]]
        dup = len(np.unique(media[members])) < len(members)
        long_ = day[members].max() - day[members].min() > max_dias
        if dup or long_:
            stats["componentes_partidas"] += 1
            labels = fcluster(linkage(emb[members], method="complete", metric="cosine"),
                              t=1 - (umbral - margen), criterion="distance")
        else:
            labels = np.ones(len(members), dtype=int)
        for lab in np.unique(labels):
            part = members[labels == lab]
            if len(np.unique(media[part])) < 2:
                continue
            centroid = _normalize(emb[part].mean(axis=0))
            sims = emb[part] @ centroid
            core = []
            for m in np.unique(media[part]):
                in_m = media[part] == m
                core.append(part[in_m][sims[in_m].argmax()])
            core = np.array(sorted(core))
            centroid = _normalize(emb[core].mean(axis=0))
            events.append({
                "core": core, "centroid": centroid, "partida": bool(dup or long_),
                "inicio": int(day[core].min()), "fin": int(day[core].max()),
            })
    return events, stats


def attach_followups(emb, day, media, events, umbral, ventana, taken: np.ndarray):
    """Notas de seguimiento: titulares libres de un medio que ya está en el evento,
    a ±`ventana` días del evento y con similitud ≥ `umbral` con su centroide. Cada
    titular va al evento más parecido. Devuelve (índice, evento, similitud)."""
    if not events:
        return np.array([], int), np.array([], int), np.array([], np.float32)
    n_media = int(media.max()) + 1
    cent = np.stack([e["centroid"] for e in events]).astype(np.float32)
    start = np.array([e["inicio"] for e in events])
    end = np.array([e["fin"] for e in events])
    has_m = np.zeros((len(events), n_media), dtype=bool)
    for k, e in enumerate(events):
        has_m[k, media[e["core"]]] = True
    free = np.flatnonzero(~taken)
    free = free[np.argsort(day[free], kind="stable")]
    fd = day[free]
    out_i, out_e, out_s = [], [], []
    for d in np.unique(fd):
        q0, q1 = np.searchsorted(fd, [d, d + 1])
        q = free[q0:q1]
        ev = np.flatnonzero((start <= d + ventana) & (end >= d - ventana))
        if not len(ev):
            continue
        sims = emb[q] @ cent[ev].T
        sims[~has_m[ev][:, media[q]].T] = -np.inf  # sólo eventos donde ya está su medio
        arg = sims.argmax(axis=1)
        val = sims[np.arange(len(q)), arg]
        ok = val >= umbral
        out_i.append(q[ok])
        out_e.append(ev[arg[ok]])
        out_s.append(val[ok])
    cat = lambda x, t: np.concatenate(x).astype(t) if x else np.array([], t)  # noqa: E731
    return cat(out_i, int), cat(out_e, int), cat(out_s, np.float32)


# ── etapas ───────────────────────────────────────────────────────────────────


def _load(out: Path):
    frame = pd.read_parquet(out / "prepared.parquet", columns=[
        "article_id", "source_id", "government_id", "title", "published_date", "date_precision"])
    emb = np.load(out / "bertopic" / "embeddings.npy", mmap_mode="r")
    topics = pd.read_parquet(out / "bertopic" / "document_topics.parquet", columns=["article_id", "dominant_topic"])
    if len(emb) != len(frame) or not frame["article_id"].equals(topics["article_id"]):
        raise ValueError("prepared.parquet, embeddings.npy y document_topics.parquet no están alineados")
    keep = (frame["date_precision"] == "day").to_numpy()
    frame = frame[keep].reset_index(drop=True)
    frame["topic"] = topics["dominant_topic"].to_numpy()[keep]
    emb = np.ascontiguousarray(emb[keep], dtype=np.float32)
    frame["fecha"] = pd.to_datetime(frame["published_date"]).dt.normalize()
    day = ((frame["fecha"] - pd.Timestamp("2018-01-01")).dt.days).to_numpy()
    media = frame["source_id"].map({m: k for k, m in enumerate(MEDIA)}).to_numpy()
    plantilla = template_mask(emb, day, media)
    info = {"titulares_fecha_al_dia": int(len(frame)), "titulares_plantilla_excluidos": int(plantilla.sum()),
            "plantilla_por_medio": frame.loc[plantilla, "source_id"].value_counts().to_dict()}
    frame, emb, day, media = frame[~plantilla].reset_index(drop=True), emb[~plantilla], day[~plantilla], media[~plantilla]
    return frame, emb, day, media, info


def stage_candidatos(args, res: Path, out: Path) -> None:
    frame, emb, day, media, info = _load(out)
    t0 = time.monotonic()
    i, j, s, best_sim, best_idx = candidate_edges(emb, day, media, args.ventana_dias, args.sim_min)
    logging.info("Candidatos: %s aristas ≥ %s en %.0f s", len(i), args.sim_min, time.monotonic() - t0)
    ids = frame["article_id"].to_numpy()
    pd.DataFrame({
        "article_id_a": ids[i], "article_id_b": ids[j],
        "medio_a": frame["source_id"].to_numpy()[i], "medio_b": frame["source_id"].to_numpy()[j],
        "sim": s, "dias": np.abs(day[i] - day[j]).astype(np.int16),
    }).to_parquet(res / "aristas.parquet", index=False)
    np.savez(res / "mejores.npz", best_sim=best_sim, best_idx=best_idx)

    best = np.nanmax(np.where(np.isnan(best_sim), -np.inf, best_sim), axis=1)
    best = np.where(np.isfinite(best), best, np.nan)
    n_media_over = {t: (best_sim >= t).sum(axis=1) for t in UMBRALES_REPORTE}
    save_json(res / "candidatos.json", {
        **info, "titulares": int(len(frame)), "ventana_dias": args.ventana_dias, "sim_min": args.sim_min,
        "aristas": int(len(i)), "aristas_por_titular": float(2 * len(i) / len(frame)),
        "mejor_par_percentiles": {str(p): float(np.nanquantile(best, p)) for p in (0.1, 0.25, 0.5, 0.75, 0.9)},
        "pct_con_pareja": {str(t): float(100 * np.nanmean(best >= t)) for t in UMBRALES_REPORTE},
        "pct_con_pareja_en_2_o_mas_medios": {str(t): float(100 * (n_media_over[t] >= 2).mean())
                                             for t in UMBRALES_REPORTE},
    })
    np.save(res / "mejor_par.npy", best.astype(np.float32))


def _event_tables(frame, emb, day, media, events, fu, labels):
    rows = []
    for k, e in enumerate(events):
        sims = emb[e["core"]] @ e["centroid"]
        rows += [{"event_id": k, "idx": int(i), "sim_centroide": float(s), "es_seguimiento": False}
                 for i, s in zip(e["core"], sims)]
    fi, fe, fs = fu
    rows += [{"event_id": int(k), "idx": int(i), "sim_centroide": float(s), "es_seguimiento": True}
             for i, k, s in zip(fi, fe, fs)]
    ev = pd.DataFrame(rows)
    base = frame.iloc[ev["idx"]].reset_index(drop=True)
    ev = pd.concat([ev.drop(columns="idx"), base[["article_id", "source_id", "government_id", "fecha", "title",
                                                   "topic"]]], axis=1)
    core = ev[~ev["es_seguimiento"]]
    g = core.groupby("event_id")
    central = core.loc[g["sim_centroide"].idxmax()].set_index("event_id")
    summary = pd.DataFrame({
        "n_medios": g["source_id"].nunique(),
        "n_titulares": ev.groupby("event_id").size(),
        "n_seguimiento": ev[ev["es_seguimiento"]].groupby("event_id").size(),
        "fecha_inicio": g["fecha"].min(), "fecha_fin": g["fecha"].max(),
        "gobierno": g["government_id"].agg(lambda s: s.mode().iat[0]),
        "topic": core.groupby("event_id")["topic"].agg(lambda s: s.mode().iat[0]),
        "partida": pd.Series({k: e["partida"] for k, e in enumerate(events)}),
        "medio_central": central["source_id"], "titular_central": central["title"],
    }).fillna({"n_seguimiento": 0})
    summary["n_seguimiento"] = summary["n_seguimiento"].astype(int)
    summary["duracion_dias"] = (summary["fecha_fin"] - summary["fecha_inicio"]).dt.days
    summary["etiqueta_topic"] = summary["topic"].map(labels).fillna("(sin tópico)")
    summary.index.name = "event_id"
    return ev, summary.reset_index()


def _run_threshold(frame, emb, day, media, pi, pj, ps, umbral, args, labels):
    events, stats = build_events(emb, day, media, pi, pj, ps, umbral, args.max_dias, args.margen)
    taken = np.zeros(len(frame), dtype=bool)
    for e in events:
        taken[e["core"]] = True
    fu = attach_followups(emb, day, media, events, umbral, args.ventana_dias, taken)
    ev, summary = _event_tables(frame, emb, day, media, events, fu, labels)
    counts = summary["n_medios"].value_counts()
    stats.update({
        "umbral": umbral, "eventos": int(len(summary)),
        **{f"eventos_{k}_o_mas_medios": int((summary["n_medios"] >= k).sum()) for k in (2, 3, 4)},
        "eventos_5_medios": int(counts.get(5, 0)),
        "pct_titulares_en_nucleo": float(100 * (~ev["es_seguimiento"]).sum() / len(frame)),
        "pct_titulares_en_eventos": float(100 * len(ev) / len(frame)),
        "titulares_seguimiento": int(ev["es_seguimiento"].sum()),
        "evento_mas_grande_titulares": int(summary["n_titulares"].max()) if len(summary) else 0,
        "eventos_largos_mas_de_max_dias": int((summary["duracion_dias"] > args.max_dias).sum()),
    })
    return ev, summary, stats


def _coverage(ev: pd.DataFrame, summary: pd.DataFrame):
    """Participación de cada medio y quién publica primero, en eventos con ≥3 medios."""
    big = summary.loc[summary["n_medios"] >= 3, ["event_id", "gobierno"]]
    core = ev[~ev["es_seguimiento"]].merge(big, on="event_id")
    rows = []
    for gov, part in core.groupby("gobierno"):
        n_ev = part["event_id"].nunique()
        first_day = part.groupby("event_id")["fecha"].transform("min")
        first = part[part["fecha"] == first_day]
        # Sólo hay fecha al día: en un empate el crédito de "primero" se reparte.
        share = 1 / first.groupby("event_id")["source_id"].transform("size")
        firsts = share.groupby(first["source_id"]).sum()
        ties = (first.groupby("event_id").size() > 1).mean()
        for m in MEDIA:
            rows.append({
                "gobierno": gov, "source_id": m, "eventos_3_mas_medios": int(n_ev),
                "pct_participa": float(100 * part.loc[part["source_id"] == m, "event_id"].nunique() / n_ev),
                "pct_publica_primero": float(100 * firsts.get(m, 0.0) / n_ev),
                "pct_eventos_con_empate_el_primer_dia": float(100 * ties),
            })
    return pd.DataFrame(rows)


def _examples_md(ev: pd.DataFrame, summary: pd.DataFrame, umbral: float, seed: int) -> str:
    big = summary[summary["n_medios"] >= 3]
    rng = np.random.default_rng(seed)
    pick = list(rng.choice(big["event_id"].to_numpy(), size=min(15, len(big)), replace=False))
    largest = big.sort_values(["n_titulares", "n_medios"], ascending=False)["event_id"].head(5).tolist()
    lines = [
        f"# Ejemplos de eventos (umbral {umbral:.2f})", "",
        "Para revisar a ojo si los titulares de cada evento hablan del mismo hecho.",
        "15 eventos con ≥3 medios elegidos al azar",
        f"(semilla {seed}) y los 5 más grandes. Titulares reconstruidos desde la URL (sin tildes ni cifras).", "",
    ]
    for title, ids in (("Eventos al azar", pick), ("Los eventos más grandes", largest)):
        lines += [f"## {title}", ""]
        for k in ids:
            s = summary.set_index("event_id").loc[k]
            lines += [f"### Evento {k} · {s['n_medios']} medios · {s['fecha_inicio']:%Y-%m-%d} → "
                      f"{s['fecha_fin']:%Y-%m-%d} · {s['etiqueta_topic']}", "",
                      "| Medio | Fecha | Tipo | Sim. | Titular |", "|---|---|---|---:|---|"]
            part = ev[ev["event_id"] == k].sort_values(["es_seguimiento", "fecha", "source_id"])
            for r in part.itertuples():
                tipo = "seguimiento" if r.es_seguimiento else "núcleo"
                lines.append(f"| {figuras.MEDIA_NAMES[r.source_id]} | {r.fecha:%Y-%m-%d} | {tipo} | "
                             f"{r.sim_centroide:.2f} | {r.title} |")
            lines.append("")
    return "\n".join(lines)


def _calibration(umbral: float) -> dict:
    """Precisión medida a mano para este umbral (calibracion.py evaluar), si existe."""
    path = HERE / "resultados_publico" / "calibracion" / "precision_por_umbral.csv"
    if not path.exists():
        return {"calibrado": False}
    tab = pd.read_csv(path)
    row = tab[np.isclose(tab["umbral"], umbral)]
    if row.empty:
        return {"calibrado": False}
    r = row.iloc[0]
    ev = load_json(path.parent / "evaluacion.json")
    return {"calibrado": True, "precision": round(float(r.precision), 4),
            "ic95": [round(float(r.ic_bajo), 4), round(float(r.ic_alto), 4)],
            "n_muestra": int(r.n_muestra), "kappa_mismo_hecho": round(ev["kappa_mismo_hecho"], 4)}


def stage_eventos(args, res: Path, out: Path) -> None:
    frame, emb, day, media, _ = _load(out)
    data = np.load(res / "mejores.npz")
    pi, pj, ps = reciprocal_pairs(data["best_idx"], data["best_sim"], media)
    logging.info("Parejas recíprocas: %s", len(pi))
    labels_path = HERE / "labels" / "publico_bertopic.csv"
    labels = dict(pd.read_csv(labels_path)[["topic", "etiqueta"]].itertuples(index=False)) if labels_path.exists() else {}
    sens = []
    main = None
    for umbral in sorted(set(args.umbrales) | {args.umbral}):
        ev, summary, stats = _run_threshold(frame, emb, day, media, pi, pj, ps, umbral, args, labels)
        stats["parejas_reciprocas"] = int((ps >= umbral).sum())
        sens.append(stats)
        logging.info("umbral %.2f: %s eventos (%s con ≥3 medios), componente más grande %s", umbral,
                     stats["eventos"], stats["eventos_3_o_mas_medios"], stats["componente_mas_grande"])
        if umbral == args.umbral:
            main = (ev, summary, stats)
    pd.DataFrame(sens).to_csv(res / "sensibilidad_umbral.csv", index=False)
    ev, summary, stats = main
    ev.drop(columns="topic").to_parquet(res / "eventos.parquet", index=False)
    summary.to_csv(res / "eventos_resumen.csv", index=False)
    cov = _coverage(ev, summary)
    cov.to_csv(res / "cobertura_eventos.csv", index=False)
    (res / "ejemplos_eventos.md").write_text(_examples_md(ev, summary, args.umbral, args.seed), encoding="utf-8")
    by_gov = summary[summary["n_medios"] >= 3].groupby("gobierno").size().to_dict()
    save_json(res / "eventos.json", {
        **stats, "calibracion": _calibration(args.umbral), "ventana_dias": args.ventana_dias, "max_dias": args.max_dias,
        "margen_particion": args.margen, "eventos_3_o_mas_medios_por_gobierno": {k: int(v) for k, v in by_gov.items()},
        "eventos_por_n_medios": {str(k): int(v) for k, v in summary["n_medios"].value_counts().sort_index().items()},
    })

    cand = load_json(res / "candidatos.json")
    figuras.eventos_similitud(np.load(res / "mejor_par.npy"), args.umbral, sorted(args.umbrales), cand, res)
    figuras.eventos_por_medios(summary, args.umbral, res)
    figuras.eventos_sensibilidad(pd.DataFrame(sens), args.umbral, res)
    figuras.eventos_por_mes(summary, args.umbral, res)
    figuras.eventos_participacion(cov, args.umbral, res)


STAGES = {"candidatos": stage_candidatos, "eventos": stage_eventos}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=HERE / "resultados_publico")
    parser.add_argument("--stage", choices=[*STAGES, "all"], default="all")
    parser.add_argument("--ventana-dias", type=int, default=2)
    parser.add_argument("--sim-min", type=float, default=0.60)
    parser.add_argument("--umbral", type=float, default=0.80, help="Umbral calibrado (calibracion.py evaluar)")
    parser.add_argument("--umbrales", type=float, nargs="+", default=[0.70, 0.75, 0.80, 0.85, 0.90])
    parser.add_argument("--max-dias", type=int, default=5)
    parser.add_argument("--margen", type=float, default=0.10,
                        help="Al partir componentes encadenadas: todos los pares ≥ umbral − margen")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = args.output.resolve()
    res = out / "eventos"
    (res / "figuras").mkdir(parents=True, exist_ok=True)
    for name in (list(STAGES) if args.stage == "all" else [args.stage]):
        t0 = time.monotonic()
        logging.info("== etapa %s", name)
        STAGES[name](args, res, out)
        logging.info("== %s terminada en %.0f s", name, time.monotonic() - t0)


if __name__ == "__main__":
    main()
