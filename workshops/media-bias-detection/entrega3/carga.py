"""Lenguaje evaluativo o cargado en los titulares, dentro del mismo hecho.

No es análisis de sentimiento (el proyecto no usa el sentimiento como medida de
sesgo). Se cuentan palabras que añaden un juicio al hecho («polémica»,
«fracaso», «caos», «arremete», «logro», «histórico»…) con un léxico curado a
mano (`lexico_carga.csv`, sin tildes, con variantes y exclusiones de contexto),
y se compara cada medio con los otros medios EN LOS MISMOS EVENTOS (diseño
emparejado de `lexico.py`): un hecho negativo produce palabras negativas en
todos los medios, así que sólo la diferencia dentro del evento habla de cómo lo
cuenta cada uno.

    1. Por medio × gobierno: % de titulares núcleo con carga negativa, positiva
       o cualquiera, frente a los otros medios en los mismos eventos (bootstrap
       por eventos); cambio Petro − Duque.
    2. Carga dirigida al gobierno: titulares que nombran al gobierno o al
       presidente (formas de `lexico.formas_nombrar`, simétricas) y llevan carga.
    3. Por tema de BERTopic.
    4. Ejemplos (ejemplos_carga.md).
    5. Robustez: con seguimiento, sin RCN entre los otros, ventana común en
       Duque, bootstrap por meses y sin las 10 entradas más frecuentes del léxico.

Etapas:
    --etapa validar   contextos (KWIC) de cada entrada → validacion_lexico.md
    --etapa analizar  todo lo demás (por defecto)

Uso: SCRIPT=carga.py ./run.sh - --output resultados_publico
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

from figuras import (AXIS, FUENTE, GOV_COLORS, GOV_NAMES, INK2, MEDIA_NAMES, MUTED, NOTA_UMBRAL, SHORT, SURFACE,
                     _margins, _save)
from lexico import (RCN, TEMAS_EXCLUIDOS_POR_TEMA, TEMAS_EXTERIOR, _r, bh_adjust, cargar, formas_nombrar,
                    matrices_emparejadas, pesos_bootstrap, precision_fecha_rcn, recorte_rcn)
from research_stats import wilson_interval
from topics import GOVS, MEDIA, save_json

HERE = Path(__file__).resolve().parent
LEXICO = HERE / "lexico_carga.csv"
POLARIDADES = ("negativa", "positiva", "neutra")
TIPOS = ("juicio", "intensificador", "sensacionalismo", "conflicto", "atribucion_cargada", "atribucion_neutra")
# Indicadores por titular (columnas de la matriz que se compara entre medios)
INDICADORES = {
    "negativa": "alguna palabra con carga negativa",
    "positiva": "alguna palabra con carga positiva",
    "carga": "alguna palabra cargada (negativa, positiva o intensificador sin polaridad)",
    "neto": "negativa − positiva (−1, 0, 1)",
    "atrib_cargada": "verbo de atribución cargado («arremetió», «admitió»)",
    "atrib_neutra": "verbo de atribución neutro («dijo», «afirmó»)",
}
# Índices como cociente de sumas sobre los eventos (numerador, denominador)
RAZONES = {"cargada_entre_atribucion": ("atrib_cargada", "atrib_alguna")}


# ── léxico ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Entrada:
    id: str
    polaridad: str
    tipo: str
    patron: re.Pattern
    excluir: re.Pattern | None
    origen: str = "a_priori"


def leer_lexico(path: Path = LEXICO) -> pd.DataFrame:
    tab = pd.read_csv(path, dtype=str, keep_default_na=False)
    malas = tab[~tab["polaridad"].isin(POLARIDADES) | ~tab["tipo"].isin(TIPOS) | ~tab["activa"].isin(["si", "no"])]
    if len(malas):
        raise ValueError(f"Entradas con polaridad, tipo o activa inválidos: {malas['id'].tolist()}")
    if tab["id"].duplicated().any():
        raise ValueError(f"ids repetidos: {tab.loc[tab['id'].duplicated(), 'id'].tolist()}")
    return tab


def compilar(tab: pd.DataFrame, solo_activas: bool = True) -> list[Entrada]:
    """Una expresión por entrada: `formas` (alternativas, sin tildes) entre
    límites de palabra; `excluir`, contextos que anulan una coincidencia que
    quede dentro de ellos («golpe de calor», «pacto historico»)."""
    if solo_activas:
        tab = tab[tab["activa"] == "si"]
    return [Entrada(r.id, r.polaridad, r.tipo, re.compile(rf"\b(?:{r.formas})\b"),
                    re.compile(rf"\b(?:{r.excluir})\b") if r.excluir else None, r.origen)
            for r in tab.itertuples()]


def coincidencias(texto: str, e: Entrada) -> list[re.Match]:
    """Coincidencias de la entrada en un titular normalizado (`core.normalize`),
    sin las que caen dentro de un contexto excluido."""
    ms = list(e.patron.finditer(texto))
    if not ms or e.excluir is None:
        return ms
    spans = [x.span() for x in e.excluir.finditer(texto)]
    return [m for m in ms if not any(a <= m.start() and m.end() <= b for a, b in spans)]


def detectar(texto: str, lexico: list[Entrada]) -> set[str]:
    """ids de las entradas presentes en el titular."""
    return {e.id for e in lexico if coincidencias(texto, e)}


def matriz_entradas(textos, lexico: list[Entrada]) -> pd.DataFrame:
    """Titular × entrada (booleana)."""
    textos = list(textos)
    return pd.DataFrame({e.id: [bool(coincidencias(t, e)) for t in textos] for e in lexico})


def indicadores(E: pd.DataFrame, lexico: list[Entrada], quitar=()) -> pd.DataFrame:
    """Indicadores por titular a partir de la matriz de entradas. `quitar`: ids
    que no cuentan (robustez sin las entradas más frecuentes)."""
    ids = lambda f: [e.id for e in lexico if f(e) and e.id not in quitar]  # noqa: E731
    alguna = lambda cols: E[cols].any(axis=1) if cols else pd.Series(False, index=E.index)  # noqa: E731
    out = pd.DataFrame(index=E.index)
    out["negativa"] = alguna(ids(lambda e: e.polaridad == "negativa" and e.tipo != "atribucion_neutra"))
    out["positiva"] = alguna(ids(lambda e: e.polaridad == "positiva" and e.tipo != "atribucion_neutra"))
    out["carga"] = alguna(ids(lambda e: e.tipo != "atribucion_neutra"))
    out["neto"] = out["negativa"].astype(int) - out["positiva"].astype(int)
    out["atrib_cargada"] = alguna(ids(lambda e: e.tipo == "atribucion_cargada"))
    out["atrib_neutra"] = alguna(ids(lambda e: e.tipo == "atribucion_neutra"))
    out["atrib_alguna"] = out["atrib_cargada"] | out["atrib_neutra"]
    return out


def menciona_gobierno(textos, gobiernos) -> np.ndarray:
    """El titular nombra al gobierno nacional o al presidente de ESE gobierno
    (`ref_ejecutivo` de `lexico.formas_nombrar`: «Gobierno Petro», «presidente
    Duque», «Gobierno nacional», «Gobierno» sin más, «mandatario», «Casa de
    Nariño»…). Simétrico: el apellido es siempre el del presidente del gobierno
    en que cae el titular."""
    return np.array([formas_nombrar(t, g)["ref_ejecutivo"] for t, g in zip(textos, gobiernos)], dtype=bool)


# ── comparación emparejada ───────────────────────────────────────────────────


def emparejado(meta: pd.DataFrame, M: pd.DataFrame, medio: str, excluir=(), reps=2000, seed=42, grupos=None,
               razones=None):
    """Proporción de titulares con cada columna de M: el medio frente a los otros
    medios en los mismos eventos (cada evento pesa uno por lado; los otros se
    promedian dentro del evento). Bootstrap por eventos o, con `grupos` (un
    entero por fila de `meta`… por evento, en el orden de `event_id`), por
    conglomerados. Devuelve (tabla, réplicas de la diferencia por columna)."""
    razones = razones or {}
    eventos, A, B = matrices_emparejadas(meta, M.to_numpy(dtype=float), medio, excluir)
    if not len(eventos):
        return pd.DataFrame(), {}
    A, B = A.toarray(), B.toarray()
    if grupos is None:
        g = np.arange(len(eventos))
    else:
        mes = meta.drop_duplicates("event_id").set_index("event_id")[grupos].loc[eventos].to_numpy()
        _, g = np.unique(mes, return_inverse=True)
    W = pesos_bootstrap(g, reps, np.random.default_rng(seed)).astype(np.float64)
    nb = W.sum(axis=1)
    ba, bb = (W @ A) / nb[:, None], (W @ B) / nb[:, None]
    pa, pb = A.mean(axis=0), B.mean(axis=0)
    cols = list(M.columns)
    filas, draws = [], {}
    for k, c in enumerate(cols):
        d = ba[:, k] - bb[:, k]
        with np.errstate(invalid="ignore", divide="ignore"):
            rel = np.where(bb[:, k] != 0, d / np.abs(bb[:, k]), np.nan)
        draws[c] = d
        filas.append(_fila(c, len(eventos), pa[k], pb[k], d, rel, reps))
    for nombre, (num, den) in razones.items():
        i, j = cols.index(num), cols.index(den)
        with np.errstate(invalid="ignore", divide="ignore"):
            d = ba[:, i] / ba[:, j] - bb[:, i] / bb[:, j]
            rel = d / (bb[:, i] / bb[:, j])
        pm = pa[i] / pa[j] if pa[j] else np.nan
        po = pb[i] / pb[j] if pb[j] else np.nan
        draws[nombre] = d
        f = _fila(nombre, len(eventos), pm, po, d, rel, reps)
        f.update({"n_ref_medio": A[:, j].sum(), "n_ref_otros": B[:, j].sum()})
        filas.append(f)
    return pd.DataFrame(filas), draws


def _fila(c, n, pm, po, d, rel, reps):
    d, rel = d[np.isfinite(d)], rel[np.isfinite(rel)]
    p = min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean()) + 1 / reps) if len(d) else np.nan
    return {"indicador": c, "eventos": n, "prop_medio": pm, "prop_otros": po, "diferencia": pm - po,
            "ic_bajo": np.quantile(d, 0.025) if len(d) else np.nan,
            "ic_alto": np.quantile(d, 0.975) if len(d) else np.nan,
            "dif_relativa": (pm - po) / abs(po) if po else np.nan,
            "rel_ic_bajo": np.quantile(rel, 0.025) if len(rel) else np.nan,
            "rel_ic_alto": np.quantile(rel, 0.975) if len(rel) else np.nan, "p": p}


def cambio_gobiernos(tab: pd.DataFrame, draws: dict, claves) -> pd.DataFrame:
    """Cambio Petro − Duque de la diferencia medio − otros. Los eventos de los dos
    gobiernos son disjuntos: las réplicas se restan como independientes."""
    filas = []
    for (m, ind) in claves:
        d_, p_ = draws.get((m, "duque", ind)), draws.get((m, "petro", ind))
        if d_ is None or p_ is None:
            continue
        rd = tab[(tab["medio"] == m) & (tab["gobierno"] == "duque") & (tab["indicador"] == ind)].iloc[0]
        rp = tab[(tab["medio"] == m) & (tab["gobierno"] == "petro") & (tab["indicador"] == ind)].iloc[0]
        k = min(len(d_), len(p_))
        dd = p_[:k] - d_[:k]
        dd = dd[np.isfinite(dd)]
        filas.append({"medio": m, "indicador": ind, "dif_duque": rd.diferencia, "dif_petro": rp.diferencia,
                      "cambio": rp.diferencia - rd.diferencia, "ic_bajo": np.quantile(dd, 0.025),
                      "ic_alto": np.quantile(dd, 0.975),
                      "p": min(1.0, 2 * min((dd <= 0).mean(), (dd >= 0).mean()) + 1 / len(dd)),
                      "dif_rel_duque": rd.dif_relativa, "dif_rel_petro": rp.dif_relativa,
                      "cambio_relativo": rp.dif_relativa - rd.dif_relativa,
                      "prop_medio_duque": rd.prop_medio, "prop_medio_petro": rp.prop_medio,
                      "prop_otros_duque": rd.prop_otros, "prop_otros_petro": rp.prop_otros})
    return pd.DataFrame(filas)


# ── datos ────────────────────────────────────────────────────────────────────


def preparar(out: Path, lexico: list[Entrada]):
    ev, _ = cargar(out)
    E = matriz_entradas(ev["texto"], lexico)
    E.index = ev.index
    I = indicadores(E, lexico)
    ev["gob"] = menciona_gobierno(ev["texto"], ev["gobierno"])
    ev["domestico"] = ~ev["topic"].isin(TEMAS_EXTERIOR)
    return ev, E, I


def frecuencias(ev, E, lexico) -> pd.DataFrame:
    core = ev[~ev["es_seguimiento"]]
    tot = E.loc[core.index].sum()
    filas = []
    for e in lexico:
        fila = {"id": e.id, "polaridad": e.polaridad, "tipo": e.tipo, "origen": e.origen,
                "titulares_nucleo": int(tot[e.id]), "pct_nucleo": 100 * tot[e.id] / len(core)}
        for g in GOVS:
            for m in MEDIA:
                sel = core[(core["gobierno"] == g) & (core["source_id"] == m)].index
                fila[f"pct_{m}_{g}"] = 100 * E.loc[sel, e.id].mean()
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("titulares_nucleo", ascending=False)


def top_entradas(freq: pd.DataFrame, n=10) -> list[str]:
    """Las n entradas con carga (no atribución neutra) más frecuentes en los titulares núcleo."""
    f = freq[freq["tipo"] != "atribucion_neutra"]
    return f.head(n)["id"].tolist()


# ── etapa validar: KWIC ──────────────────────────────────────────────────────


def kwic(ev, tab: pd.DataFrame, n_ej=8, seed=42) -> str:
    """Contextos de cada entrada del léxico (también las desactivadas, para
    documentar por qué se quitaron): formas más frecuentes, palabra de la
    izquierda y de la derecha, coincidencias anuladas por `excluir` y titulares al azar."""
    rng = np.random.default_rng(seed)
    core = ev[~ev["es_seguimiento"]]
    textos = core["texto"].tolist()
    filas = []
    for e in compilar(tab, solo_activas=False):
        crudas, finales, anuladas = [], [], 0
        for i, t in enumerate(textos):
            ms = list(e.patron.finditer(t))
            if not ms:
                continue
            ok = coincidencias(t, e)
            anuladas += len(ms) - len(ok)
            for m in ok:
                finales.append((i, m))
            crudas.append(i)
        filas.append((e, finales, anuladas, len(set(crudas))))
    filas.sort(key=lambda x: -len({i for i, _ in x[1]}))
    activa = dict(zip(tab["id"], tab["activa"]))
    nota = dict(zip(tab["id"], tab["nota"]))
    lines = ["# Validación del léxico de carga: contextos (KWIC)", "",
             f"Titulares núcleo de los eventos ({len(core):,} titulares). Por entrada: titulares con coincidencia,".replace(",", ".", 1),
             "formas más frecuentes, palabra a la izquierda y a la derecha, coincidencias anuladas por las",
             "exclusiones de contexto y ejemplos al azar (semilla " + str(seed) + "). Las entradas con `activa = no` se",
             "muestran sin sus exclusiones para documentar por qué se quitaron.", ""]
    resumen = ["| Entrada | Polaridad | Tipo | Activa | Titulares | Anuladas por contexto |", "|---|---|---|---|---:|---:|"]
    cuerpo = []
    for e, fin, anul, _ in filas:
        tits = sorted({i for i, _ in fin})
        resumen.append(f"| {e.id} | {e.polaridad} | {e.tipo} | {activa[e.id]} | {len(tits)} | {anul} |")
        if not tits:
            continue
        formas = Counter(m.group(0) for _, m in fin).most_common(6)
        izq, der = Counter(), Counter()
        for i, m in fin:
            t = textos[i]
            a = t[:m.start()].split()
            b = t[m.end():].split()
            izq[(a[-1] if a else "^") + " " + m.group(0)] += 1
            der[m.group(0) + " " + (b[0] if b else "$")] += 1
        cuerpo += [f"## {e.id} ({e.polaridad}, {e.tipo}; activa: {activa[e.id]}) — {len(tits)} titulares", ""]
        if nota[e.id]:
            cuerpo += [f"Nota: {nota[e.id]}", ""]
        cuerpo += ["- Formas: " + ", ".join(f"{f} ({k})" for f, k in formas),
                   "- Izquierda: " + ", ".join(f"«{f}» ({k})" for f, k in izq.most_common(8)),
                   "- Derecha: " + ", ".join(f"«{f}» ({k})" for f, k in der.most_common(8)),
                   f"- Anuladas por contexto: {anul}", ""]
        for i in rng.permutation(tits)[:n_ej]:
            t = textos[i]
            for m in sorted(coincidencias(t, e), key=lambda m: -m.start()):
                t = t[:m.start()] + "**" + m.group(0) + "**" + t[m.end():]
            cuerpo.append(f"  - {t}")
        cuerpo.append("")
    return "\n".join(lines + resumen + [""] + cuerpo)


# ── análisis ─────────────────────────────────────────────────────────────────

COLS = ["negativa", "positiva", "carga", "neto", "atrib_cargada", "atrib_neutra", "atrib_alguna"]
COLS_GOB = ["gob_negativa", "gob_positiva", "gob_carga", "gob_neto"]


def matriz_gob(ev: pd.DataFrame, I: pd.DataFrame) -> pd.DataFrame:
    """Carga dirigida al gobierno: el titular nombra al gobierno/presidente Y lleva carga."""
    g = ev["gob"].to_numpy()
    return pd.DataFrame({f"gob_{c}": I[c].to_numpy() * g for c in ["negativa", "positiva", "carga", "neto"]},
                        index=ev.index).astype(float)


def _celdas(ev, rcn_desde, variante, seguimiento=False):
    """(medio, gobierno, base, excluir) de cada celda en una variante."""
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(ev[ev["gobierno"] == g], m, g, rcn_desde)
            if not seguimiento:
                base = base[~base["es_seguimiento"]]
            excl = ()
            if variante == "sin_rcn":
                if m == RCN:
                    continue
                excl = (RCN,)
            if variante == "ventana_comun" and g == "duque":
                base = base[pd.to_datetime(base["fecha_inicio"]) >= rcn_desde]
            if variante == "longitud_similar":
                base = base[base["event_id"].isin(eventos_longitud_similar(base, m))]
            yield m, g, base, excl


def eventos_longitud_similar(base: pd.DataFrame, medio: str, tol: float = 2.0) -> np.ndarray:
    """Eventos en los que el titular del medio y el promedio de los otros difieren
    en ≤ `tol` palabras. Un titular más largo tiene más ocasiones de llevar una
    palabra del léxico (los slugs de El Tiempo en Duque son 2 palabras más cortos)."""
    lado = np.where(base["source_id"] == medio, "medio", "otros")
    n = base.assign(lado=lado).groupby(["event_id", "lado"])["n_palabras"].mean().unstack()
    n = n.dropna()
    return n.index[(n["medio"] - n["otros"]).abs() <= tol].to_numpy()


def analisis_general(ev, I, rcn_desde, args, variante="principal", I_alt=None):
    """Indicadores por medio × gobierno frente a los otros medios en los mismos eventos."""
    I = I if I_alt is None else I_alt
    filas, draws = [], {}
    seg = variante == "con_seguimiento"
    for m, g, base, excl in _celdas(ev, rcn_desde, variante, seguimiento=seg):
        t, d = emparejado(base, I.loc[base.index, COLS].astype(float), m, excl, args.reps, args.seed,
                          grupos="mes" if variante == "meses" else None, razones=RAZONES)
        t.insert(0, "gobierno", g)
        t.insert(0, "medio", m)
        filas.append(t)
        draws.update({(m, g, k): v for k, v in d.items()})
    tab = pd.concat(filas, ignore_index=True)
    tab.insert(0, "variante", variante)
    return tab, draws


def analisis_gobierno(ev, I, rcn_desde, args, variante="principal", I_alt=None):
    """Carga dirigida al gobierno, en eventos domésticos (sin tópicos de otros países).

    - `todos`: % de TODOS los titulares núcleo que nombran al gobierno y llevan
      carga (mezcla cuánto se nombra al gobierno con cómo).
    - `ambos_nombran`: sólo titulares que nombran al gobierno, en eventos donde
      el medio y al menos otro medio lo nombran. Ante el mismo hecho y la misma
      mención, ¿el medio añade carga? Es la medida principal."""
    I = I if I_alt is None else I_alt
    G = matriz_gob(ev, I)
    dom = ev[ev["domestico"]]
    seg = variante == "con_seguimiento"
    filas, draws = [], {}
    for m, g, base, excl in _celdas(dom, rcn_desde, variante, seguimiento=seg):
        # todos los titulares
        t, d = emparejado(base, G.loc[base.index], m, excl, args.reps, args.seed,
                          grupos="mes" if variante == "meses" else None)
        t.insert(0, "medida", "todos")
        sub = base[base["gob"]]
        cols = ["negativa", "positiva", "carga", "neto"]
        t2, d2 = emparejado(sub, I.loc[sub.index, cols].astype(float).add_prefix("gob_"), m, excl, args.reps,
                            args.seed, grupos="mes" if variante == "meses" else None)
        t2.insert(0, "medida", "ambos_nombran")
        for tt in (t, t2):
            tt.insert(0, "gobierno", g)
            tt.insert(0, "medio", m)
        filas += [t, t2]
        draws.update({(m, g, "todos:" + k): v for k, v in d.items()})
        draws.update({(m, g, "ambos_nombran:" + k): v for k, v in d2.items()})
    tab = pd.concat(filas, ignore_index=True)
    tab.insert(0, "variante", variante)
    return tab, draws


def analisis_entradas(ev, E, lexico, rcn_desde, args) -> pd.DataFrame:
    """Diferencia medio − otros (mismos eventos) de cada entrada del léxico: qué
    palabras empujan cada diferencia agregada."""
    tipo = {e.id: (e.polaridad, e.tipo) for e in lexico}
    filas = []
    for m, g, base, excl in _celdas(ev, rcn_desde, "principal"):
        t, _ = emparejado(base, E.loc[base.index].astype(float), m, reps=max(200, args.reps // 4), seed=args.seed)
        t = t.rename(columns={"indicador": "entrada"})
        t.insert(0, "gobierno", g)
        t.insert(0, "medio", m)
        t["polaridad"] = t["entrada"].map(lambda i: tipo[i][0])
        t["tipo"] = t["entrada"].map(lambda i: tipo[i][1])
        filas.append(t)
    return pd.concat(filas, ignore_index=True)


def analisis_tema(ev, I, rcn_desde, args):
    core = ev[~ev["es_seguimiento"]]
    filas = []
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(core[core["gobierno"] == g], m, g, rcn_desde)
            for topic, part in base.groupby("topic"):
                if topic in TEMAS_EXCLUIDOS_POR_TEMA:
                    continue
                n_ev = part.loc[part["source_id"] == m, "event_id"].nunique()
                if n_ev < args.min_eventos_tema:
                    continue
                t, _ = emparejado(part, I.loc[part.index, ["negativa", "positiva", "carga"]].astype(float), m,
                                  reps=args.reps // 2, seed=args.seed)
                if t.empty:
                    continue
                t.insert(0, "etiqueta_topic", part["etiqueta_topic"].iat[0])
                t.insert(0, "topic", int(topic))
                t.insert(0, "gobierno", g)
                t.insert(0, "medio", m)
                filas.append(t)
    tab = pd.concat(filas, ignore_index=True)
    tab["q_bh"] = np.nan
    for ind, idx in tab.groupby("indicador").groups.items():
        tab.loc[idx, "q_bh"] = bh_adjust(tab.loc[idx, "p"].to_numpy())
    return tab


def niveles_gobierno(ev, I, rcn_desde) -> pd.DataFrame:
    """Nivel (no emparejado) de carga en los titulares núcleo de eventos domésticos
    que nombran al gobierno, los cinco medios juntos, por gobierno; IC de Wilson.
    Sirve para ver el cambio COMÚN a todos los medios (agenda, periodo), que el
    diseño emparejado no atribuye a ningún medio. Duque: completo y ventana común."""
    core = ev[~ev["es_seguimiento"] & ev["domestico"] & ev["gob"]]
    filas = []
    for g, ventana in (("duque", "completa"), ("duque", "comun"), ("petro", "completa")):
        sub = core[core["gobierno"] == g]
        if ventana == "comun":
            sub = sub[pd.to_datetime(sub["fecha_inicio"]) >= rcn_desde]
        for c in ["negativa", "positiva", "carga"]:
            k, n = int(I.loc[sub.index, c].sum()), len(sub)
            lo, hi = wilson_interval(k, n)
            filas.append({"gobierno": g, "ventana_duque": ventana, "indicador": c, "titulares_gobierno": n,
                          "con_carga": k, "prop": k / n, "ic_bajo": lo, "ic_alto": hi})
    return pd.DataFrame(filas)


# ── ejemplos ─────────────────────────────────────────────────────────────────


def _marcas(texto, lexico, tipos_excl=("atribucion_neutra",)):
    out = []
    for e in lexico:
        if e.tipo in tipos_excl:
            continue
        for m in coincidencias(texto, e):
            signo = {"negativa": "−", "positiva": "+", "neutra": "±"}[e.polaridad]
            out.append(f"{m.group(0)} ({signo})")
    return ", ".join(dict.fromkeys(out))


def _tabla(ev, k, lexico, resaltar):
    part = ev[(ev["event_id"] == k) & ~ev["es_seguimiento"]].sort_values("source_id", key=lambda s: s.map(MEDIA.index))
    r0 = part.iloc[0]
    lines = [f"**Evento {k}** · {r0['fecha_inicio']} · {r0['n_medios']} medios · {r0['etiqueta_topic']}", "",
             "| Medio | Titular | Carga |", "|---|---|---|"]
    for r in part.itertuples():
        nombre = MEDIA_NAMES[r.source_id]
        nombre = f"**{nombre}**" if r.source_id == resaltar else nombre
        lines.append(f"| {nombre} | {r.title} | {_marcas(r.texto, lexico) or '—'} |")
    return lines + [""]


def ejemplos_md(ev, I, lexico, rcn_desde, seed, n=2) -> str:
    """Eventos donde el medio usa carga y NINGÚN otro medio la usa (dirigida al
    gobierno: el medio nombra al gobierno con carga y otro medio lo nombra sin ella)."""
    rng = np.random.default_rng(seed)
    core = ev[~ev["es_seguimiento"]]
    lines = ["# Ejemplos de lenguaje cargado dentro del mismo hecho", "",
             "Titulares reconstruidos desde la URL (sin tildes, cifras ni puntuación). Cada tabla es un evento con los",
             "titulares núcleo de cada medio; en negrita, el medio que usa la carga. La columna «Carga» lista las",
             "palabras del léxico detectadas: (−) negativa, (+) positiva, (±) intensificador o sensacionalismo sin",
             "polaridad. El emparejamiento acierta el mismo hecho en el 81 % de los casos (IC 95 % 72–90 %).",
             f"Ejemplos elegidos al azar entre los candidatos (semilla {seed}), prefiriendo eventos con más medios.",
             "Son ilustraciones, no evidencia: las cifras están en LEEME.md.", ""]
    secciones = [
        ("1. Carga dirigida al gobierno: el medio nombra al gobierno con carga negativa y otro medio lo nombra sin ella",
         "negativa", True),
        ("2. Carga dirigida al gobierno con polaridad positiva", "positiva", True),
        ("3. Carga negativa en general: sólo el medio la usa", "negativa", False),
    ]
    for titulo, ind, gob in secciones:
        lines += [f"## {titulo}", ""]
        for g in GOVS:
            lines += [f"### Gobierno {GOV_NAMES[g]}", ""]
            for m in MEDIA:
                base = recorte_rcn(core[core["gobierno"] == g], m, g, rcn_desde)
                if gob:
                    base = base[base["domestico"]]
                own = base[(base["source_id"] == m) & I.loc[base.index, ind] & (base["gob"] if gob else True)]
                cand = []
                for k in own["event_id"].unique():
                    otros = base[(base["event_id"] == k) & (base["source_id"] != m)]
                    if gob:
                        otros = otros[otros["gob"]]
                    if len(otros) and not I.loc[otros.index, ind].any():
                        cand.append((-otros["source_id"].nunique(), rng.random(), k))
                if not cand:
                    continue
                lines += [f"#### {MEDIA_NAMES[m]} (eventos candidatos: {len(cand)})", ""]
                for _, _, k in sorted(cand)[:n]:
                    lines += _tabla(ev, k, lexico, m)
    return "\n".join(lines)


# ── figuras 30 a 32 ──────────────────────────────────────────────────────────


def _pp(v, _=None, dec=1):
    if abs(v) < 1e-9:
        return "0 pp"
    return f"{v:+.{dec}f} pp".replace(".", ",").replace("-", "−")


def _dots(ax, tab, ind, ylabel=True, robusto=None):
    x = np.arange(len(MEDIA))
    for k, g in enumerate(GOVS):
        t = tab[(tab["indicador"] == ind) & (tab["gobierno"] == g)].set_index("medio").reindex(MEDIA)
        xx = x + (k - 0.5) * 0.3
        ax.errorbar(xx, 100 * t["diferencia"], yerr=[100 * (t["diferencia"] - t["ic_bajo"]),
                                                     100 * (t["ic_alto"] - t["diferencia"])],
                    fmt="o", color=GOV_COLORS[g], ms=7, mec=SURFACE, mew=1.5, elinewidth=1.4, capsize=0)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x, [SHORT[m] for m in MEDIA], fontsize=8.5)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_pp))
    ax.grid(axis="x", visible=False)


def fig_general(tab, rcn_desde, res):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    for ax, ind, tit in zip(axes, ["negativa", "positiva", "carga"],
                            ["Carga negativa", "Carga positiva", "Cualquier carga (incl. intensificadores)"]):
        _dots(ax, tab, ind)
        ax.set_title(tit, fontsize=10)
    axes[0].set_ylabel("medio − otros medios, mismos eventos")
    handles = [Line2D([], [], marker="o", ls="", color=GOV_COLORS[g], ms=8, label=f"Gobierno {GOV_NAMES[g]}")
               for g in GOVS]
    fig.tight_layout(w_pad=2.5)
    _margins(fig, handles, ncol=2, top_in=0.9, bottom_in=0.6)
    _save(fig, res, "30_carga_medio_gobierno.png", "¿Qué medio añade más lenguaje cargado al mismo hecho?",
          "Diferencia, en puntos porcentuales, entre el % de titulares núcleo del medio con alguna palabra del léxico "
          "curado (lexico_carga.csv) y el % de los otros medios en los mismos eventos (los otros se promedian dentro "
          "del evento). IC 95 % por bootstrap de eventos. Sobre 0, el medio usa más carga que los demás al contar "
          f"el mismo hecho. No es sentimiento ni sesgo por sí solo. RCN en Duque sólo desde {rcn_desde:%Y-%m}. "
          f"{NOTA_UMBRAL} {FUENTE}")


def fig_gobierno(gob, niveles, rcn_desde, res):
    t = gob[gob["medida"] == "ambos_nombran"]
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.8), gridspec_kw={"width_ratios": [0.7, 1, 1, 1]})
    ax = axes[0]
    for k, (g, v, filled) in enumerate((("duque", "completa", True), ("duque", "comun", False),
                                        ("petro", "completa", True))):
        n = niveles[(niveles["gobierno"] == g) & (niveles["ventana_duque"] == v)].set_index("indicador")
        n = n.loc[["negativa", "positiva"]]
        xx = np.arange(2) + (k - 1) * 0.22
        ax.errorbar(xx, 100 * n["prop"], yerr=[100 * (n["prop"] - n["ic_bajo"]), 100 * (n["ic_alto"] - n["prop"])],
                    fmt="o", color=GOV_COLORS[g], mfc=GOV_COLORS[g] if filled else SURFACE, mec=GOV_COLORS[g],
                    ms=7, mew=1.5, elinewidth=1.4)
    ax.set_xticks(range(2), ["negativa", "positiva"])
    ax.set_xlim(-0.5, 1.5)
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f} %"))
    ax.set_title("Nivel, los cinco medios juntos", fontsize=10)
    ax.set_ylabel("% de titulares que nombran al gobierno")
    ax.grid(axis="x", visible=False)
    for ax, ind, tit in zip(axes[1:], ["gob_negativa", "gob_positiva", "gob_neto"],
                            ["Carga negativa", "Carga positiva", "Neto (negativa − positiva)"]):
        _dots(ax, t, ind)
        ax.set_title(tit + ": medio − otros", fontsize=10)
    axes[1].set_ylabel("medio − otros medios, mismos eventos")
    handles = [Line2D([], [], marker="o", ls="", color=GOV_COLORS[g], ms=8, label=f"Gobierno {GOV_NAMES[g]}")
               for g in GOVS]
    handles.append(Line2D([], [], marker="o", ls="", mfc=SURFACE, mec=GOV_COLORS["duque"], ms=8,
                          label=f"Duque desde {rcn_desde:%Y-%m} (ventana común)"))
    fig.tight_layout(w_pad=2.5)
    _margins(fig, handles, ncol=3, top_in=0.9, bottom_in=0.6)
    _save(fig, res, "31_carga_dirigida_gobierno.png", "Carga en los titulares que nombran al gobierno",
          "Izquierda: % de los titulares núcleo de eventos domésticos que nombran al gobierno con alguna palabra "
          "negativa o positiva, los cinco medios juntos (IC 95 % de Wilson); el cambio es común a todos los medios y "
          "puede ser de agenda. Resto: sólo titulares núcleo que nombran al gobierno nacional o al presidente de ese gobierno («Gobierno "
          "Petro/Duque», «presidente», «Gobierno nacional», «Gobierno»…), en eventos domésticos donde el medio y al "
          "menos otro medio lo nombran. Diferencia entre el % del medio con carga y el de los otros medios en el "
          "mismo evento; IC 95 % por bootstrap de eventos. La carga puede referirse al gobierno o al hecho: es una "
          f"cota de cómo se cuenta, no de una postura. RCN en Duque sólo desde {rcn_desde:%Y-%m}. {NOTA_UMBRAL} {FUENTE}")


VARIANTES = {"principal": "principal", "meses": "bootstrap por meses", "con_seguimiento": "con seguimiento",
             "sin_rcn": "sin RCN entre los otros", "ventana_comun": "ventana común (Duque desde 2020-09)",
             "longitud_similar": "titulares de largo similar (±2 palabras)",
             "sin_top10": "sin las 10 entradas más frecuentes"}
MARCAS_VAR = {"principal": "o", "meses": "s", "con_seguimiento": "^", "sin_rcn": "D", "ventana_comun": "v",
              "longitud_similar": "X", "sin_top10": "P"}


def fig_robustez(rob, res):
    paneles = [("general", "negativa", "Carga negativa (todos los titulares)"),
               ("gobierno", "gob_negativa", "Carga negativa al nombrar al gobierno"),
               ("gobierno", "gob_positiva", "Carga positiva al nombrar al gobierno")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 7.2), sharey=True)
    vars_ = list(VARIANTES)
    filas = [(m, g) for m in MEDIA for g in GOVS]
    for ax, (fuente, ind, tit) in zip(axes, paneles):
        t = rob[(rob["analisis"] == fuente) & (rob["indicador"] == ind)]
        for i, (m, g) in enumerate(filas):
            for j, v in enumerate(vars_):
                r = t[(t["medio"] == m) & (t["gobierno"] == g) & (t["variante"] == v)]
                if r.empty:
                    continue
                r = r.iloc[0]
                y = i + (j - (len(vars_) - 1) / 2) * 0.12
                ax.plot([100 * r.ic_bajo, 100 * r.ic_alto], [y, y], color=GOV_COLORS[g], lw=1, alpha=0.7)
                ax.plot(100 * r.diferencia, y, marker=MARCAS_VAR[v], color=GOV_COLORS[g], ms=5,
                        mfc=GOV_COLORS[g] if v == "principal" else SURFACE, mec=GOV_COLORS[g], ls="")
        ax.axvline(0, color=INK2, lw=0.8)
        for i in range(1, len(MEDIA)):
            ax.axhline(2 * i - 0.5, color=AXIS, lw=0.6)
        ax.set_title(tit, fontsize=10)
        ax.xaxis.set_major_locator(MaxNLocator(7, integer=True))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _pp(v, dec=0)))
        ax.set_xlabel("medio − otros medios, mismos eventos")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(range(len(filas)), [f"{SHORT[m]} · {GOV_NAMES[g]}" for m, g in filas], fontsize=8.5)
    axes[0].set_ylim(len(filas) - 0.5, -0.5)
    handles = [Line2D([], [], marker=MARCAS_VAR[v], ls="", color=INK2, mfc=INK2 if v == "principal" else SURFACE,
                      ms=7, label=VARIANTES[v]) for v in vars_]
    fig.tight_layout(w_pad=2)
    _margins(fig, handles, ncol=3, top_in=1.15, bottom_in=0.8)
    _save(fig, res, "32_robustez_carga.png", "Robustez: ¿las diferencias dependen de una elección?",
          "Diferencia medio − otros medios en los mismos eventos con IC 95 % en cada variante. Color: gobierno "
          "(violeta Duque, verde Petro). Bootstrap por meses = se remuestrean los meses de inicio de los eventos. "
          "Largo similar = sólo eventos donde el titular del medio y el promedio de los otros difieren en ≤2 palabras. "
          "Sin las 10 entradas más frecuentes = se recalculan los indicadores sin esas entradas del léxico. "
          f"Paneles 2 y 3: titulares que nombran al gobierno, en eventos domésticos donde el medio y otro lo nombran. "
          f"{NOTA_UMBRAL} {FUENTE}")


# ── etapa principal ──────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=HERE / "resultados_publico")
    parser.add_argument("--etapa", choices=["validar", "analizar"], default="analizar")
    parser.add_argument("--lexico", type=Path, default=LEXICO)
    parser.add_argument("--reps", type=int, default=2000, help="Réplicas del bootstrap")
    parser.add_argument("--min-eventos-tema", type=int, default=150,
                        help="Eventos mínimos del medio en un tema para el análisis por tema")
    parser.add_argument("--rcn-min-dia", type=float, default=0.75,
                        help="% mínimo de titulares de RCN con fecha al día, sostenido (como lexico.py)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = args.output.resolve()
    res = out / "carga"
    (res / "figuras").mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    tab_lex = leer_lexico(args.lexico)
    lexico = compilar(tab_lex)

    if args.etapa == "validar":
        ev, _ = cargar(out)
        (res / "validacion_lexico.md").write_text(kwic(ev, tab_lex, seed=args.seed), encoding="utf-8")
        logging.info("KWIC listo (%.0f s)", time.monotonic() - t0)
        return

    _, rcn_desde = precision_fecha_rcn(out, args.rcn_min_dia)
    ev, E, I = preparar(out, lexico)
    logging.info("%s titulares; léxico con %s entradas activas (%.0f s)", len(ev), len(lexico), time.monotonic() - t0)
    (res / "validacion_lexico.md").write_text(kwic(ev, tab_lex, seed=args.seed), encoding="utf-8")
    freq = frecuencias(ev, E, lexico)
    freq.to_csv(res / "frecuencias_lexico.csv", index=False)
    top10 = top_entradas(freq, 10)
    I_sin = indicadores(E, lexico, quitar=top10)

    gen, gen_rob, gob, gob_rob = [], [], [], []
    draws_gen, draws_gob = {}, {}
    for v in VARIANTES:
        I_alt = I_sin if v == "sin_top10" else None
        base = "principal" if v in ("meses", "sin_top10") else v
        t, d = analisis_general(ev, I, rcn_desde, args, variante=base if v != "meses" else "meses", I_alt=I_alt)
        t["variante"] = v
        t2, d2 = analisis_gobierno(ev, I, rcn_desde, args, variante=base if v != "meses" else "meses", I_alt=I_alt)
        t2["variante"] = v
        gen.append(t)
        gob.append(t2)
        if v == "principal":
            draws_gen, draws_gob = d, d2
        logging.info("variante %s (%.0f s)", v, time.monotonic() - t0)
    gen, gob = pd.concat(gen, ignore_index=True), pd.concat(gob, ignore_index=True)
    gen.to_csv(res / "carga_medio_gobierno.csv", index=False)
    gob.to_csv(res / "carga_gobierno.csv", index=False)

    gen_p, gob_p = gen[gen["variante"] == "principal"], gob[gob["variante"] == "principal"]
    cambio = cambio_gobiernos(gen_p, draws_gen, [(m, c) for m in MEDIA for c in [*COLS, *RAZONES]])
    cambio.insert(0, "analisis", "general")
    gob_p_k = gob_p.assign(indicador=gob_p["medida"] + ":" + gob_p["indicador"])
    cambio_g = cambio_gobiernos(gob_p_k, draws_gob,
                                [(m, f"{me}:{c}") for m in MEDIA for me in ("todos", "ambos_nombran") for c in COLS_GOB])
    cambio_g.insert(0, "analisis", "gobierno")
    cambio = pd.concat([cambio, cambio_g], ignore_index=True)
    cambio.to_csv(res / "carga_cambio_duque_petro.csv", index=False)

    # robustez en formato largo (para la figura 32 y el resumen)
    rob = pd.concat([gen.assign(analisis="general"),
                     gob[gob["medida"] == "ambos_nombran"].assign(analisis="gobierno")], ignore_index=True)
    principal = rob[rob["variante"] == "principal"].set_index(["analisis", "medio", "gobierno", "indicador"])
    rob["signo_igual_principal"] = [np.sign(r.diferencia) == np.sign(principal.loc[(r.analisis, r.medio, r.gobierno,
                                                                                    r.indicador), "diferencia"])
                                    if (r.analisis, r.medio, r.gobierno, r.indicador) in principal.index else np.nan
                                    for r in rob.itertuples()]
    rob["ic_excluye_0"] = (rob["ic_bajo"] > 0) | (rob["ic_alto"] < 0)
    rob_res = rob[["analisis", "variante", "medio", "gobierno", "indicador", "eventos", "prop_medio", "prop_otros",
                   "diferencia", "ic_bajo", "ic_alto", "ic_excluye_0", "signo_igual_principal"]]
    rob_res.to_csv(res / "robustez_carga.csv", index=False)

    analisis_entradas(ev, E, lexico, rcn_desde, args).to_csv(res / "carga_por_entrada.csv", index=False)
    tema = analisis_tema(ev, I, rcn_desde, args)
    tema.to_csv(res / "carga_tema.csv", index=False)

    (res / "ejemplos_carga.md").write_text(ejemplos_md(ev, I, lexico, rcn_desde, args.seed), encoding="utf-8")

    fig_general(gen_p, rcn_desde, res)
    fig_robustez(rob, res)

    def celda(t, m, g, ind):
        r = t[(t["medio"] == m) & (t["gobierno"] == g) & (t["indicador"] == ind)]
        if r.empty:
            return None
        r = r.iloc[0]
        return {"medio": _r(r.prop_medio), "otros": _r(r.prop_otros), "diferencia": _r(r.diferencia),
                "ic95": [_r(r.ic_bajo), _r(r.ic_alto)], "dif_relativa": _r(r.dif_relativa), "eventos": int(r.eventos)}

    gob_amb = gob_p[gob_p["medida"] == "ambos_nombran"]
    core = ev[~ev["es_seguimiento"]]
    niveles_gob = niveles_gobierno(ev, I, rcn_desde)
    niveles_gob.to_csv(res / "niveles_gobierno.csv", index=False)
    fig_gobierno(gob_p, niveles_gob, rcn_desde, res)
    save_json(res / "carga.json", {
        "parametros": {"reps": args.reps, "seed": args.seed, "min_eventos_tema": args.min_eventos_tema,
                       "rcn_desde": rcn_desde.strftime("%Y-%m"), "entradas_activas": len(lexico),
                       "entradas_desactivadas": int((tab_lex["activa"] == "no").sum()),
                       "entradas_tras_datos": int((tab_lex["origen"] == "tras_datos").sum()),
                       "top10_quitadas_en_robustez": top10,
                       "temas_exterior_excluidos_en_gobierno": sorted(TEMAS_EXTERIOR)},
        "niveles_nucleo": {g: {m: {c: _r(I.loc[core[(core["gobierno"] == g) & (core["source_id"] == m)].index, c]
                                     .astype(float).mean()) for c in ["negativa", "positiva", "carga"]}
                               for m in MEDIA} for g in GOVS},
        "general": {m: {g: {c: celda(gen_p, m, g, c) for c in ["negativa", "positiva", "carga", "neto",
                                                               "cargada_entre_atribucion"]} for g in GOVS}
                    for m in MEDIA},
        "gobierno_ambos_nombran": {m: {g: {c: celda(gob_amb, m, g, c) for c in COLS_GOB} for g in GOVS}
                                   for m in MEDIA},
        "niveles_gobierno_todos_los_medios": niveles_gob.round(4).to_dict(orient="records"),
        "cambio_duque_petro": cambio.round(4).to_dict(orient="records"),
        "temas_ic_excluye_0_q05": tema[(tema["q_bh"] < 0.05)][["medio", "gobierno", "topic", "etiqueta_topic",
                                                               "indicador", "diferencia", "ic_bajo", "ic_alto",
                                                               "q_bh"]].round(4).to_dict(orient="records"),
        "segundos": round(time.monotonic() - t0),
    })
    logging.info("Listo en %.0f s → %s", time.monotonic() - t0, res)


if __name__ == "__main__":
    main()
