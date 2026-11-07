"""Elección léxica dentro del mismo hecho: palabras distintivas y formas de nombrar al gobierno.

Sobre los eventos de `eventos.py` (titulares de medios distintos sobre el mismo
hecho, umbral calibrado 0,80). Al fijar el hecho, la diferencia de palabras entre
un medio y los demás ya no se explica por la agenda (de qué se habla) sino por
cómo se cuenta.

    1. Palabras distintivas: log-odds con prior de Dirichlet informativo (Monroe,
       Colaresi y Quinn 2008) del medio frente a los OTROS medios en los MISMOS
       eventos. Cada evento pesa lo mismo en los dos lados (los titulares de los
       otros medios se promedian dentro del evento). Inferencia con bootstrap por
       eventos y, como robustez, por meses (bloques de eventos del mismo mes).
    2. Formas de nombrar al gobierno y al presidente, simétricas Duque / Petro:
       proporción por medio × gobierno con IC de Wilson, y diferencia frente a los
       otros medios en los mismos eventos con bootstrap por eventos.
    3. Ejemplos cualitativos (ejemplos_lexico.md).

Noticias RCN sólo tiene fecha al día de forma sostenida desde un mes que se mide
aquí (`--rcn-min-dia`); sus eventos de Duque anteriores se descartan porque son
una submuestra seleccionada por el formato de la URL. Ver LEEME.md.

Uso: SCRIPT=lexico.py ./run.sh - --output resultados_publico
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, PercentFormatter
from scipy import sparse
from scipy.stats import norm, spearmanr

import figuras
from core import normalize, tokenize
from figuras import (AXIS, FUENTE, GOV_COLORS, GOV_NAMES, GRID, INK, INK2, MEDIA_COLORS, MEDIA_NAMES, MUTED,
                     NOTA_UMBRAL, SHORT, SURFACE, _margins, _save, miles)
from research_stats import holm_adjust, wilson_interval
from topics import GOVS, MEDIA, load_json, save_json, stop_words

HERE = Path(__file__).resolve().parent
RCN = "noticias_rcn"
# Tópicos de BERTopic sobre otros países: ahí «gobierno» suele ser un gobierno
# extranjero, así que las formas de nombrar se miden en los eventos domésticos.
TEMAS_EXTERIOR = {2, 5, 13, 16}
# T8 es una mezcla sin tema (no se cita) y T14 es fútbol residual.
TEMAS_EXCLUIDOS_POR_TEMA = {8, 14}

# Marcadores de formato que stopwords_dominio.txt quita; aquí se dejan para poder
# marcarlos como formato en vez de esconderlos.
FORMATO_DOMINIO = {"video", "videos", "vivo", "asi", "columna", "webstory", "noticias", "conozca", "detalles", "ver"}
# Palabras de formato, género o registro: dicen cómo se presenta la nota, no
# cómo se encuadra el hecho. Se marcan, no se quitan.
FORMATO = FORMATO_DOMINIO | {
    "envivo", "minuto", "ultima", "hora", "urgente", "atencion", "exclusiva", "exclusivo", "entrevista",
    "opinion", "editorial", "podcast", "fotos", "foto", "imagenes", "momento", "momentos", "impactante",
    "impactantes", "claves", "clave", "vea", "mire", "sepa", "explicamos", "radiografia", "analisis",
    "reaccion", "reacciones", "audio", "galeria",
    # autorreferencias, programas y secciones fijas («Mañanas Blu programa…», «reviva aquí los goles»)
    "blu", "rcn", "caracol", "mananas", "programa", "reviva", "aqui", "aca", "envivo", "cotizacion", "cotiza",
    "divisa", "trm", "oficial", "dato", "datos",
    # artefactos del slug: «por ciento» (la cifra se pierde) y etiquetas de sección («elecciones usa»,
    # «eliminatoria mundial»)
    "ciento", "usa", "eliminatoria", "eliminatorias",
}
# Un término que en al menos esta fracción de sus usos por el medio va junto a
# una palabra de formato se marca también como formato (firmas de columnas:
# «… opinión de Ricardo Ospina»; programas: «… Mañanas Blu programa de…»).
UMBRAL_CONTAGIO_FORMATO = 0.5
CONTAGIO = {"opinion", "columna", "editorial", "programa", "mananas", "reviva", "podcast", "envivo", "webstory"}
# Verbos de atribución: cómo se introduce lo que dice una fuente. Son un recurso
# de encuadre conocido, pero también un hábito de redacción; se marcan aparte.
ATRIBUCION = {
    "asegura", "aseguro", "aseguran", "afirma", "afirmo", "advierte", "advirtio", "advierten", "denuncia",
    "denuncio", "denuncian", "reacciona", "reacciono", "respondio", "contesta", "contesto", "explica", "explico",
    "senala", "senalo", "insiste", "insistio", "critica", "critico", "cuestiona", "cuestiono", "arremete",
    "arremetio", "califica", "califico", "sostiene", "reconoce", "reconocio", "alerta", "alerto", "admite",
    "admitio", "defiende", "defendio", "rechaza", "rechazo", "manifesto", "expreso", "declaro", "indico",
    "aclara", "aclaro", "confirma", "confirmo", "agrega", "anade", "lanza", "lanzo",
}
APELLIDO = {"duque": "duque", "petro": "petro"}
NOMBRE_PILA = {"duque": "ivan", "petro": "gustavo"}
# Palabras tras «gobierno» que indican OTRO gobierno (extranjero, local, anterior)
# o que ya cuentan como otra forma.
NO_GENERICO = {
    "de", "del", "nacional", "colombiano", "distrital", "departamental", "local", "locales", "municipal", "regional",
    "estadounidense", "venezolano", "ecuatoriano", "peruano", "chino", "ruso", "israeli", "espanol", "britanico",
    "frances", "aleman", "argentino", "brasileno", "mexicano", "chileno", "cubano", "nicaraguense", "ucraniano",
    "irani", "taliban", "interino", "militar", "corporativo", "escolar", "abierto", "digital", "japones",
    "italiano", "canadiense", "panameno", "boliviano", "haitiano", "hondureno", "salvadoreno", "guatemalteco",
    "dominicano", "turco", "sirio", "palestino", "coreano", "paraguayo", "uruguayo", "costarricense", "chavista",
    "federal", "estatal", "entrante", "saliente", "anterior", "pasado", "electo", "trump", "biden", "maduro",
    "milei", "bukele", "boric", "lula", "noboa", "obama", "putin", "sanchez", "netanyahu", "zelenski", "bolsonaro",
    "ortega", "uribe", "santos", "petro", "duque", "gustavo", "ivan", "sheinbaum", "arce", "castillo", "boluarte",
    "lasso", "fernandez", "macri", "guaido", "delcy", "abelardo", "galan", "lopez", "claudia", "penalosa",
}
FORMAS = ["gobierno_apellido", "presidente_apellido", "nombre_completo", "apellido_solo", "menciona_apellido",
          "gobierno_nacional", "gobierno_generico", "mandatario", "ejecutivo", "casa_narino", "presidencia",
          "ministro", "ref_gobierno", "ref_ejecutivo", "personal_amplio"]
FORMAS_NOMBRE = {
    "gobierno_apellido": "«Gobierno Petro/Duque»", "presidente_apellido": "«presidente Petro/Duque»",
    "nombre_completo": "«Gustavo Petro»/«Iván Duque»", "apellido_solo": "«Petro»/«Duque» solo",
    "menciona_apellido": "menciona el apellido", "gobierno_nacional": "«Gobierno nacional»",
    "gobierno_generico": "«Gobierno» sin más", "mandatario": "«mandatario»/«jefe de Estado»",
    "ejecutivo": "«Ejecutivo»", "casa_narino": "«Casa de Nariño»", "presidencia": "«Presidencia de la República»",
    "ministro": "ministro(a)", "ref_gobierno": "alguna forma de «gobierno»", "ref_ejecutivo": "alguna referencia al Ejecutivo",
    "personal_amplio": "nombra al presidente",
}
# Índices de personalización: numerador entre denominador, por titular.
INDICES = {
    "pers_gobierno": ("gobierno_apellido", "ref_gobierno",
                      "«Gobierno Petro/Duque» entre los titulares que dicen «gobierno» (nacional)"),
    "pers_ejecutivo": ("personal_amplio", "ref_ejecutivo",
                       "nombra al presidente entre los que se refieren al Ejecutivo"),
}
MARCAS_FORMATO = {
    "pregunta": r"^(?:que|como|cuanto|cuanta|cuantos|cuantas|cuando|donde|quien|quienes|cual|cuales|por que|para que)\b",
    "que_se_sabe": r"\b(?:que|lo que) se sabe\b",
    "video": r"\bvideos?\b",
    "en_vivo": r"\ben vivo\b|\bminuto a minuto\b",
    "asi": r"^asi\b|\basi (?:fue|es|se|quedo|va|luce|serian?|reacciono|respondio)\b",
    "claves": r"\bclaves\b|\blo que (?:debe|tiene que) saber\b",
    "ultima_hora": r"\bultima hora\b|\burgente\b|\batencion\b",
    "opinion": r"\bopinion\b|\bcolumna\b|\beditorial\b",
}


# ── texto ────────────────────────────────────────────────────────────────────


def stop_lexico() -> set[str]:
    """Stopwords de NLTK + dominio (como topics.py), sin quitar los marcadores de
    formato: se dejan para marcarlos."""
    return stop_words() - FORMATO_DOMINIO


def terminos(titulo: str, stop: set[str]) -> set[str]:
    """Unigramas y bigramas (sobre la secuencia ya sin stopwords) presentes en el titular."""
    toks = tokenize(titulo, stop)
    return set(toks) | {f"{a} {b}" for a, b in zip(toks, toks[1:])}


def clase_termino(termino: str) -> str:
    partes = termino.split()
    if termino in FORMATO or any(p in FORMATO for p in partes):
        return "formato"
    if termino in ATRIBUCION or any(p in ATRIBUCION for p in partes):
        return "atribucion"
    return "contenido"


def formas_nombrar(texto: str, gobierno: str) -> dict[str, bool]:
    """Formas de nombrar al gobierno y al presidente en un titular normalizado
    (`core.normalize`), con el apellido del presidente de ESE gobierno. Las formas
    no son excluyentes, salvo `apellido_solo` (el apellido sin «gobierno»,
    «presidente» ni nombre de pila delante)."""
    ap, pila = APELLIDO[gobierno], NOMBRE_PILA[gobierno]
    pat = {
        "gobierno_apellido": rf"\bgobierno (?:de |del presidente )?(?:{pila} )?{ap}\b",
        "presidente_apellido": rf"\bpresident[ea] (?:de colombia )?(?:{pila} )?{ap}\b",
        "nombre_completo": rf"\b{pila} {ap}\b",
    }
    f = {k: bool(re.search(p, texto)) for k, p in pat.items()}
    resto = texto
    for p in pat.values():
        resto = re.sub(p, " ", resto)
    f["apellido_solo"] = bool(re.search(rf"\b{ap}\b", resto))
    f["menciona_apellido"] = bool(re.search(rf"\b{ap}\b", texto))
    f["gobierno_nacional"] = bool(re.search(r"\bgobierno (?:nacional|colombiano|de colombia)\b", texto))
    sig = re.findall(r"\bgobierno\b(?: (\w+))?", texto)
    f["gobierno_generico"] = any(s not in NO_GENERICO for s in sig)
    f["mandatario"] = bool(re.search(r"\bmandatari[oa]\b(?! (?:de|del|venezolano|estadounidense|ecuatoriano))"
                                     r"|\bjefe de estado\b", texto))
    f["ejecutivo"] = bool(re.search(r"(?<!presidente )(?<!director )(?<!directora )(?<!presidenta )"
                                    r"\bejecutivo\b(?! de)", texto))
    f["casa_narino"] = bool(re.search(r"\b(?:casa|palacio) de narino\b", texto))
    f["presidencia"] = bool(re.search(r"\bpresidencia de la republica\b", texto))
    f["ministro"] = bool(re.search(
        r"\bminist(?:ro|ra|ros|ras)\b|\bmin(?:hacienda|salud|defensa|trabajo|interior|minas|energia|educacion|"
        r"ambiente|justicia|transporte|agricultura|vivienda|comercio|cultura|igualdad|tic)\b", texto))
    f["ref_gobierno"] = f["gobierno_apellido"] or f["gobierno_nacional"] or f["gobierno_generico"]
    f["personal_amplio"] = (f["gobierno_apellido"] or f["presidente_apellido"] or f["nombre_completo"]
                            or f["apellido_solo"])
    f["ref_ejecutivo"] = (f["personal_amplio"] or f["ref_gobierno"] or f["mandatario"] or f["ejecutivo"]
                          or f["casa_narino"] or f["presidencia"])
    return f


# ── diseño emparejado ────────────────────────────────────────────────────────


def matrices_emparejadas(meta: pd.DataFrame, X, medio: str, excluir=()):
    """Para los eventos con `medio` y al menos un titular de otro medio (sin
    `excluir`): A[e] = media de las filas de X del medio en el evento e y
    B[e] = media de las filas de los otros medios. Así cada evento pesa uno en
    cada lado, tenga 2 o 5 medios. Devuelve (event_ids, A, B), A y B dispersas."""
    src = meta["source_id"].to_numpy()
    evs = meta["event_id"].to_numpy()
    lado_m = src == medio
    lado_o = ~lado_m & ~np.isin(src, list(excluir))
    eventos = np.intersect1d(np.unique(evs[lado_m]), np.unique(evs[lado_o]))
    X = sparse.csr_matrix(X, dtype=np.float64)

    def media_por_evento(mask):
        filas = np.flatnonzero(mask & np.isin(evs, eventos))
        e = np.searchsorted(eventos, evs[filas])
        w = 1.0 / np.bincount(e, minlength=len(eventos))[e]
        P = sparse.csr_matrix((w, (e, np.arange(len(filas)))), shape=(len(eventos), len(filas)))
        return (P @ X[filas]).tocsr()

    return eventos, media_por_evento(lado_m), media_por_evento(lado_o)


def log_odds(y_i, y_j, prior, n_i=None, n_j=None, a0=None):
    """Log-odds con prior de Dirichlet informativo (Monroe et al. 2008, ec. 16 y 18).

    δ_w = log[(y_iw + α_w) / (n_i + α_0 − y_iw − α_w)] − log[(y_jw + α_w) / (n_j + α_0 − y_jw − α_w)],
    var(δ_w) ≈ 1/(y_iw + α_w) + 1/(y_jw + α_w). Positivo: más propio de i.

    Sin `n_i`/`n_j`, la versión original con conteos de tokens (n = total de la
    fila, α_0 = Σ α_w). En el diseño emparejado se usa la presencia por titular:
    y = eventos (ponderados) cuyo titular lleva el término y n = número de eventos,
    igual en los dos lados; δ es la diferencia de logits de las tasas suavizadas.
    Así, si el medio y los otros usan el término igual en los mismos eventos,
    δ = 0 exactamente (con tokens, la diferencia de longitud de los titulares
    desplazaría todos los δ). Acepta matrices (réplicas × vocabulario)."""
    y_i, y_j, a = np.asarray(y_i, float), np.asarray(y_j, float), np.asarray(prior, float)
    a0 = a.sum() if a0 is None else a0
    n_i = y_i.sum(axis=-1, keepdims=True) if n_i is None else np.asarray(n_i, float)
    n_j = y_j.sum(axis=-1, keepdims=True) if n_j is None else np.asarray(n_j, float)
    delta = (np.log(y_i + a) - np.log(n_i + a0 - y_i - a)) - (np.log(y_j + a) - np.log(n_j + a0 - y_j - a))
    var = 1 / (y_i + a) + 1 / (y_j + a)
    return delta, var


def bh_adjust(p_values) -> np.ndarray:
    """q-valores de Benjamini-Hochberg (FDR). Con miles de términos por celda Holm
    (error familiar) deja casi todo fuera; para explorar vocabulario se usa FDR y
    Holm se reporta aparte."""
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    order = np.argsort(p)
    q = p[order] * n / np.arange(1, n + 1)
    q = np.minimum(1, np.minimum.accumulate(q[::-1])[::-1])
    out = np.empty_like(q)
    out[order] = q
    return out


def pesos_bootstrap(grupos: np.ndarray, reps: int, rng) -> np.ndarray:
    """Pesos (réplicas × eventos) de un bootstrap por conglomerados: se remuestrean
    los grupos con reemplazo y cada evento hereda el número de veces que salió su grupo."""
    g = int(grupos.max()) + 1
    draws = rng.integers(0, g, size=(reps, g))
    cuenta = np.zeros((reps, g), dtype=np.float32)
    np.add.at(cuenta, (np.arange(reps)[:, None], draws), 1)
    return cuenta[:, grupos]


def bootstrap_log_odds(A, B, prior, a0, grupos, reps, seed, bloque=250):
    """δ de presencia para cada réplica del bootstrap por conglomerados (`grupos`)."""
    rng = np.random.default_rng(seed)
    out = []
    At, Bt = A.T.tocsr(), B.T.tocsr()
    for r0 in range(0, reps, bloque):
        W = pesos_bootstrap(grupos, min(bloque, reps - r0), rng)
        n = W.sum(axis=1, keepdims=True)
        yi = np.asarray(At @ W.T).T
        yj = np.asarray(Bt @ W.T).T
        out.append(log_odds(yi, yj, prior, n, n, a0)[0])
    return np.vstack(out)


def comparar(meta, X, vocab, prior, medio, excluir=(), reps=1000, seed=42, min_eventos=10, meses=True):
    """Log-odds de presencia del medio frente a los otros medios en los mismos
    eventos, con bootstrap por eventos (y por meses si `meses`). `prior` =
    (α_w, α_0): α_0 titulares ficticios con la tasa de fondo de cada término. Sólo
    términos presentes en ≥ `min_eventos` eventos de la comparación."""
    prior, a0 = prior
    eventos, A, B = matrices_emparejadas(meta, X, medio, excluir)
    if len(eventos) < 30:
        return None, 0
    ev_m = np.asarray((A > 0).sum(axis=0)).ravel()
    ev_o = np.asarray((B > 0).sum(axis=0)).ravel()
    ev_any = np.asarray(((A + B) > 0).sum(axis=0)).ravel()
    keep = np.flatnonzero(ev_any >= min_eventos)
    A, B = A[:, keep].tocsr(), B[:, keep].tocsr()
    a = prior[keep]
    y_i = np.asarray(A.sum(axis=0)).ravel()
    y_j = np.asarray(B.sum(axis=0)).ravel()
    n = len(eventos)
    delta, var = log_odds(y_i, y_j, a, n, n, a0)
    boot = bootstrap_log_odds(A, B, a, a0, np.arange(n), reps, seed)
    se = boot.std(axis=0, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(se > 0, delta / se, 0.0)
    p = 2 * norm.sf(np.abs(z))
    # eventos discordantes: sólo el medio usa el término, o sólo los otros
    ambos = np.asarray((A > 0).multiply(B > 0).sum(axis=0)).ravel()
    solo_m = ev_m[keep] - ambos
    solo_o = ev_o[keep] - ambos
    tab = pd.DataFrame({
        "termino": np.asarray(vocab)[keep], "n_eventos_medio": ev_m[keep], "n_eventos_otros": ev_o[keep],
        "n_solo_medio": solo_m, "n_solo_otros": solo_o,
        "frac_medio": y_i / n, "frac_otros": y_j / n,
        "delta": delta, "z_monroe": delta / np.sqrt(var), "se": se, "z": z,
        "ic_bajo": np.quantile(boot, 0.025, axis=0), "ic_alto": np.quantile(boot, 0.975, axis=0),
        "p": p, "q_bh": bh_adjust(p), "p_holm": holm_adjust(p),
    })
    if meses:
        ev_mes = meta.drop_duplicates("event_id").set_index("event_id")["mes"].loc[eventos].to_numpy()
        _, grupos = np.unique(ev_mes, return_inverse=True)
        se_m = bootstrap_log_odds(A, B, a, a0, grupos, reps, seed + 1).std(axis=0, ddof=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            tab["z_mes"] = np.where(se_m > 0, delta / se_m, 0.0)
    return tab, len(eventos)


def proporciones_emparejadas(meta, F: pd.DataFrame, medio, excluir=(), reps=2000, seed=42):
    """Proporción de titulares con cada forma: el medio frente a los otros medios
    en los mismos eventos, con IC por bootstrap de eventos. También los índices
    de personalización (cociente de sumas sobre los eventos)."""
    eventos, A, B = matrices_emparejadas(meta, F.to_numpy(dtype=float), medio, excluir)
    if not len(eventos):
        return pd.DataFrame()
    A, B = A.toarray(), B.toarray()
    cols = list(F.columns)
    W = pesos_bootstrap(np.arange(len(eventos)), reps, np.random.default_rng(seed))
    sa, sb = A.sum(axis=0), B.sum(axis=0)
    ba, bb = W @ A, W @ B
    nb = W.sum(axis=1, keepdims=True)
    rows = []
    for k, c in enumerate(cols):
        d = (ba[:, k] - bb[:, k]) / nb[:, 0]
        rows.append({"forma": c, "eventos": len(eventos), "prop_medio": sa[k] / len(eventos),
                     "prop_otros": sb[k] / len(eventos), "diferencia": (sa[k] - sb[k]) / len(eventos),
                     "ic_bajo": np.quantile(d, 0.025), "ic_alto": np.quantile(d, 0.975),
                     "p": min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean()) + 1 / reps)})
    for nombre, (num, den, _) in INDICES.items():
        i, j = cols.index(num), cols.index(den)
        with np.errstate(invalid="ignore", divide="ignore"):
            d = ba[:, i] / ba[:, j] - bb[:, i] / bb[:, j]
        d = d[np.isfinite(d)]
        pm, po = sa[i] / sa[j] if sa[j] else np.nan, sb[i] / sb[j] if sb[j] else np.nan
        rows.append({"forma": nombre, "eventos": len(eventos), "prop_medio": pm, "prop_otros": po,
                     "diferencia": pm - po, "ic_bajo": np.quantile(d, 0.025) if len(d) else np.nan,
                     "ic_alto": np.quantile(d, 0.975) if len(d) else np.nan,
                     "p": min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean()) + 1 / reps) if len(d) else np.nan,
                     "n_ref_medio": sa[j], "n_ref_otros": sb[j]})
    return pd.DataFrame(rows)


def newcombe(k1, n1, k2, n2):
    """IC 95 % de p2 − p1 (método híbrido de Newcombe con intervalos de Wilson)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_interval(k1, n1)
    l2, u2 = wilson_interval(k2, n2)
    d = p2 - p1
    return d, d - np.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), d + np.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)


