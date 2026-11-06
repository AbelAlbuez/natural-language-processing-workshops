"""Calibración manual del emparejamiento de titulares entre medios (paso 2).

    muestra   parejas recíprocas entre medios (las mismas que usa eventos.py),
              estratificadas por similitud, en orden aleatorio
    planilla  resultados_publico/calibracion/planilla_calibracion.xlsx para el equipo
              (sin la similitud, para no sesgar a quien anota)
    dividir   una planilla por persona para dos anotadores en paralelo: las parejas
              dobles en las dos, las demás repartidas por tramo
    evaluar   lee la planilla llena: precisión por tramo y por umbral, acuerdo
              entre anotadores (kappa de Cohen) y umbral recomendado

Pareja recíproca: B es el titular más parecido del medio de B para A (±2 días)
y A es el más parecido del medio de A para B. Es el criterio de eventos.py, así
que la precisión medida aquí es la del método.

Uso (en la imagen duque-petro-lda:local, desde entrega3/):
    python calibracion.py muestra
    python calibracion.py planilla
    python calibracion.py dividir
    python calibracion.py evaluar --personas planilla_persona_1.xlsx planilla_persona_2.xlsx
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "resultados_publico"
OUT = DATA / "calibracion"
MEDIA = ["el_tiempo", "blu_radio", "noticias_rcn", "noticias_caracol", "la_republica"]
NOMBRES = {"el_tiempo": "El Tiempo", "blu_radio": "Blu Radio", "noticias_rcn": "Noticias RCN",
           "noticias_caracol": "Noticias Caracol", "la_republica": "La República"}
# Tramos de similitud: cubren desde lo que casi nunca es el mismo hecho hasta
# lo que casi siempre lo es, para ubicar dónde se cruza el umbral.
TRAMOS = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.0001]
# Sin comas: en la validación de Excel la coma separa opciones.
ETIQUETAS = ["Mismo hecho", "Mismo tema / otro hecho", "Distinto", "No se puede saber"]


def tramo(sim: float) -> str:
    for lo, hi in zip(TRAMOS, TRAMOS[1:]):
        if lo <= sim < hi:
            return f"{lo:.2f}–{min(hi, 1):.2f}"
    return "<0.60"


def reciprocal_pairs(dates: np.ndarray, media: np.ndarray, emb: np.ndarray, queries: np.ndarray,
                     window_days: int = 2, sim_min: float = 0.60) -> pd.DataFrame:
    """Parejas recíprocas (a, b) de medios distintos con similitud ≥ sim_min.

    `dates` en días enteros. Para cada consulta a y cada otro medio, se busca su
    mejor b en ±window_days y se comprueba que a sea el mejor de b en el medio de a.
    """
    by_medium = {}
    for m in np.unique(media):
        idx = np.flatnonzero(media == m)
        idx = idx[np.argsort(dates[idx], kind="stable")]
        by_medium[m] = (idx, dates[idx])

    def best_in(i, medium):
        idx, d = by_medium[medium]
        lo, hi = np.searchsorted(d, [dates[i] - window_days, dates[i] + window_days + 1])
        if lo == hi:
            return -1, -1.0
        cand = idx[lo:hi]
        sims = emb[cand] @ emb[i]
        k = int(np.argmax(sims))
        return int(cand[k]), float(sims[k])

    rows, seen = [], set()
    for a in queries:
        for m in by_medium:
            if m == media[a]:
                continue
            b, sim = best_in(a, m)
            if b < 0 or sim < sim_min:
                continue
            back, _ = best_in(b, media[a])
            key = (min(a, b), max(a, b))
            if back == a and key not in seen:
                seen.add(key)
                rows.append({"a": a, "b": b, "sim": sim})
    return pd.DataFrame(rows, columns=["a", "b", "sim"])


def population_by_tramo(force: bool = False) -> pd.Series:
    """Cuántas parejas recíprocas del corpus completo caen en cada tramo.

    Son las parejas a las que se aplica el umbral en eventos.py (mismo `_load`,
    mismas exclusiones de plantilla). Se guarda en poblacion_tramos.csv.
    """
    path = OUT / "poblacion_tramos.csv"
    if path.exists() and not force:
        return pd.read_csv(path).set_index("tramo")["parejas"]
    import eventos

    _, _, _, media, _ = eventos._load(DATA)
    data = np.load(DATA / "eventos" / "mejores.npz")
    _, _, sims = eventos.reciprocal_pairs(data["best_idx"], data["best_sim"], media)
    counts = pd.Series([tramo(float(x)) for x in sims]).value_counts()
    counts = counts.drop("<0.60", errors="ignore").sort_index().rename("parejas")
    counts.rename_axis("tramo").reset_index().to_csv(path, index=False)
    return counts


def weighted_precision(d1: pd.DataFrame, population: pd.Series) -> pd.DataFrame:
    """Precisión de quedarse con las parejas ≥ cada umbral, ponderada por población.

    La muestra tiene el mismo número de parejas por tramo, pero en el corpus los
    tramos bajos son mucho más frecuentes; sin ponderar, la precisión ≥ u se
    sobrestima. Estimador estratificado: Σ W_t p_t, con W_t = N_t / Σ N_t sobre los
    tramos ≥ u. IC 95 % normal con varianza Σ W_t² p̃_t(1 − p̃_t)/n_t, donde
    p̃_t = (x + 1)/(n + 2) evita varianza cero en tramos con 0 % o 100 %.
    """
    stats = d1.groupby("tramo")["acierto"].agg(["sum", "count"])
    rows = []
    for u in TRAMOS[:-1]:
        ts = [t for t in stats.index if float(t.split("–")[0]) >= u - 1e-9 and t in population.index]
        if not ts:
            continue
        w = population[ts] / population[ts].sum()
        x, n = stats.loc[ts, "sum"], stats.loc[ts, "count"]
        p = x / n
        pt = (x + 1) / (n + 2)
        prec = float((w * p).sum())
        se = float(np.sqrt((w**2 * pt * (1 - pt) / n).sum()))
        rows.append({"umbral": u, "parejas_corpus": int(population[ts].sum()), "n_muestra": int(n.sum()),
                     "precision": prec, "ic_bajo": max(0.0, prec - 1.96 * se),
                     "ic_alto": min(1.0, prec + 1.96 * se)})
    return pd.DataFrame(rows)


def stratified(pairs: pd.DataFrame, per_bin: int, seed: int) -> pd.DataFrame:
    pairs = pairs.assign(tramo=pairs["sim"].map(tramo))
    pairs = pairs[pairs["tramo"] != "<0.60"]
    parts = [g.sample(min(per_bin, len(g)), random_state=seed) for _, g in pairs.groupby("tramo")]
    return pd.concat(parts).sample(frac=1, random_state=seed).reset_index(drop=True)


def stage_muestra(args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(DATA / "prepared.parquet", columns=[
        "article_id", "url", "source_id", "government_id", "title", "published_date", "date_precision"])
    emb = np.load(DATA / "bertopic" / "embeddings.npy")
    day = (frame["date_precision"] == "day").to_numpy()
    dates = (pd.to_datetime(frame["published_date"]).dt.normalize()
             - pd.Timestamp("2018-01-01")).dt.days.to_numpy()
    media = frame["source_id"].to_numpy()
    # Mismo filtro que eventos.py: fuera las plantillas masivas (p. ej. >1.000 páginas
    # "En vivo elecciones… en <municipio>" de El Tiempo el mismo día).
    from eventos import template_mask

    codes = pd.factorize(media)[0]
    plantilla = np.zeros(len(frame), dtype=bool)
    sub = np.flatnonzero(day)
    plantilla[sub] = template_mask(emb[sub], dates[sub], codes[sub])
    logging.info("Excluidos %s titulares de plantilla masiva", plantilla.sum())
    day = day & ~plantilla
    keep = np.flatnonzero(day)
    rng = np.random.default_rng(args.seed)
    queries = rng.choice(keep, size=min(args.consultas, len(keep)), replace=False)
    # Sólo titulares con fecha al día entran como candidatos.
    emb_day = emb.copy()
    emb_day[~day] = 0
    logging.info("Buscando parejas recíprocas para %s consultas", len(queries))
    pairs = reciprocal_pairs(np.where(day, dates, -10_000), media, emb_day, queries)
    pairs = pairs[day[pairs["b"]]]
    logging.info("%s parejas recíprocas con similitud ≥ 0,60", len(pairs))
    sample = stratified(pairs, args.por_tramo, args.seed)

    rows, key = [], []
    for n, r in enumerate(sample.itertuples(), start=1):
        a, b = (r.a, r.b) if rng.random() < 0.5 else (r.b, r.a)  # orden A/B al azar
        fa, fb = frame.iloc[a], frame.iloc[b]
        pid = f"P{n:03d}"
        rows.append({
            "pareja": pid, "doble": "Sí" if n <= args.dobles else "No",
            "medio_a": NOMBRES[fa.source_id], "fecha_a": str(fa.published_date)[:10], "titular_a": fa.title,
            "url_a": fa.url, "medio_b": NOMBRES[fb.source_id], "fecha_b": str(fb.published_date)[:10],
            "titular_b": fb.title, "url_b": fb.url,
        })
        key.append({"pareja": pid, "article_id_a": int(fa.article_id), "article_id_b": int(fb.article_id),
                    "similitud": round(r.sim, 4), "tramo": r.tramo,
                    "gobierno_a": fa.government_id, "gobierno_b": fb.government_id})
    pd.DataFrame(rows).to_csv(OUT / "muestra.csv", index=False)
    pd.DataFrame(key).to_csv(OUT / "clave_no_abrir.csv", index=False)
    resumen = pd.DataFrame(key).groupby("tramo").size().to_dict()
    json.dump({"consultas": int(len(queries)), "parejas_reciprocas": int(len(pairs)), "por_tramo": resumen,
               "plantilla_excluidos": int(plantilla.sum()),
               "dobles": args.dobles, "semilla": args.seed}, open(OUT / "muestra.json", "w"),
              ensure_ascii=False, indent=2)
    logging.info("Muestra: %s parejas; por tramo %s", len(rows), resumen)


# ── planilla ─────────────────────────────────────────────────────────────────


def build_workbook(muestra: pd.DataFrame, path: Path, persona: int | None = None) -> None:
    """Planilla de anotación. Con `persona`, una sola columna de respuesta (cada
    persona en su propio archivo, sin ver las respuestas de la otra); sin ella,
    dos anotadores en el mismo archivo."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    base = Font(name="Arial", size=10)
    bold = Font(name="Arial", size=10, bold=True)
    title = Font(name="Arial", size=14, bold=True)
    head_fill = PatternFill("solid", fgColor="D9D9D9")
    input_fill = PatternFill("solid", fgColor="FFFF00")
    double_fill = PatternFill("solid", fgColor="DDEBF7")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical="top")
    n_dobles = int((muestra["doble"] == "Sí").sum())

    # ── Instrucciones
    ws = wb.active
    ws.title = "Instrucciones"
    if persona:
        quien = [
            (f"Planilla de la persona {persona}: {len(muestra)} parejas. Su compañero o compañera tiene la otra "
             f"planilla. Las {n_dobles} parejas marcadas «doble = Sí» (en azul) están en las dos planillas: "
             "anótelas sin consultar con la otra persona, porque sirven para medir el acuerdo entre ustedes.", base),
            ("1. En la hoja «Anotación», escriba su nombre en «Anotador · nombre» (basta en la primera fila).", base),
            ("2. Elija una opción en «¿Mismo hecho?» con la lista desplegable. Sólo edite las celdas amarillas.", base),
        ]
    else:
        quien = [
            (f"Hay {len(muestra)} parejas. Las {n_dobles} marcadas «doble = Sí» (en azul) deben anotarlas dos "
             "personas distintas, sin ver la respuesta de la otra: sirven para medir el acuerdo.", base),
            ("1. En la hoja «Anotación», escriba su nombre en «Anotador 1 · nombre» (o «Anotador 2» si la fila ya "
             "tiene un primer anotador).", base),
            ("2. Elija una opción en «¿Mismo hecho?» con la lista desplegable. Sólo edite las celdas amarillas.", base),
        ]
    lines = [
        ("Calibración del emparejamiento de titulares entre medios", title),
        ("", base),
        ("Para qué sirve", bold),
        ("Cada fila es una pareja de titulares de dos medios distintos, publicados con ±2 días de diferencia, que el "
         "método considera candidatos a ser el mismo hecho. Las respuestas permiten medir qué tan seguido acierta y "
         "elegir el umbral de similitud.", base),
        ("", base),
        ("Qué hacer", bold),
        *quien,
        ("3. Si duda, abra los enlaces: el titular viene reconstruido desde la URL (sin tildes, cifras ni "
         "puntuación) y la página muestra el titular publicado.", base),
        ("4. No abra el archivo clave_no_abrir.csv: tiene la similitud de cada pareja y sesgaría la respuesta.", base),
        ("", base),
        ("Opciones", bold),
        ("Mismo hecho: el mismo acontecimiento, declaración, decisión o dato concreto, aunque esté redactado distinto o "
         "destaque otro aspecto. Ej.: «Gobierno y Fecode anunciaron que llegaron a un acuerdo» / «Fecode logró acuerdo "
         "con el gobierno para mejorar la educación».", base),
        ("Mismo tema / otro hecho: tratan el mismo asunto pero son hechos distintos (otro día de la noticia, otra "
         "declaración, otro caso). Ej.: dos notas sobre la reforma pensional, una del aval fiscal y otra de una "
         "crítica de Asofondos.", base),
        ("Distinto: no tienen relación salvo palabras sueltas.", base),
        ("No se puede saber: el titular reconstruido no permite decidir ni con la página abierta.", base),
        ("", base),
        ("Leyenda", bold),
        ("Celdas amarillas: las que usted edita. Filas azules: pareja doble. Todo lo demás es fijo.", base),
        ("", base),
        ("Ejemplo de fila anotada (no forma parte de la muestra)", bold),
    ]
    for r, (text, font) in enumerate(lines, start=1):
        c = ws.cell(row=r, column=1, value=text)
        c.font, c.alignment = font, Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 120
    who = "Anotador" if persona else "Anotador 1"
    # Ejemplo en vertical: la columna A es ancha para el texto de las instrucciones.
    example = [
        ("pareja · doble", "P000 · No", False),
        ("Titular A (La República, 2021-08-07)",
         "Gobierno y fecode anunciaron que llegaron a un acuerdo sobre condiciones de maestros", False),
        ("Titular B (Noticias Caracol, 2021-08-07)", "Fecode logro acuerdo con el gobierno para mejorar la educacion",
         False),
        (f"{who} · nombre", "Ana Pérez", True),
        (f"{who} · ¿mismo hecho?", "Mismo hecho", True),
        (f"{who} · comentario", "Misma reunión; Caracol destaca la educación", True),
    ]
    for k, (field, value, editable) in enumerate(example, start=len(lines) + 1):
        c = ws.cell(row=k, column=1, value=f"{field}:  {value}")
        c.font, c.border, c.alignment = base, border, Alignment(wrap_text=True, vertical="top")
        if editable:
            c.fill = input_fill

    # ── Anotación
    an = wb.create_sheet("Anotación")
    blocks = ["Anotador"] if persona else ["Anotador 1", "Anotador 2"]
    headers = ["pareja", "doble", "medio A", "fecha A", "titular A", "enlace A", "medio B", "fecha B", "titular B",
               "enlace B"]
    widths = [8, 7, 15, 11, 50, 9, 15, 11, 50, 9]
    for b in blocks:
        headers += [f"{b} · nombre", f"{b} · ¿mismo hecho?", f"{b} · comentario"]
        widths += [16, 22, 28]
    for j, (h, w) in enumerate(zip(headers, widths), start=1):
        c = an.cell(row=1, column=j, value=h)
        c.font, c.fill, c.border, c.alignment = bold, head_fill, border, Alignment(wrap_text=True, vertical="center")
        an.column_dimensions[c.column_letter].width = w
    an.freeze_panes = "C2"
    an.row_dimensions[1].height = 30
    dv = DataValidation(type="list", formula1='"' + ",".join(ETIQUETAS) + '"', allow_blank=True,
                        showErrorMessage=True, errorTitle="Opción no válida", error="Elija una opción de la lista.")
    an.add_data_validation(dv)
    decision_cols = [12 + 3 * k for k in range(len(blocks))]  # L, O
    for i, r in enumerate(muestra.itertuples(), start=2):
        values = [r.pareja, r.doble, r.medio_a, r.fecha_a, r.titular_a, "abrir", r.medio_b, r.fecha_b, r.titular_b,
                  "abrir"] + [None] * (3 * len(blocks))
        for j, v in enumerate(values, start=1):
            c = an.cell(row=i, column=j, value=v)
            c.font, c.border, c.alignment = base, border, wrap
            if r.doble == "Sí" and j <= 10:
                c.fill = double_fill
        for j, url in ((6, r.url_a), (10, r.url_b)):
            c = an.cell(row=i, column=j)
            c.hyperlink = url
            c.font = Font(name="Arial", size=10, color="0563C1", underline="single")
        active = blocks if (persona or r.doble == "Sí") else blocks[:1]
        for k in range(len(active)):
            for j in range(11 + 3 * k, 14 + 3 * k):
                an.cell(row=i, column=j).fill = input_fill
            dv.add(an.cell(row=i, column=decision_cols[k]).coordinate)
    last = len(muestra) + 1

    # ── Progreso (fórmulas: se actualiza al anotar)
    pg = wb.create_sheet("Progreso")
    pg["A1"], pg["A1"].font = "Progreso de la anotación", title
    col1 = an.cell(row=1, column=decision_cols[0]).column_letter
    rows = [
        ("Parejas en esta planilla", f"=COUNTA('Anotación'!A2:A{last})"),
        ("Parejas dobles", f"=COUNTIF('Anotación'!B2:B{last},\"Sí\")"),
        (f"Anotadas ({blocks[0]})", f"=COUNTA('Anotación'!{col1}2:{col1}{last})"),
        (f"% anotado ({blocks[0]})", "=IFERROR(B5/B3,0)"),
    ]
    if not persona:
        col2 = an.cell(row=1, column=decision_cols[1]).column_letter
        rows += [("Dobles anotadas (Anotador 2)", f"=COUNTA('Anotación'!{col2}2:{col2}{last})"),
                 ("% de dobles con segundo anotador", "=IFERROR(B7/B4,0)")]
    for k, (label, formula) in enumerate(rows, start=3):
        pg.cell(row=k, column=1, value=label).font = base
        c = pg.cell(row=k, column=2, value=formula)
        c.font = base
        if label.startswith("%"):
            c.number_format = "0.0%"
    start_counts = 3 + len(rows) + 1
    pg.cell(row=start_counts, column=1, value=f"Respuestas ({blocks[0]})").font = bold
    for k, label in enumerate(ETIQUETAS, start=start_counts + 1):
        pg.cell(row=k, column=1, value=label).font = base
        pg.cell(row=k, column=2, value=f"=COUNTIF('Anotación'!{col1}2:{col1}{last},A{k})").font = base
    pg.column_dimensions["A"].width = 38
    pg.column_dimensions["B"].width = 12
    wb.save(path)
    logging.info("Planilla: %s (%s parejas, %s dobles)", path, len(muestra), n_dobles)