# ── datos ────────────────────────────────────────────────────────────────────


def precision_fecha_rcn(out: Path, min_dia: float) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Proporción mensual de titulares de RCN con fecha al día (subcorpus público,
    periodo Duque) y el primer mes desde el que TODOS los meses de Duque superan
    `min_dia`."""
    p = pd.read_parquet(out / "prepared.parquet", columns=["source_id", "government_id", "published_date",
                                                          "date_precision"])
    r = p[(p["source_id"] == RCN)].copy()
    r["mes"] = pd.to_datetime(r["published_date"]).dt.to_period("M")
    tab = r.groupby(["mes", "government_id"])["date_precision"].agg(
        titulares="size", con_dia=lambda s: int((s == "day").sum())).reset_index()
    tab["pct_dia"] = 100 * tab["con_dia"] / tab["titulares"]
    duque = tab[tab["government_id"] == "duque"].sort_values("mes")
    ok = (duque["pct_dia"] >= 100 * min_dia).to_numpy()
    # último mes de Duque que no cumple; la ventana empieza en el siguiente
    falla = np.flatnonzero(~ok)
    desde = duque["mes"].iloc[falla[-1] + 1] if len(falla) else duque["mes"].iloc[0]
    tab["mes"] = tab["mes"].astype(str)
    return tab, desde.to_timestamp()


def cargar(out: Path):
    ev = pd.read_parquet(out / "eventos" / "eventos.parquet")
    summ = pd.read_csv(out / "eventos" / "eventos_resumen.csv",
                       usecols=["event_id", "n_medios", "gobierno", "topic", "etiqueta_topic", "fecha_inicio"])
    ev = ev.merge(summ, on="event_id", how="left")
    ev["texto"] = ev["title"].map(normalize)
    ev["n_palabras"] = ev["texto"].str.split().str.len()
    ev["mes"] = pd.to_datetime(ev["fecha_inicio"]).dt.to_period("M").astype(str)
    return ev.reset_index(drop=True), summ


def matriz_terminos(ev: pd.DataFrame, stop: set[str], min_eventos: int):
    """Matriz binaria titular × término (unigramas y bigramas presentes en ≥ `min_eventos` eventos)."""
    sets = [terminos(t, stop) for t in ev["title"]]
    eventos_por = {}
    for e, s in zip(ev["event_id"].to_numpy(), sets):
        for t in s:
            eventos_por.setdefault(t, set()).add(e)
    vocab = sorted(t for t, es in eventos_por.items() if len(es) >= min_eventos)
    pos = {t: k for k, t in enumerate(vocab)}
    rows, cols = [], []
    for i, s in enumerate(sets):
        for t in s:
            if t in pos:
                rows.append(i)
                cols.append(pos[t])
    X = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(ev), len(vocab)))
    return X, vocab, sets


# ── análisis ─────────────────────────────────────────────────────────────────


def recorte_rcn(part: pd.DataFrame, medio: str, gobierno: str, rcn_desde) -> pd.DataFrame:
    if medio == RCN and gobierno == "duque":
        return part[pd.to_datetime(part["fecha_inicio"]) >= rcn_desde]
    return part


def contagio_formato(own_sets: list[set[str]]) -> dict[str, float]:
    """Para cada término, fracción de los titulares del medio que lo usan y que
    llevan además un marcador de firma o programa (`CONTAGIO`)."""
    tot, con = {}, {}
    for s in own_sets:
        f = any(t in CONTAGIO for t in s)
        for t in s:
            tot[t] = tot.get(t, 0) + 1
            con[t] = con.get(t, 0) + f
    return {t: con[t] / tot[t] for t in tot}


def analisis_log_odds(ev, X, vocab, prior, rcn_desde, args, sets):
    nucleo = ~ev["es_seguimiento"].to_numpy()
    filas, resumen = [], []
    for g in GOVS:
        for m in MEDIA:
            t0 = time.monotonic()
            base = recorte_rcn(ev[ev["gobierno"] == g], m, g, rcn_desde)
            core = base[~base["es_seguimiento"]]
            tab, n_ev = comparar(core, X[core.index], vocab, prior, m, reps=args.reps, seed=args.seed,
                                 min_eventos=args.min_eventos)
            tab.insert(0, "gobierno", g)
            tab.insert(0, "medio", m)
            # robustez: con seguimiento, sin RCN entre los otros, ventana común (Duque)
            rob = {"seg": (base, ()), "sinrcn": (core, (RCN,) if m != RCN else None)}
            if g == "duque":
                rob["ventana"] = (core[pd.to_datetime(core["fecha_inicio"]) >= rcn_desde], ())
            for nombre, (sub, excl) in rob.items():
                if excl is None:
                    tab[f"delta_{nombre}"], tab[f"z_{nombre}"] = np.nan, np.nan
                    continue
                r, _ = comparar(sub, X[sub.index], vocab, prior, m, excluir=excl, reps=max(200, args.reps // 2),
                                seed=args.seed + 7, min_eventos=1, meses=False)
                r = r.set_index("termino").reindex(tab["termino"])
                tab[f"delta_{nombre}"] = r["delta"].to_numpy()
                tab[f"z_{nombre}"] = r["z"].to_numpy()
            if "z_ventana" not in tab:
                tab["delta_ventana"], tab["z_ventana"] = np.nan, np.nan
            cont = contagio_formato([sets[i] for i in core.index[core["source_id"] == m]])
            tab["frac_con_firma_programa"] = tab["termino"].map(cont).fillna(0.0)
            filas.append(tab)
            logging.info("log-odds %s · %s: %s eventos, %s términos (%.0f s)", m, g, n_ev, len(tab),
                         time.monotonic() - t0)
    res = pd.concat(filas, ignore_index=True)
    res["clase"] = res["termino"].map(clase_termino)
    res.loc[res["frac_con_firma_programa"] >= UMBRAL_CONTAGIO_FORMATO, "clase"] = "formato"
    res["tipo"] = np.where(res["termino"].str.contains(" "), "bigrama", "unigrama")
    res["distintiva"] = ((res["delta"] > 0) & (res["q_bh"] < 0.05) & (res["n_eventos_medio"] >= args.min_eventos)
                         & (res["n_solo_medio"] >= args.min_discordantes))
    res["evitada"] = ((res["delta"] < 0) & (res["q_bh"] < 0.05) & (res["n_eventos_otros"] >= args.min_eventos)
                      & (res["n_solo_otros"] >= args.min_discordantes))
    sig = lambda c: res[c].fillna(np.inf) >= 1.96  # noqa: E731  (NaN = la prueba no aplica)
    sig_neg = lambda c: res[c].fillna(-np.inf) <= -1.96  # noqa: E731
    res["robusta"] = res["distintiva"] & (res["z_mes"] >= 1.96) & (res["z_seg"] >= 1.96) & sig("z_sinrcn")
    res["robusta_evitada"] = (res["evitada"] & (res["z_mes"] <= -1.96) & (res["z_seg"] <= -1.96)
                              & (res["z_sinrcn"].isna() | sig_neg("z_sinrcn")))
    return res


def analisis_cambio(lo: pd.DataFrame) -> pd.DataFrame:
    """Cambio Duque → Petro del log-odds de cada término, por medio (bootstrap por
    eventos; los conjuntos de eventos de los dos gobiernos son disjuntos)."""
    filas = []
    for m in MEDIA:
        d = lo[(lo["medio"] == m) & (lo["gobierno"] == "duque")].set_index("termino")
        p = lo[(lo["medio"] == m) & (lo["gobierno"] == "petro")].set_index("termino")
        comunes = d.index.intersection(p.index)
        d, p = d.loc[comunes], p.loc[comunes]
        dd = p["delta"] - d["delta"]
        se = np.sqrt(d["se"] ** 2 + p["se"] ** 2)
        z = (dd / se.where(se > 0)).fillna(0.0)
        pv = np.asarray(2 * norm.sf(np.abs(z)))
        filas.append(pd.DataFrame({
            "medio": m, "termino": comunes, "clase": d["clase"].to_numpy(),
            "delta_duque": d["delta"].to_numpy(), "delta_petro": p["delta"].to_numpy(),
            "z_duque": d["z"].to_numpy(), "z_petro": p["z"].to_numpy(),
            "n_eventos_medio_duque": d["n_eventos_medio"].to_numpy(),
            "n_eventos_medio_petro": p["n_eventos_medio"].to_numpy(),
            "cambio": dd.to_numpy(), "ic_bajo": (dd - 1.96 * se).to_numpy(), "ic_alto": (dd + 1.96 * se).to_numpy(),
            "z_cambio": z.to_numpy(), "p": pv, "q_bh": bh_adjust(pv), "p_holm": holm_adjust(pv),
            "distintiva_duque": d["distintiva"].to_numpy(), "distintiva_petro": p["distintiva"].to_numpy(),
        }))
    return pd.concat(filas, ignore_index=True)


def analisis_tema(ev, X, vocab, prior, rcn_desde, args):
    core = ev[~ev["es_seguimiento"]]
    filas, tamanos = [], []
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(core[core["gobierno"] == g], m, g, rcn_desde)
            for topic, part in base.groupby("topic"):
                if topic in TEMAS_EXCLUIDOS_POR_TEMA:
                    continue
                n_ev = part.loc[part["source_id"] == m, "event_id"].nunique()
                tamanos.append({"medio": m, "gobierno": g, "topic": topic, "eventos_medio": n_ev})
                if n_ev < args.min_eventos_tema:
                    continue
                tab, n = comparar(part, X[part.index], vocab, prior, m, reps=args.reps // 2, seed=args.seed,
                                  min_eventos=args.min_eventos, meses=False)
                if tab is None:
                    continue
                tab.insert(0, "eventos", n)
                tab.insert(0, "etiqueta_topic", part["etiqueta_topic"].iat[0])
                tab.insert(0, "topic", topic)
                tab.insert(0, "gobierno", g)
                tab.insert(0, "medio", m)
                filas.append(tab)
    res = pd.concat(filas, ignore_index=True)
    res["clase"] = res["termino"].map(clase_termino)
    res["distintiva"] = ((res["delta"] > 0) & (res["q_bh"] < 0.05) & (res["n_eventos_medio"] >= args.min_eventos)
                         & (res["n_solo_medio"] >= args.min_discordantes))
    return res, pd.DataFrame(tamanos)


def matriz_formas(ev: pd.DataFrame) -> pd.DataFrame:
    rows = [formas_nombrar(t, g) for t, g in zip(ev["texto"], ev["gobierno"])]
    return pd.DataFrame(rows, index=ev.index)[FORMAS].astype(bool)


def _props_celda(own, F, m, g, ventana):
    filas, n = [], len(own)
    for c in FORMAS:
        k = int(F.loc[own.index, c].sum())
        lo, hi = wilson_interval(k, n)
        filas.append({"medio": m, "gobierno": g, "ventana": ventana, "forma": c, "titulares": n, "con_forma": k,
                      "prop": k / n, "ic_bajo": lo, "ic_alto": hi})
    for nombre, (num, den, _) in INDICES.items():
        k, n_ref = int(F.loc[own.index, num].sum()), int(F.loc[own.index, den].sum())
        lo, hi = wilson_interval(k, n_ref) if n_ref else (np.nan, np.nan)
        filas.append({"medio": m, "gobierno": g, "ventana": ventana, "forma": nombre, "titulares": n_ref,
                      "con_forma": k, "prop": k / n_ref if n_ref else np.nan, "ic_bajo": lo, "ic_alto": hi})
    return filas


def analisis_formas(ev, F, rcn_desde, args):
    """Proporciones por medio × gobierno (Wilson), cambio Duque → Petro (Newcombe)
    y comparación emparejada frente a los otros medios (bootstrap por eventos),
    en los titulares núcleo de eventos domésticos. `ventana`: «principal» (RCN
    en Duque desde `rcn_desde`) o «comun» (todos los medios en Duque desde
    `rcn_desde`, para ver si el cambio Duque → Petro depende del periodo)."""
    dom = ev[~ev["es_seguimiento"] & ~ev["topic"].isin(TEMAS_EXTERIOR)]
    props, pareadas = [], []
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(dom[dom["gobierno"] == g], m, g, rcn_desde)
            props += _props_celda(base[base["source_id"] == m], F, m, g, "principal")
            if g == "duque":
                comun = base[pd.to_datetime(base["fecha_inicio"]) >= rcn_desde]
                props += _props_celda(comun[comun["source_id"] == m], F, m, g, "comun")
            for etiqueta, excl in (("todos", ()), ("sin_rcn", (RCN,))):
                if etiqueta == "sin_rcn" and m == RCN:
                    continue
                r = proporciones_emparejadas(base, F.loc[base.index], m, excluir=excl, reps=args.reps_formas,
                                             seed=args.seed)
                r.insert(0, "otros", etiqueta)
                r.insert(0, "gobierno", g)
                r.insert(0, "medio", m)
                pareadas.append(r)
    props = pd.DataFrame(props)
    cambio = []
    for ventana in ("principal", "comun"):
        for m in MEDIA:
            for c in [*FORMAS, *INDICES]:
                a = props[(props["medio"] == m) & (props["forma"] == c)]
                d_ = a[(a["gobierno"] == "duque") & (a["ventana"] == ventana)].iloc[0]
                p_ = a[a["gobierno"] == "petro"].iloc[0]
                if not d_.titulares or not p_.titulares:
                    continue
                d, lo, hi = newcombe(d_.con_forma, d_.titulares, p_.con_forma, p_.titulares)
                cambio.append({"ventana_duque": ventana, "medio": m, "forma": c, "prop_duque": d_.prop,
                               "prop_petro": p_.prop, "cambio": d, "ic_bajo": lo, "ic_alto": hi,
                               "n_duque": d_.titulares, "n_petro": p_.titulares})
    props.loc[props["gobierno"] == "petro", "ventana"] = "principal"
    return props, pd.concat(pareadas, ignore_index=True), pd.DataFrame(cambio)


def analisis_formato(ev, rcn_desde, args):
    """Marcas de formato del titular (preguntas, «videos», «en vivo»…): el medio
    frente a los otros en los mismos eventos. Se reportan aparte para no
    confundir formato con encuadre."""
    core = ev[~ev["es_seguimiento"]]
    M = pd.DataFrame({k: core["texto"].str.contains(p, regex=True) for k, p in MARCAS_FORMATO.items()})
    filas = []
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(core[core["gobierno"] == g], m, g, rcn_desde)
            eventos, A, B = matrices_emparejadas(base, M.loc[base.index].to_numpy(float), m)
            sa, sb = np.asarray(A.sum(axis=0)).ravel(), np.asarray(B.sum(axis=0)).ravel()
            W = pesos_bootstrap(np.arange(len(eventos)), args.reps_formas, np.random.default_rng(args.seed))
            dif = (W @ (A.toarray() - B.toarray())) / W.sum(axis=1, keepdims=True)
            for k, c in enumerate(M.columns):
                filas.append({"medio": m, "gobierno": g, "marca": c, "eventos": len(eventos),
                              "prop_medio": sa[k] / len(eventos), "prop_otros": sb[k] / len(eventos),
                              "diferencia": (sa[k] - sb[k]) / len(eventos),
                              "ic_bajo": np.quantile(dif[:, k], 0.025), "ic_alto": np.quantile(dif[:, k], 0.975)})
    return pd.DataFrame(filas)


ACTORES = {"petro": "gustavo", "duque": "ivan", "trump": "donald", "maduro": "nicolas", "uribe": "alvaro",
            "biden": "joe", "benedetti": "armando"}


def nombre_completo_actores(ev, rcn_desde) -> pd.DataFrame:
    """Entre los titulares núcleo que mencionan el apellido de un actor, % que
    trae también el nombre de pila delante. Si un medio usa el nombre completo
    con todos los actores, es convención de la casa y no un encuadre del presidente."""
    core = ev[~ev["es_seguimiento"]]
    filas = []
    for g in GOVS:
        for m in MEDIA:
            own = recorte_rcn(core[core["gobierno"] == g], m, g, rcn_desde)
            own = own[own["source_id"] == m]
            for ap, pila in ACTORES.items():
                men = own["texto"].str.contains(rf"\b{ap}\b")
                n = int(men.sum())
                if n < 20:
                    continue
                k = int(own.loc[men, "texto"].str.contains(rf"\b{pila} {ap}\b").sum())
                lo, hi = wilson_interval(k, n)
                filas.append({"medio": m, "gobierno": g, "actor": ap, "titulares_con_apellido": n,
                              "con_nombre_de_pila": k, "prop": k / n, "ic_bajo": lo, "ic_alto": hi})
    return pd.DataFrame(filas)


def tamanos(ev, rcn_desde):
    filas = []
    for g in GOVS:
        for m in MEDIA:
            for ventana in ("completa", "rcn"):
                base = ev[ev["gobierno"] == g]
                if ventana == "rcn":
                    if not (m == RCN and g == "duque"):
                        continue
                    base = recorte_rcn(base, m, g, rcn_desde)
                core = base[~base["es_seguimiento"]]
                ev_m = core.loc[core["source_id"] == m, "event_id"].unique()
                filas.append({
                    "medio": m, "gobierno": g, "ventana": "desde " + rcn_desde.strftime("%Y-%m") if ventana == "rcn"
                    else "completa",
                    "eventos": len(ev_m),
                    "eventos_3_mas_medios": int(core[core["event_id"].isin(ev_m)].groupby("event_id")["source_id"]
                                                .nunique().ge(3).sum()),
                    "titulares_nucleo": int((core["source_id"] == m).sum()),
                    "titulares_seguimiento": int((base["es_seguimiento"] & (base["source_id"] == m)).sum()),
                    "titulares_otros_en_sus_eventos": int(((core["source_id"] != m) & core["event_id"].isin(ev_m)).sum()),
                    "eventos_domesticos": int(core[(core["source_id"] == m) & ~core["topic"].isin(TEMAS_EXTERIOR)]
                                              ["event_id"].nunique()),
                    "palabras_por_titular": round(float(core.loc[core["source_id"] == m, "n_palabras"].mean()), 2),
                    "palabras_por_titular_otros": round(float(core.loc[(core["source_id"] != m)
                                                                        & core["event_id"].isin(ev_m),
                                                                        "n_palabras"].mean()), 2),
                })
    return pd.DataFrame(filas)


# ── ejemplos ─────────────────────────────────────────────────────────────────


def _tabla_evento(ev, k, resaltar=None) -> list[str]:
    part = ev[(ev["event_id"] == k) & ~ev["es_seguimiento"]].sort_values("source_id",
                                                                         key=lambda s: s.map(MEDIA.index))
    r0 = part.iloc[0]
    lines = [f"**Evento {k}** · {r0['fecha_inicio']} · {r0['n_medios']} medios · {r0['etiqueta_topic']}", "",
             "| Medio | Titular |", "|---|---|"]
    for r in part.itertuples():
        nombre = MEDIA_NAMES[r.source_id]
        lines.append(f"| {'**' + nombre + '**' if r.source_id == resaltar else nombre} | {r.title} |")
    return lines + [""]


def ejemplos_md(ev, sets, lo, F, rcn_desde, seed) -> str:
    rng = np.random.default_rng(seed)
    core = ev[~ev["es_seguimiento"]]
    lines = [
        "# Ejemplos de elección léxica dentro del mismo hecho", "",
        "Titulares reconstruidos desde la URL (sin tildes, cifras ni puntuación). Cada tabla es un evento: los",
        "titulares núcleo de cada medio, uno por medio. En negrita, el medio cuya palabra distintiva se ilustra.",
        "El emparejamiento acierta el mismo hecho en el 81 % de los casos (IC 95 % 72–90 %): algún evento puede",
        "mezclar dos hechos parecidos. Semilla " + str(seed) + ".", "",
        "## 1. Palabras distintivas por medio", "",
        "Para cada medio y gobierno, las tres palabras de contenido más distintivas entre las robustas (z bootstrap",
        "por eventos, ver LEEME.md) y dos eventos donde el medio la usa y al menos otro medio no.", "",
    ]
    for g in GOVS:
        lines += [f"### Gobierno {GOV_NAMES[g]}", ""]
        for m in MEDIA:
            top = lo[(lo["medio"] == m) & (lo["gobierno"] == g) & lo["robusta"] & (lo["clase"] == "contenido")]
            top = top.sort_values("z", ascending=False).head(3)
            if top.empty:
                continue
            lines += [f"#### {MEDIA_NAMES[m]}", ""]
            base = recorte_rcn(core[core["gobierno"] == g], m, g, rcn_desde)
            own = base[base["source_id"] == m]
            for r in top.itertuples():
                lines += [(f"*«{r.termino}»*: en el {100 * r.frac_medio:.1f} % de sus titulares frente al "
                           f"{100 * r.frac_otros:.1f} % de los otros medios en los mismos eventos "
                           f"(log-odds {r.delta:+.2f}, z {r.z:.1f}, {r.n_eventos_medio} eventos).").replace(".", ",")
                          .replace("eventos),", "eventos)."), ""]
                con = own[[r.termino in sets[i] for i in own.index]]
                cand = []
                for k in con["event_id"].unique():
                    otros = base[(base["event_id"] == k) & (base["source_id"] != m)]
                    if len(otros) and not all(r.termino in sets[i] for i in otros.index):
                        cand.append((-otros["source_id"].nunique(), rng.random(), k))
                for _, _, k in sorted(cand)[:2]:
                    lines += _tabla_evento(ev, k, resaltar=m)
    lines += ["## 2. Cómo se nombra al gobierno en el mismo hecho", "",
              "Eventos domésticos en los que un medio escribe «Gobierno Petro/Duque» y otro medio escribe",
              "«Gobierno» o «Gobierno nacional» sin el apellido.", ""]
    dom = core[~core["topic"].isin(TEMAS_EXTERIOR)]
    for g in GOVS:
        part = dom[dom["gobierno"] == g]
        fp = F.loc[part.index]
        per = part.assign(p=fp["gobierno_apellido"].to_numpy(),
                          i=(fp["gobierno_nacional"] | fp["gobierno_generico"]).to_numpy() & ~fp["gobierno_apellido"]
                          .to_numpy())
        agg = per.groupby("event_id")[["p", "i"]].any()
        ks = agg[agg["p"] & agg["i"]].index.to_numpy()
        lines += [f"### Gobierno {GOV_NAMES[g]} ({len(ks)} eventos con los dos usos)", ""]
        for k in rng.permutation(ks)[:3]:
            lines += _tabla_evento(ev, k)
    ej = core[(core["fecha_inicio"] == "2025-03-05") & core["texto"].str.contains("urgencia")]
    if len(ej):
        lines += ["### El ejemplo del README: mensaje de urgencia de la reforma a la salud", ""]
        lines += _tabla_evento(ev, ej["event_id"].iat[0])
    return "\n".join(lines)


# ── figuras (26 a 29) ────────────────────────────────────────────────────────

MARCA_CLASE = {"formato": " [formato]", "atribucion": " [atrib.]", "contenido": ""}


def fig_distintivas(lo, rcn_desde, res, n=8):
    fig, axes = plt.subplots(len(MEDIA), 2, figsize=(12, 17))
    xmax = 0
    for i, m in enumerate(MEDIA):
        for j, g in enumerate(GOVS):
            ax = axes[i, j]
            t = lo[(lo["medio"] == m) & (lo["gobierno"] == g) & lo["distintiva"]]
            n_formato = int((t["clase"] == "formato").sum())
            t = t[t["clase"] != "formato"].sort_values("z", ascending=False).head(n).iloc[::-1]
            y = np.arange(len(t))
            alpha = np.where(t["robusta"], 1.0, 0.45)
            color = np.where(t["clase"] == "contenido", GOV_COLORS[g], "#b8b6ad")  # atribución en gris
            for yy, r, a, c in zip(y, t.itertuples(), alpha, color):
                ax.barh(yy, r.delta, color=c, alpha=a, height=0.62, edgecolor=SURFACE, linewidth=1)
                ax.plot([r.ic_bajo, r.ic_alto], [yy, yy], color=INK2, lw=1)
            ax.set_yticks(y, [f"{r.termino}{MARCA_CLASE[r.clase]}" for r in t.itertuples()], fontsize=8.5)
            xmax = max(xmax, t["ic_alto"].max() if len(t) else 0)
            sub = (f"{MEDIA_NAMES[m]} · {GOV_NAMES[g]}")
            if m == RCN and g == "duque":
                sub += f" (desde {rcn_desde:%Y-%m})"
            if n_formato:
                sub += f"  · +{n_formato} de formato omitidas"
            ax.set_title(sub, fontsize=10)
            ax.grid(axis="y", visible=False)
            ax.axvline(0, color=AXIS, lw=0.8)
            ax.set_ylim(len(t) - n - 0.4, len(t) - 0.4)  # mismo alto de barra, alineadas arriba
            if not len(t):
                ax.text(0.5, 0.5, "sin palabras significativas", transform=ax.transAxes, ha="center", color=MUTED)
    for ax in axes.ravel():
        ax.set_xlim(0, xmax * 1.05)
    for ax in axes[-1]:
        ax.set_xlabel("log-odds vs. otros medios, mismos eventos (IC 95 %)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=GOV_COLORS["duque"], label="contenido, Duque"),
               plt.Rectangle((0, 0), 1, 1, color=GOV_COLORS["petro"], label="contenido, Petro"),
               plt.Rectangle((0, 0), 1, 1, color="#b8b6ad", label="verbo de atribución"),
               plt.Rectangle((0, 0), 1, 1, color=MUTED, alpha=0.45, label="significativa pero no robusta")]
    fig.tight_layout(h_pad=1.6, w_pad=3)
    _margins(fig, handles, ncol=4, top_in=0.9, bottom_in=0.6)
    _save(fig, res, "26_palabras_distintivas.png", "Palabras propias de cada medio al contar el mismo hecho",
          "Hasta ocho términos con mayor z (bootstrap por eventos, FDR q < 0,05, ≥10 eventos y ≥5 en que sólo el medio lo usa) por medio y gobierno. "
          "Robusta = además z ≥ 1,96 con bootstrap por meses, con notas de seguimiento y sin RCN entre los otros. "
          "Se omiten los términos de formato (programas, firmas, «en vivo», etiquetas del slug); los verbos de "
          "atribución van en gris. Titulares núcleo; los otros medios se promedian "
          f"dentro de cada evento. RCN en Duque sólo desde {rcn_desde:%Y-%m} (fecha al día). {NOTA_UMBRAL} {FUENTE}",
          note_y=0.0)


def fig_cambio(cambio, res, n=6):
    fig, axes = plt.subplots(1, len(MEDIA), figsize=(16, 5.6))
    for ax, m in zip(axes, MEDIA):
        t = cambio[(cambio["medio"] == m) & (cambio["q_bh"] < 0.05) & (cambio["clase"] == "contenido")
                   & (cambio["n_eventos_medio_duque"] >= 5) & (cambio["n_eventos_medio_petro"] >= 5)]
        t = t.reindex(t["z_cambio"].abs().sort_values(ascending=False).index).head(n)
        t = t.sort_values("cambio")
        y = np.arange(len(t))
        for yy, r in zip(y, t.itertuples()):
            ax.plot([r.delta_duque, r.delta_petro], [yy, yy], color=AXIS, lw=2, zorder=1)
        ax.scatter(t["delta_duque"], y, s=60, color=GOV_COLORS["duque"], edgecolor=SURFACE, lw=1.5, zorder=2)
        ax.scatter(t["delta_petro"], y, s=60, color=GOV_COLORS["petro"], edgecolor=SURFACE, lw=1.5, zorder=2)
        ax.set_yticks(y, t["termino"], fontsize=8.5)
        ax.axvline(0, color=INK2, lw=0.8)
        ax.set_title(SHORT[m], fontsize=10)
        ax.grid(axis="y", visible=False)
        if not len(t):
            ax.text(0.5, 0.5, "sin cambios\nsignificativos", transform=ax.transAxes, ha="center", color=MUTED)
            ax.set_xticks([])
            ax.axvline(0, color=SURFACE, lw=2)
        ax.set_xlabel("log-odds vs. otros medios")
    handles = [Line2D([], [], marker="o", ls="", color=GOV_COLORS[g], ms=8, label=f"Gobierno {GOV_NAMES[g]}")
               for g in GOVS]
    fig.tight_layout(w_pad=2.5)
    _margins(fig, handles, ncol=2, top_in=0.9, bottom_in=0.8)
    _save(fig, res, "27_cambio_palabras.png", "Qué palabras de cada medio cambian de Duque a Petro",
          "Términos de contenido usados por el medio en ≥5 eventos de cada gobierno cuyo log-odds frente a los otros "
          "medios (mismos eventos) cambia con FDR q < 0,05 dentro del medio; hasta seis por medio, ordenados por el "
          "cambio. "
          "A la derecha de 0, el medio usa el término más que los otros al contar el mismo hecho. RCN en Duque sólo "
          f"con fecha al día (2020-09 en adelante, periodo COVID). {NOTA_UMBRAL} {FUENTE}")


def fig_formas(props, rcn_desde, res):
    formas = ["gobierno_apellido", "presidente_apellido", "nombre_completo", "apellido_solo",
              "gobierno_nacional", "gobierno_generico", "ministro", "ref_ejecutivo"]
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.5))
    x = np.arange(len(MEDIA))
    for ax, f in zip(axes.ravel(), formas):
        for k, g in enumerate(GOVS):
            t = props[(props["forma"] == f) & (props["gobierno"] == g)].set_index("medio").loc[MEDIA]
            xx = x + (k - 0.5) * 0.28
            ax.errorbar(xx, 100 * t["prop"], yerr=[100 * (t["prop"] - t["ic_bajo"]), 100 * (t["ic_alto"] - t["prop"])],
                        fmt="o", color=GOV_COLORS[g], ms=7, mec=SURFACE, mew=1.5, elinewidth=1.4, capsize=0)
        ax.set_xticks(x, [SHORT[m] for m in MEDIA], fontsize=8, rotation=30, ha="right")
        ax.set_title(FORMAS_NOMBRE[f], fontsize=10)
        ax.set_ylim(0, None)
        ax.yaxis.set_major_formatter(FuncFormatter(
            lambda v, _: (f"{v:.0f} %" if float(v).is_integer() else f"{v:.1f} %").replace(".", ",")))
        ax.grid(axis="x", visible=False)
    handles = [Line2D([], [], marker="o", ls="", color=GOV_COLORS[g], ms=8, label=f"Gobierno {GOV_NAMES[g]}")
               for g in GOVS]
    fig.tight_layout(h_pad=2, w_pad=2)
    _margins(fig, handles, ncol=2, top_in=0.9, bottom_in=1.0)
    _save(fig, res, "28_formas_nombrar.png", "Cómo nombra cada medio al gobierno y al presidente",
          "% de los titulares núcleo de eventos domésticos (sin tópicos de otros países) con cada forma; el apellido "
          "es el del presidente de ese gobierno. IC 95 % de Wilson. Las escalas varían por panel. RCN en Duque sólo "
          f"desde {rcn_desde:%Y-%m}. «Mandatario», «Ejecutivo» y «Casa de Nariño» son casi inexistentes en los "
          f"titulares reconstruidos. {NOTA_UMBRAL} {FUENTE}")


def fig_personalizacion(props, pareadas, rcn_desde, res):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    x = np.arange(len(MEDIA))
    ax = axes[0]
    for k, g in enumerate(GOVS):
        t = props[(props["forma"] == "pers_gobierno") & (props["gobierno"] == g)].set_index("medio").loc[MEDIA]
        xx = x + (k - 0.5) * 0.28
        ax.errorbar(xx, 100 * t["prop"], yerr=[100 * (t["prop"] - t["ic_bajo"]), 100 * (t["ic_alto"] - t["prop"])],
                    fmt="o", color=GOV_COLORS[g], ms=8, mec=SURFACE, mew=1.5, elinewidth=1.4)
        for xi, n in zip(xx, t["titulares"]):
            ax.text(xi, -3, f"n={n}", ha="center", fontsize=7, color=MUTED)
    ax.set_xticks(x, [SHORT[m] for m in MEDIA])
    ax.set_ylim(-5, 40)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} %" if v >= 0 else ""))
    ax.set_title("«Gobierno Petro/Duque» entre los titulares que dicen «gobierno»", fontsize=10)
    ax.grid(axis="x", visible=False)
    ax = axes[1]
    for k, g in enumerate(GOVS):
        for otros, filled in (("todos", True), ("sin_rcn", False)):
            t = pareadas[(pareadas["forma"] == "pers_gobierno") & (pareadas["gobierno"] == g)
                         & (pareadas["otros"] == otros)].set_index("medio").reindex(MEDIA)
            xx = x + (k - 0.5) * 0.36 + (0.08 if not filled else -0.08)
            ax.errorbar(xx, 100 * t["diferencia"], yerr=[100 * (t["diferencia"] - t["ic_bajo"]),
                                                         100 * (t["ic_alto"] - t["diferencia"])],
                        fmt="o", color=GOV_COLORS[g], mfc=GOV_COLORS[g] if filled else SURFACE, ms=7,
                        mec=GOV_COLORS[g], mew=1.5, elinewidth=1.2)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x, [SHORT[m] for m in MEDIA])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f} pp"))
    ax.set_title("Lo mismo: el medio menos los otros medios, en los mismos eventos", fontsize=10)
    ax.grid(axis="x", visible=False)
    handles = [Line2D([], [], marker="o", ls="", color=GOV_COLORS[g], ms=8, label=f"Gobierno {GOV_NAMES[g]}")
               for g in GOVS]
    handles.append(Line2D([], [], marker="o", ls="", mfc=SURFACE, mec=INK2, ms=8, label="sin RCN entre los otros"))
    fig.tight_layout(w_pad=3)
    _margins(fig, handles, ncol=3, top_in=0.9, bottom_in=0.8)
    _save(fig, res, "29_personalizacion_gobierno.png", "¿«Gobierno Petro» o «el Gobierno»?",
          "Izquierda: entre los titulares núcleo de eventos domésticos que nombran al gobierno nacional («Gobierno "
          "Petro/Duque», «Gobierno nacional» o «Gobierno» sin más), % con el apellido; IC 95 % de Wilson. Derecha: "
          "el mismo índice del medio menos el de los otros medios en los mismos eventos (cociente de sumas sobre "
          f"los eventos), IC 95 % por bootstrap de eventos. RCN en Duque sólo desde {rcn_desde:%Y-%m}. {NOTA_UMBRAL} {FUENTE}")


# ── etapa principal ──────────────────────────────────────────────────────────


def _r(x, k=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=HERE / "resultados_publico")
    parser.add_argument("--reps", type=int, default=2000, help="Réplicas del bootstrap de log-odds")
    parser.add_argument("--reps-formas", type=int, default=2000, help="Réplicas del bootstrap de proporciones")
    parser.add_argument("--alpha0", type=float, default=100.0,
                        help="Peso del prior, en titulares ficticios con la tasa de fondo")
    parser.add_argument("--min-eventos", type=int, default=10,
                        help="Eventos distintos mínimos con el término (frecuencia mínima)")
    parser.add_argument("--min-discordantes", type=int, default=5,
                        help="Eventos mínimos en los que sólo el medio (o sólo los otros) usa el término")
    parser.add_argument("--min-eventos-tema", type=int, default=150,
                        help="Eventos mínimos del medio en un tema para el análisis por tema")
    parser.add_argument("--rcn-min-dia", type=float, default=0.75,
                        help="% mínimo de titulares de RCN con fecha al día, sostenido, para abrir su ventana Duque")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = args.output.resolve()
    res = out / "lexico"
    (res / "figuras").mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    fechas_rcn, rcn_desde = precision_fecha_rcn(out, args.rcn_min_dia)
    fechas_rcn.to_csv(res / "rcn_precision_fecha.csv", index=False)
    logging.info("RCN con fecha al día sostenida desde %s", rcn_desde.date())

    ev, _ = cargar(out)
    stop = stop_lexico()
    X, vocab, sets = matriz_terminos(ev, stop, args.min_eventos)
    core = ev[~ev["es_seguimiento"]]
    # prior: α_0 titulares ficticios con la tasa de presencia de cada término en
    # todos los titulares núcleo (los cinco medios, los dos gobiernos)
    tasa = (np.asarray(X[core.index].sum(axis=0)).ravel() + 0.5) / (len(core) + 1)
    prior = (args.alpha0 * tasa, args.alpha0)
    logging.info("%s titulares, %s términos con ≥%s eventos", len(ev), len(vocab), args.min_eventos)

    tam = tamanos(ev, rcn_desde)
    tam.to_csv(res / "tamanos.csv", index=False)

    lo = analisis_log_odds(ev, X, vocab, prior, rcn_desde, args, sets)
    lo.to_csv(res / "logodds_medio_gobierno.csv", index=False)
    cambio = analisis_cambio(lo)
    cambio.to_csv(res / "logodds_cambio_duque_petro.csv", index=False)
    tema, tam_tema = analisis_tema(ev, X, vocab, prior, rcn_desde, args)
    tema.to_csv(res / "logodds_tema.csv", index=False)
    tam_tema.to_csv(res / "tamanos_tema.csv", index=False)
    logging.info("log-odds listos (%.0f s)", time.monotonic() - t0)

    F = matriz_formas(ev)
    props, pareadas, cambio_formas = analisis_formas(ev, F, rcn_desde, args)
    props_p = props[props["ventana"] == "principal"]
    props.to_csv(res / "formas_nombrar.csv", index=False)
    pareadas.to_csv(res / "formas_nombrar_emparejado.csv", index=False)
    cambio_formas.to_csv(res / "formas_nombrar_cambio.csv", index=False)
    nombre_completo_actores(ev, rcn_desde).to_csv(res / "nombre_completo_actores.csv", index=False)
    formato = analisis_formato(ev, rcn_desde, args)
    formato.to_csv(res / "formato_titulares.csv", index=False)

    # robustez sin RCN: resumen por medio × gobierno
    rob = []
    for (m, g), t in lo.groupby(["medio", "gobierno"], sort=False):
        d = t[t["distintiva"]]
        ok = t[["delta", "delta_sinrcn"]].dropna()
        rob.append({
            "medio": m, "gobierno": g, "terminos": len(t), "distintivas": len(d), "robustas": int(t["robusta"].sum()),
            "distintivas_contenido": int((d["clase"] == "contenido").sum()),
            "pct_distintivas_z_mes_196": _r(100 * (d["z_mes"] >= 1.96).mean(), 1) if len(d) else None,
            "pct_distintivas_z_seg_196": _r(100 * (d["z_seg"] >= 1.96).mean(), 1) if len(d) else None,
            "pct_distintivas_z_sinrcn_196": _r(100 * (d["z_sinrcn"] >= 1.96).mean(), 1)
            if len(d) and m != RCN else None,
            "spearman_delta_sinrcn": _r(spearmanr(ok["delta"], ok["delta_sinrcn"])[0], 3) if len(ok) > 2 else None,
            "spearman_delta_seg": _r(spearmanr(t["delta"], t["delta_seg"], nan_policy="omit")[0], 3),
            "spearman_delta_ventana": _r(spearmanr(t["delta"], t["delta_ventana"], nan_policy="omit")[0], 3)
            if g == "duque" else None,
        })
    rob = pd.DataFrame(rob)
    rob_formas = pareadas[pareadas["forma"].isin(["gobierno_apellido", "pers_gobierno", "personal_amplio"])]
    rob_formas = rob_formas.pivot_table(index=["medio", "gobierno", "forma"], columns="otros",
                                        values=["diferencia", "ic_bajo", "ic_alto"]).reset_index()
    rob_formas.columns = ["_".join(c).strip("_") for c in rob_formas.columns]
    rob.to_csv(res / "robustez_sin_rcn.csv", index=False)
    rob_formas.to_csv(res / "robustez_sin_rcn_formas.csv", index=False)

    (res / "ejemplos_lexico.md").write_text(ejemplos_md(ev, sets, lo, F, rcn_desde, args.seed), encoding="utf-8")

    fig_distintivas(lo, rcn_desde, res)
    fig_cambio(cambio, res)
    fig_formas(props_p, rcn_desde, res)
    fig_personalizacion(props_p, pareadas, rcn_desde, res)

    # cifras clave
    def top(m, g, n=10, robusta=True):
        t = lo[(lo["medio"] == m) & (lo["gobierno"] == g) & lo["distintiva"] & (lo["clase"] == "contenido")]
        if robusta:
            t = t[t["robusta"]]
        return [f"{r.termino} ({r.delta:+.2f}; z {r.z:.1f}; {r.n_eventos_medio} ev.)"
                for r in t.sort_values("z", ascending=False).head(n).itertuples()]

    def prop(m, g, f):
        r = props_p[(props_p["medio"] == m) & (props_p["gobierno"] == g) & (props_p["forma"] == f)].iloc[0]
        return {"prop": _r(r.prop), "ic95": [_r(r.ic_bajo), _r(r.ic_alto)], "n": int(r.titulares)}

    def par(m, g, f, otros="todos"):
        r = pareadas[(pareadas["medio"] == m) & (pareadas["gobierno"] == g) & (pareadas["forma"] == f)
                     & (pareadas["otros"] == otros)]
        if r.empty:
            return None
        r = r.iloc[0]
        return {"medio": _r(r.prop_medio), "otros": _r(r.prop_otros), "diferencia": _r(r.diferencia),
                "ic95": [_r(r.ic_bajo), _r(r.ic_alto)], "eventos": int(r.eventos)}

    save_json(res / "lexico.json", {
        "parametros": {"reps": args.reps, "reps_formas": args.reps_formas, "alpha0": args.alpha0,
                       "min_eventos": args.min_eventos, "min_discordantes": args.min_discordantes, "min_eventos_tema": args.min_eventos_tema,
                       "rcn_min_dia": args.rcn_min_dia, "seed": args.seed, "terminos_vocabulario": len(vocab),
                       "temas_exterior_excluidos_en_formas": sorted(TEMAS_EXTERIOR)},
        "rcn": {"fecha_al_dia_sostenida_desde": rcn_desde.strftime("%Y-%m"),
                "eventos_duque_total": int(tam[(tam["medio"] == RCN) & (tam["gobierno"] == "duque")
                                               & (tam["ventana"] == "completa")]["eventos"].iat[0]),
                "eventos_duque_ventana": int(tam[(tam["medio"] == RCN) & (tam["ventana"] != "completa")]
                                             ["eventos"].iat[0])},
        "tamanos": tam.to_dict(orient="records"),
        "distintivas_por_celda": rob.to_dict(orient="records"),
        "top_contenido_robustas": {m: {g: top(m, g) for g in GOVS} for m in MEDIA},
        "cambios_significativos_bh": {m: int(((cambio["medio"] == m) & (cambio["q_bh"] < 0.05)).sum())
                                        for m in MEDIA},
        "formas": {m: {g: {f: prop(m, g, f) for f in [*FORMAS, *INDICES]} for g in GOVS} for m in MEDIA},
        "emparejado_gobierno_apellido": {m: {g: {"todos": par(m, g, "gobierno_apellido"),
                                                 "sin_rcn": par(m, g, "gobierno_apellido", "sin_rcn")}
                                             for g in GOVS} for m in MEDIA},
        "emparejado_pers_gobierno": {m: {g: par(m, g, "pers_gobierno") for g in GOVS} for m in MEDIA},
        "emparejado_personal_amplio": {m: {g: par(m, g, "personal_amplio") for g in GOVS} for m in MEDIA},
        "cambio_formas": cambio_formas[cambio_formas["forma"].isin(["gobierno_apellido", "pers_gobierno",
                                                                    "personal_amplio", "menciona_apellido"])]
        .round(4).to_dict(orient="records"),
        "segundos": round(time.monotonic() - t0),
    })
    logging.info("Listo en %.0f s → %s", time.monotonic() - t0, res)


if __name__ == "__main__":
    main()