def split_for_two(muestra: pd.DataFrame, key: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reparte la muestra entre dos personas: las dobles van a las dos; las demás
    se alternan dentro de cada tramo de similitud, para que ninguna se quede con
    los casos fáciles o los difíciles."""
    merged = muestra.merge(key[["pareja", "tramo"]], on="pareja")
    dobles = merged[merged["doble"] == "Sí"]
    # Ordenadas por tramo y alternadas en una sola secuencia: el reparto queda
    # exacto (75/75) y cada tramo también se divide casi a la mitad.
    simples = merged[merged["doble"] != "Sí"].sample(frac=1, random_state=seed).sort_values("tramo", kind="stable")
    simples = simples.assign(_k=np.arange(len(simples)) % 2)
    order = lambda d: d.sample(frac=1, random_state=seed)[muestra.columns].reset_index(drop=True)  # noqa: E731
    p1 = order(pd.concat([dobles, simples[simples["_k"] == 0]]))
    p2 = order(pd.concat([dobles, simples[simples["_k"] == 1]]))
    return p1, p2


def stage_planilla(args) -> None:
    build_workbook(pd.read_csv(OUT / "muestra.csv"), OUT / "planilla_calibracion.xlsx")


def stage_dividir(args) -> None:
    muestra = pd.read_csv(OUT / "muestra.csv")
    key = pd.read_csv(OUT / "clave_no_abrir.csv")
    for n, part in enumerate(split_for_two(muestra, key, args.seed), start=1):
        build_workbook(part, OUT / f"planilla_persona_{n}.xlsx", persona=n)


# ── evaluar ──────────────────────────────────────────────────────────────────


def cohen_kappa(a: list[str], b: list[str]) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def combine_personas(sheets: list[pd.DataFrame]) -> pd.DataFrame:
    """Une las planillas por persona en el formato de dos anotadores: la persona 1
    es «Anotador 1» y la 2 es «Anotador 2» en las dobles; en las parejas simples,
    la respuesta de quien la tenga va como «Anotador 1»."""
    cols = ["nombre", "¿mismo hecho?", "comentario"]
    rows = {}
    for n, sheet in enumerate(sheets, start=1):
        for r in sheet.to_dict("records"):
            entry = rows.setdefault(r["pareja"], {"pareja": r["pareja"], "doble": r["doble"]})
            slot = "Anotador 1" if (n == 1 or r["doble"] != "Sí") else "Anotador 2"
            for c in cols:
                entry[f"{slot} · {c}"] = r.get(f"Anotador · {c}")
    out = pd.DataFrame(rows.values())
    for slot in ("Anotador 1", "Anotador 2"):
        for c in cols:
            out[f"{slot} · {c}"] = out.get(f"{slot} · {c}")
    return out


def stage_evaluar(args) -> None:
    import sys

    sys.path.insert(0, str(HERE.parent / "entrega2"))
    from research_stats import wilson_interval

    key = pd.read_csv(OUT / "clave_no_abrir.csv")
    if args.personas:
        ann = combine_personas([pd.read_excel(p, sheet_name="Anotación") for p in args.personas])
    else:
        ann = pd.read_excel(args.planilla, sheet_name="Anotación")
    df = ann.merge(key, on="pareja", validate="one_to_one")
    d1 = df.dropna(subset=["Anotador 1 · ¿mismo hecho?"])
    d1 = d1[d1["Anotador 1 · ¿mismo hecho?"] != "No se puede saber"]
    d1 = d1.assign(acierto=d1["Anotador 1 · ¿mismo hecho?"].eq("Mismo hecho"))
    por_tramo = []
    for t, g in d1.groupby("tramo"):
        lo, hi = wilson_interval(int(g["acierto"].sum()), len(g))
        por_tramo.append({"tramo": t, "n": len(g), "precision": g["acierto"].mean(), "ic_bajo": lo, "ic_alto": hi})
    umbrales = []
    for u in TRAMOS[:-1]:
        g = d1[d1["similitud"] >= u]
        if len(g):
            lo, hi = wilson_interval(int(g["acierto"].sum()), len(g))
            umbrales.append({"umbral": u, "n": len(g), "precision": g["acierto"].mean(), "ic_bajo": lo, "ic_alto": hi})
    umbrales = pd.DataFrame(umbrales)
    ponderada = weighted_precision(d1, population_by_tramo())
    ok = ponderada[ponderada["precision"] >= args.precision_objetivo]
    dobles = df.dropna(subset=["Anotador 1 · ¿mismo hecho?", "Anotador 2 · ¿mismo hecho?"])
    a1, a2 = dobles["Anotador 1 · ¿mismo hecho?"].tolist(), dobles["Anotador 2 · ¿mismo hecho?"].tolist()
    binario = lambda xs: ["si" if x == "Mismo hecho" else "no" for x in xs]  # noqa: E731
    result = {
        "anotadas": int(len(d1)),
        "umbral_recomendado": float(ok["umbral"].min()) if len(ok) else None,
        "precision_objetivo": args.precision_objetivo,
        "criterio": "menor umbral con precisión ponderada por la población de parejas ≥ objetivo",
        "precision_ponderada": {f"{r.umbral:.2f}": round(r.precision, 4) for r in ponderada.itertuples()},
        "kappa_4_clases": cohen_kappa(a1, a2), "kappa_mismo_hecho": cohen_kappa(binario(a1), binario(a2)),
        "parejas_dobles_anotadas": int(len(dobles)),
    }
    pd.DataFrame(por_tramo).to_csv(OUT / "precision_por_tramo.csv", index=False)
    umbrales.to_csv(OUT / "precision_por_umbral_sin_ponderar.csv", index=False)
    ponderada.to_csv(OUT / "precision_por_umbral.csv", index=False)
    json.dump(result, open(OUT / "evaluacion.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(ponderada.round(3).to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapa", choices=["muestra", "planilla", "dividir", "evaluar"])
    parser.add_argument("--consultas", type=int, default=30_000)
    parser.add_argument("--por-tramo", type=int, default=30)
    parser.add_argument("--dobles", type=int, default=60, help="Parejas que anotan dos personas (acuerdo)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--planilla", type=Path, default=OUT / "planilla_calibracion.xlsx")
    parser.add_argument("--personas", type=Path, nargs="+", default=None,
                        help="Planillas por persona (de la etapa dividir) en vez de --planilla")
    parser.add_argument("--precision-objetivo", type=float, default=0.90)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    {"muestra": stage_muestra, "planilla": stage_planilla, "dividir": stage_dividir,
     "evaluar": stage_evaluar}[args.etapa](args)


if __name__ == "__main__":
    main()
