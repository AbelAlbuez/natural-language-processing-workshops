"""Silver standard de titulares sesgados: muestra, planillas para dos personas, evaluación y adjudicación.

    muestra    titulares del subcorpus público, estratificados por medio × gobierno y,
               dentro de cada celda, por si tienen evento (titulares de otros medios
               sobre el mismo hecho, umbral 0,80) y por si son candidatos a sesgo
               (léxico cargado o «Gobierno Petro/Duque»; titular que más se aparta de
               los otros del mismo evento). Escribe muestra.csv (lo que se ve),
               clave_no_abrir.csv (medio, URL, estrato y peso) y muestra.json.
    dividir    planilla_silver_persona_{1,2}.xlsx: las dobles en las dos, el resto
               repartido por celda × estrato. A ciegas del medio: no hay nombre, URL
               ni sección, y las menciones a un medio en el contexto se enmascaran.
    evaluar    kappa de Cohen (sesgo, tipo, dirección, intensidad), acuerdo por
               categoría, tasa de «sesgado» por medio × gobierno ponderada por estrato
               (IC de Wilson con n efectivo de Kish) y silver_standard.csv.
    adjudicar  adjudicacion.xlsx con los desacuerdos de las dobles; se vuelve a
               correr `evaluar --adjudicacion …` cuando esté lleno.

Uso (en la imagen duque-petro-lda:local, desde entrega3/):
    SCRIPT=silver.py ./run.sh - muestra
    SCRIPT=silver.py ./run.sh - dividir
    SCRIPT=silver.py ./run.sh - evaluar --personas resultados_publico/silver/planilla_silver_persona_1.xlsx \
                                                   resultados_publico/silver/planilla_silver_persona_2.xlsx
    SCRIPT=silver.py ./run.sh - adjudicar --personas …   (y luego evaluar … --adjudicacion …/adjudicacion.xlsx)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from calibracion import MEDIA, NOMBRES, cohen_kappa
from core import normalize

HERE = Path(__file__).resolve().parent
DATA = HERE / "resultados_publico"
OUT = DATA / "silver"
GOBIERNOS = {"duque": "Duque", "petro": "Petro"}
RCN, RCN_DESDE = "noticias_rcn", pd.Timestamp("2020-09-01")  # ver resultados_publico/lexico/LEEME.md
TEMAS_EXCLUIDOS = {14}  # fútbol residual: no es asunto público
SECCIONES_EXCLUIDAS = {"opinion", "humor"}
MIN_PALABRAS = 5

# ── esquema (sin comas: en la validación de Excel la coma separa opciones) ───
SESGADO = ["Sí", "No", "No se puede saber"]
TIPOS = ["Lenguaje cargado", "Opinión como hecho", "Atribución selectiva", "Sensacionalismo",
         "Encuadre parcial / omisión de contexto", "Otro"]
DIRECCION = ["Favorable", "Desfavorable", "Neutra / no aplica"]
INTENSIDAD = ["1 leve", "2 moderada", "3 fuerte"]
CAMPOS = ["nombre", "¿sesgado?", "tipo principal", "dirección", "intensidad", "comentario"]
LISTAS = {"¿sesgado?": SESGADO, "tipo principal": TIPOS, "dirección": DIRECCION, "intensidad": INTENSIDAD}

# ── estratos ─────────────────────────────────────────────────────────────────
# E_ = con evento (se muestran los titulares de los otros medios sobre el mismo hecho);
# S_ = sin evento. Prioridad entre criterios: léxico > divergente > resto.
ESTRATOS = ["E_lexico", "E_divergente", "E_resto", "S_lexico", "S_resto"]
PLAN = {"E_lexico": 7, "E_divergente": 5, "E_resto": 6, "S_lexico": 5, "S_resto": 7}  # 30 por celda; 13 al azar
CUANTIL_DIVERGENTE = 0.15
RESTO = {"E": "E_resto", "S": "S_resto"}

# Menciones a un medio (marca, dominio, programa). «el tiempo» y «la república» son
# ambiguos («el tiempo se agota», «Banco de la República»): sólo cuentan en las
# construcciones que nombran al periódico («editorial de el tiempo», «diario la república»).
MARCA = re.compile(
    r"\b(?:noticias |canal |emisora |mananas )?(?:blu(?: radio)?|bluradio|caracol(?:tv|radio| radio| television)?|rcn"
    r"|noticiasrcn|noticiascaracol)\b|\beltiempo\b|\blarepublica\b"
    r"|\b(?:de|a|diario|periodico|editorial|casa editorial|foro|unidad investigativa) el tiempo\b"
    r"|\bel tiempo com\b|\b(?:diario|periodico) la republica\b|\bla republica co(?:m)?\b"
    r"|\b(?:con|a) la republica\b(?! (?:de|del|bolivariana|dominicana|checa|popular|federal|argentina|islamica|"
    r"democratica|francesa|centroafricana|del congo))", re.I)
DOMINIOS = ["eltiempo.com", "bluradio.com", "noticiasrcn.com", "noticiascaracol.com", "larepublica.co"]  # referencia

# Léxico de candidatos (enriquecimiento del muestreo, NO un clasificador). Formas
# normalizadas sin tildes. Lista propia y breve; se puede armonizar después con
# lexico_carga.yaml. Una coincidencia sólo hace al titular candidato.
CARGA = {
    "descalificacion": [
        "fracaso", "fracasa", "fracasado", "desastre", "desastroso", "caos", "caotico", "verguenza", "vergonzoso",
        "bochorno", "bochornoso", "papelon", "ridiculo", "nefasto", "absurdo", "irresponsable", "irresponsabilidad",
        "improvisacion", "improvisado", "incompetente", "inepto", "despilfarro", "derroche", "mentira", "mentiras",
        "mintio", "miente", "cortina de humo", "circo", "mermelada", "montaje", "persecucion politica",
        "golpe blando", "chambonada", "metida de pata", "torpeza", "desgreno"],
    "estigmatizacion": [
        "populista", "populismo", "dictador", "dictadura", "tirano", "castrochavismo", "castrochavista",
        "comunista", "neoliberal", "mamerto", "paraco", "guerrillero", "terrorista", "narcogobierno"],
    "dramatizacion": [
        "escandalo", "escandaloso", "polemica", "polemico", "polemicos", "insolito", "increible", "impactante",
        "brutal", "terrible", "estremecedor", "aterrador", "escalofriante", "indignante", "indignacion",
        "alarmante", "estalla", "estallo", "revienta", "terremoto politico", "tormenta politica", "lluvia de criticas",
        "ola de criticas", "duro golpe", "jalon de orejas", "regano", "se despacho", "arremete", "arremetio",
        "embiste", "dardo", "dardos", "pulla", "humillacion", "humillante", "contra las cuerdas", "en jaque",
        "cuerda floja", "salpica", "se hunde", "naufraga", "debacle", "catastrofe", "catastrofico"],
    "exaltacion": [
        "historico", "historica", "exito", "exitoso", "exitosa", "contundente", "rotundo", "magistral",
        "acierto", "por fin", "salvavidas", "espaldarazo", "gran logro", "heroe", "heroica", "heroico"],
}
# Usos descriptivos que no son carga: nombres propios y términos técnicos u oficiales.
NO_CARGA = re.compile(r"\bpacto historico\b|\bcentro historico\b|\b(?:maximo|minimo|record|nivel) historico\b"
                      r"|\b(?:ataque|atentado|acto|grupo|organizacion|amenaza) terrorista\b")
_PAT_CARGA = re.compile(r"\b(?:" + "|".join(sorted({re.escape(t) for ts in CARGA.values() for t in ts},
                                                    key=len, reverse=True)) + r")\b")


def menciona_medio(texto: str) -> bool:
    return bool(MARCA.search(normalize(texto)))


def enmascarar_medio(texto: str) -> str:
    """Reemplaza las menciones a un medio por «[medio]» (sobre el titular tal cual:
    los titulares reconstruidos no tienen tildes, así que basta ignorar mayúsculas)."""
    return MARCA.sub("[medio]", texto)


def terminos_carga(texto_norm: str) -> list[str]:
    return sorted(set(_PAT_CARGA.findall(NO_CARGA.sub(" ", texto_norm))))


def personaliza(texto_norm: str, gobierno: str) -> bool:
    """«Gobierno Petro/Duque» (con el apellido del presidente de ESE gobierno), con la
    misma expresión regular que lexico.formas_nombrar."""
    from lexico import formas_nombrar

    return formas_nombrar(texto_norm, gobierno)["gobierno_apellido"]


def asignar_estrato(en_evento: pd.Series, lexico: pd.Series, divergente: pd.Series) -> pd.Series:
    bloque = np.where(en_evento, "E", "S")
    criterio = np.where(lexico, "lexico", np.where(divergente & en_evento, "divergente", "resto"))
    return pd.Series([f"{b}_{c}" for b, c in zip(bloque, criterio)], index=en_evento.index)


def asignacion(N: dict[str, int], plan: dict[str, int] = PLAN) -> dict[str, int]:
    """Tamaño por estrato dentro de una celda: el del plan, sin pasar de la población;
    lo que falta se pasa al resto del mismo bloque (E/S) y, si tampoco alcanza, al otro."""
    n = {h: min(plan[h], N.get(h, 0)) for h in plan}
    falta = sum(plan.values()) - sum(n.values())
    for h in [RESTO[b] for b in ("E", "S")] * 2:  # primero los dos restos, luego otra vuelta
        if falta <= 0:
            break
        extra = min(falta, N.get(h, 0) - n[h])
        n[h] += extra
        falta -= extra
    return n


# ── muestra ──────────────────────────────────────────────────────────────────


def poblacion(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Titulares elegibles y por qué se excluyen los demás. `frame` trae
    article_id, source_id, government_id, title, published_date, section, topic."""
    f = frame.copy()
    f["texto"] = f["title"].map(normalize)
    fecha = pd.to_datetime(f["published_date"])
    motivos = {
        "rcn_duque_antes_2020_09": (f["source_id"] == RCN) & (f["government_id"] == "duque") & (fecha < RCN_DESDE),
        "tema_futbol_residual": f["topic"].isin(TEMAS_EXCLUIDOS),
        "opinion_o_humor": f["section"].isin(SECCIONES_EXCLUIDAS)
        | f["texto"].str.contains(r"\b(?:opinion|columna|editorial)\b"),
        "menciona_un_medio": f["title"].map(menciona_medio),
        "menos_de_5_palabras": f["texto"].str.split().str.len() < MIN_PALABRAS,
    }
    fuera = np.zeros(len(f), dtype=bool)
    excl = {}
    for k, m in motivos.items():  # se cuenta cada motivo sobre lo que queda
        m = m.to_numpy() & ~fuera
        excl[k] = int(m.sum())
        fuera |= m
    f = f[~fuera]
    dup = f.duplicated(["source_id", "texto"])
    excl["duplicado_en_el_medio"] = int(dup.sum())
    return f[~dup].copy(), excl


def contexto_eventos(ev: pd.DataFrame, seed: int) -> dict[int, list[str]]:
    """Por evento: titulares núcleo de cada medio (uno por medio), con las menciones
    a medios enmascaradas, en orden aleatorio."""
    rng = np.random.default_rng(seed)
    nucleo = ev[~ev["es_seguimiento"]]
    out = {}
    for e, g in nucleo.groupby("event_id"):
        g = g.iloc[rng.permutation(len(g))]
        out[int(e)] = list(zip(g["source_id"], g["title"].map(enmascarar_medio)))
    return out


def sim_otros(ev: pd.DataFrame, emb: np.ndarray, row_of: pd.Series) -> pd.Series:
    """Coseno entre cada titular de un evento y el centroide de los titulares núcleo de
    los OTROS medios del mismo evento. Bajo = el titular se aparta de cómo lo contaron los demás."""
    sims = {}
    for _, g in ev.groupby("event_id"):
        nuc = g[~g["es_seguimiento"]]
        for r in g.itertuples():
            otros = nuc[nuc["source_id"] != r.source_id]
            if otros.empty:
                continue
            c = emb[row_of[otros["article_id"]].to_numpy()].mean(0)
            c /= np.linalg.norm(c) or 1
            sims[r.article_id] = float(emb[row_of[r.article_id]] @ c)
    return pd.Series(sims, name="sim_otros")


def fecha_visible(fecha, precision: str) -> str:
    return str(fecha)[:10] if precision == "day" else str(fecha)[:7]


def muestrear(pop: pd.DataFrame, seed: int, plan: dict[str, int] = PLAN) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Muestra estratificada por celda (medio × gobierno) y estrato. Devuelve la muestra
    y la tabla de población/muestra por estrato (N_h, n_h)."""
    partes, tabla = [], []
    for (m, g), cel in pop.groupby(["source_id", "government_id"]):
        N = cel["estrato"].value_counts().to_dict()
        n = asignacion(N, plan)
        for h in ESTRATOS:
            sub = cel[cel["estrato"] == h]
            take = sub.sample(n[h], random_state=seed) if n[h] else sub.iloc[:0]
            partes.append(take)
            tabla.append({"source_id": m, "government_id": g, "estrato": h, "N_h": int(N.get(h, 0)), "n_h": n[h]})
    return pd.concat(partes), pd.DataFrame(tabla)


def elegir_dobles(sample: pd.DataFrame, por_celda: int, seed: int) -> pd.Index:
    """`por_celda` titulares dobles en cada celda: primero uno de cada estrato presente
    (para que haya candidatos y no candidatos en las dobles), luego al azar."""
    rng = np.random.default_rng(seed)
    elegidos = []
    for _, cel in sample.groupby(["source_id", "government_id"]):
        cel = cel.iloc[rng.permutation(len(cel))]
        prim = cel.drop_duplicates("estrato").index[:por_celda]
        resto = cel.index.difference(prim)
        extra = rng.choice(resto, size=min(por_celda - len(prim), len(resto)), replace=False)
        elegidos += list(prim) + list(extra)
    return pd.Index(elegidos)


def stage_muestra(args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(DATA / "prepared.parquet", columns=[
        "article_id", "url", "source_id", "government_id", "title", "published_date", "date_precision", "section"])
    topics = pd.read_parquet(DATA / "bertopic" / "document_topics.parquet", columns=["article_id", "dominant_topic"])
    frame = frame.merge(topics.rename(columns={"dominant_topic": "topic"}), on="article_id", how="left")
    row_of = pd.Series(np.arange(len(frame)), index=frame["article_id"])
    emb = np.load(DATA / "bertopic" / "embeddings.npy", mmap_mode="r")
    ev = pd.read_parquet(DATA / "eventos" / "eventos.parquet")

    pop, excl = poblacion(frame)
    logging.info("Población elegible: %s titulares; exclusiones %s", len(pop), excl)
    ev_of = ev.set_index("article_id")["event_id"]
    pop["event_id"] = pop["article_id"].map(ev_of)
    pop["en_evento"] = pop["event_id"].notna()
    so = sim_otros(ev[ev["event_id"].isin(pop["event_id"].dropna())], np.asarray(emb), row_of)
    pop["sim_otros"] = pop["article_id"].map(so)
    pop["en_evento"] &= pop["sim_otros"].notna()
    pop["terminos_carga"] = pop["texto"].map(lambda t: " | ".join(terminos_carga(t)))
    pop["personaliza"] = [personaliza(t, g) for t, g in zip(pop["texto"], pop["government_id"])]
    pop["lexico"] = (pop["terminos_carga"] != "") | pop["personaliza"]
    corte = pop[pop["en_evento"]].groupby(["source_id", "government_id"])["sim_otros"].quantile(CUANTIL_DIVERGENTE)
    pop["corte_divergente"] = [corte.get((m, g), np.nan) for m, g in zip(pop["source_id"], pop["government_id"])]
    pop["divergente"] = pop["en_evento"] & (pop["sim_otros"] <= pop["corte_divergente"])
    pop["estrato"] = asignar_estrato(pop["en_evento"], pop["lexico"], pop["divergente"])

    sample, tabla = muestrear(pop, args.seed)
    dobles = elegir_dobles(sample, args.dobles_por_celda, args.seed)
    sample["doble"] = np.where(sample.index.isin(dobles), "Sí", "No")
    sample = sample.sample(frac=1, random_state=args.seed).reset_index(drop=True)
    sample["id"] = [f"T{i:03d}" for i in range(1, len(sample) + 1)]  # el id no codifica medio ni estrato

    ctx = contexto_eventos(ev[ev["event_id"].isin(sample["event_id"].dropna())], args.seed)
    rows, key = [], []
    for r in sample.itertuples():
        otros = [t for s, t in ctx.get(int(r.event_id), []) if s != r.source_id] if r.en_evento else []
        rows.append({
            "id": r.id, "doble": r.doble, "fecha": fecha_visible(r.published_date, r.date_precision),
            "gobierno": GOBIERNOS[r.government_id], "titular": r.title,
            "contexto": "\n".join(f"• {t}" for t in otros[:4]) if otros else "(sin titulares de otros medios)",
            "n_otros": len(otros),
        })
        N_h = int(tabla.set_index(["source_id", "government_id", "estrato"]).loc[
            (r.source_id, r.government_id, r.estrato), "N_h"])
        n_h = int(tabla.set_index(["source_id", "government_id", "estrato"]).loc[
            (r.source_id, r.government_id, r.estrato), "n_h"])
        key.append({
            "id": r.id, "article_id": int(r.article_id), "source_id": r.source_id, "medio": NOMBRES[r.source_id],
            "government_id": r.government_id, "url": r.url, "section": r.section, "topic": r.topic,
            "estrato": r.estrato, "N_h": N_h, "n_h": n_h, "peso": N_h / n_h,
            "event_id": None if pd.isna(r.event_id) else int(r.event_id),
            "sim_otros": None if pd.isna(r.sim_otros) else round(r.sim_otros, 4),
            "terminos_carga": r.terminos_carga, "personaliza": bool(r.personaliza),
            "divergente": bool(r.divergente),
        })
    muestra = pd.DataFrame(rows)
    muestra.to_csv(OUT / "muestra.csv", index=False)
    pd.DataFrame(key).to_csv(OUT / "clave_no_abrir.csv", index=False)
    tabla.to_csv(OUT / "poblacion_estratos.csv", index=False)
    cel = pop.groupby(["source_id", "government_id"]).agg(
        titulares=("article_id", "size"), en_evento=("en_evento", "mean"), lexico=("lexico", "mean"),
        personaliza=("personaliza", "mean"), carga=("terminos_carga", lambda s: (s != "").mean()))
    resumen = {
        "semilla": args.seed, "titulares": len(muestra), "dobles": int((muestra["doble"] == "Sí").sum()),
        "por_persona": int((muestra["doble"] == "Sí").sum() + (muestra["doble"] == "No").sum() / 2),
        "plan_por_celda": PLAN, "cuantil_divergente": CUANTIL_DIVERGENTE, "rcn_duque_desde": str(RCN_DESDE.date()),
        "exclusiones": excl, "poblacion_elegible": int(len(pop)),
        "poblacion_por_celda": {f"{m}|{g}": {k: (int(v) if k == "titulares" else round(float(v), 4))
                                             for k, v in r.items()} for (m, g), r in cel.iterrows()},
        "muestra_por_estrato": tabla.groupby("estrato")["n_h"].sum().to_dict(),
        "muestra_con_contexto": int((muestra["n_otros"] > 0).sum()),
        "terminos_carga": CARGA,
    }
    json.dump(resumen, open(OUT / "muestra.json", "w"), ensure_ascii=False, indent=2, default=int)
    logging.info("Muestra: %s titulares (%s dobles); por estrato %s", len(muestra), resumen["dobles"],
                 resumen["muestra_por_estrato"])


# ── planillas ────────────────────────────────────────────────────────────────


def split_for_two(muestra: pd.DataFrame, key: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Como calibracion.split_for_two, por celda × estrato: las dobles en las dos
    planillas; las simples alternadas para que cada persona tenga de todo."""
    merged = muestra.merge(key[["id", "source_id", "government_id", "estrato"]], on="id")
    dobles = merged[merged["doble"] == "Sí"]
    simples = merged[merged["doble"] != "Sí"].sample(frac=1, random_state=seed).sort_values(
        ["source_id", "government_id", "estrato"], kind="stable")
    simples = simples.assign(_k=np.arange(len(simples)) % 2)
    order = lambda d: d.sample(frac=1, random_state=seed)[muestra.columns].reset_index(drop=True)  # noqa: E731
    return (order(pd.concat([dobles, simples[simples["_k"] == 0]])),
            order(pd.concat([dobles, simples[simples["_k"] == 1]])))


INSTRUCCIONES_DEF = [
    ("Lenguaje cargado", "palabras valorativas, emotivas o estigmatizantes sobre un actor o un hecho cuando existe "
     "una forma neutra de decir lo mismo. Ej.: «Ministro se despachó contra los jueces» (neutro: «Ministro criticó "
     "a los jueces»); «El fracaso de la reforma» cuando sólo se aplazó un debate. No cuenta: términos técnicos o "
     "jurídicos aunque suenen fuertes («masacre» para tres o más asesinatos; «captura»)."),
    ("Opinión como hecho", "el titular afirma como hecho una valoración, predicción o interpretación sin decir quién "
     "la sostiene. Ej.: «La reforma acabará con el sistema de salud» (sin fuente). Si está atribuida («Gremios "
     "advierten que la reforma…») no es esta categoría."),
    ("Atribución selectiva", "en un asunto disputado se da voz sólo a una parte, se presenta una fuente marginal como "
     "representativa o se usan verbos que juzgan la credibilidad («admitió», «confesó», «se inventó» frente a "
     "«dijo»). El contexto ayuda: ¿los otros medios citan a otra fuente o a las dos partes?"),
    ("Sensacionalismo", "exagera la gravedad, la novedad o la emoción del hecho: alarmismo, dramatización o gancho "
     "(«caos total», «terremoto político», «lo que nadie le contó»). Se distingue del lenguaje cargado porque "
     "infla el hecho más que valorar a un actor."),
    ("Encuadre parcial / omisión de contexto", "destaca un aspecto que empuja una lectura y omite un dato central "
     "que cambia la interpretación y que los otros medios sí ponen. Ej.: «Gobierno sube impuesto a la gasolina» "
     "cuando los demás titulan que es un ajuste mensual ya previsto. Requiere contexto: sin otros titulares, úselo "
     "sólo si conoce el hecho."),
    ("Otro", "sesgo que no encaja en las anteriores (p. ej. ironía o sarcasmo); explíquelo en el comentario."),
]
GUIA = [
    "1. Lea el titular y después los de otros medios sobre el mismo hecho (columna «otros medios»). No son la "
    "verdad: sirven para ver qué otras formas había de contarlo. Ojo: el emparejamiento acierta en ~4 de cada 5 "
    "casos; si el contexto habla de otro hecho (p. ej. otro actor u otro lugar), ignórelo y juzgue el titular solo.",
    "2. Pregúntese: ¿la redacción empuja a valorar el hecho o a un actor más allá de lo que informa? Si no, «No».",
    "3. Juzgue cómo se cuenta, no el hecho: una noticia mala para el gobierno contada con neutralidad es «No». "
    "No importa si usted está de acuerdo.",
    "4. Diferencias de estilo o formato no son sesgo por sí solas: preguntas, «en vivo», «claves», nombre completo o "
    "sólo apellido, «Gobierno Petro» frente a «el Gobierno». Sí lo son si añaden una valoración.",
    "5. «No se puede saber»: el titular está truncado o no se entiende, o el sesgo depende de un dato que no "
    "conoce. Que no haya otros medios no basta por sí solo para elegirla.",
    "6. Si es «Sí», elija UN tipo (el más visible), la dirección y la intensidad. Si duda entre dos tipos, anote el "
    "otro en el comentario.",
    "7. Dirección, respecto al gobierno de turno (columna «gobierno»): «Favorable» si el sesgo deja mejor parado al "
    "gobierno, al presidente o a sus ministros (o peor a quien se le opone en ese asunto); «Desfavorable» lo "
    "contrario; «Neutra / no aplica» si el sesgo no toca al gobierno (p. ej. sensacionalismo sobre un crimen).",
    "8. Intensidad: «1 leve» una palabra o un matiz que otra persona podría no ver; «2 moderada» claro pero dentro "
    "de lo habitual en titulares; «3 fuerte» el titular es sobre todo una valoración o una exageración evidente.",
    "9. No intente adivinar el medio y no busque el titular en internet: la anotación es a ciegas a propósito.",
]


def build_workbook(muestra: pd.DataFrame, path: Path, persona: int) -> None:
    """Planilla de una persona: Instrucciones, Anotación y Progreso (fórmulas)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    base, bold = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
    title = Font(name="Arial", size=14, bold=True)
    head_fill = PatternFill("solid", fgColor="D9D9D9")
    input_fill = PatternFill("solid", fgColor="FFFF00")
    double_fill = PatternFill("solid", fgColor="DDEBF7")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical="top")
    n, n_dobles = len(muestra), int((muestra["doble"] == "Sí").sum())
    minutos = round(n * 40 / 60 / 5) * 5

    # ── Instrucciones
    ws = wb.active
    ws.title = "Instrucciones"
    lines = [
        ("Silver standard de titulares sesgados", title), ("", base),
        ("Para qué sirve", bold),
        ("Cada fila es un titular de prensa colombiana (2018–2026). Usted decide si la forma de titular está sesgada "
         "y, si lo está, de qué manera. Las respuestas forman un conjunto etiquetado para validar listas de palabras "
         "cargadas y entrenar o evaluar un clasificador. No se mide la veracidad del titular.", base),
        ("Los titulares vienen reconstruidos desde la dirección web: sin tildes, cifras ni puntuación, y a veces "
         "cortados. No se muestra el medio ni el enlace para no influir en su juicio; las menciones a un medio "
         "dentro del texto aparecen como «[medio]».", base),
        ("", base),
        ("Qué hacer", bold),
        (f"Planilla de la persona {persona}: {n} titulares (unos {minutos} minutos a ~40 s cada uno; mejor en dos "
         f"sesiones). Las {n_dobles} filas «doble = Sí» (en azul) están también en la planilla de su compañero o "
         "compañera: anótelas sin consultar, porque sirven para medir el acuerdo.", base),
        ("1. En la hoja «Anotación», escriba su nombre en la primera fila de «nombre».", base),
        ("2. En cada fila elija «¿sesgado?» con la lista desplegable. Si es «Sí», llene también tipo principal, "
         "dirección e intensidad. Si es «No» o «No se puede saber», deje esas tres vacías.", base),
        ("3. La columna «control» avisa si falta o sobra algo. Sólo edite las celdas amarillas.", base),
        ("4. No abra clave_no_abrir.csv: dice el medio de cada titular.", base),
        ("", base),
        ("Tipos de sesgo (elija el principal)", bold),
        *[(f"{k}: {v}", base) for k, v in INSTRUCCIONES_DEF],
        ("", base),
        ("Guía de decisión", bold),
        *[(g, base) for g in GUIA],
        ("", base),
        ("Leyenda", bold),
        ("Celdas amarillas: las que usted edita. Filas azules: titular doble (también lo anota la otra persona). "
         "Todo lo demás es fijo.", base),
        ("", base),
        ("Ejemplo de fila anotada (inventado; no forma parte de la muestra)", bold),
    ]
    for r, (text, font) in enumerate(lines, start=1):
        c = ws.cell(row=r, column=1, value=text)
        c.font, c.alignment = font, Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 120
    example = [
        ("id · doble", "T000 · No", False), ("fecha · gobierno", "2023-03-15 · Petro", False),
        ("titular", "Ministro se despacho contra los jueces que frenaron la reforma", False),
        ("otros medios sobre el mismo hecho", "• Ministro critico decision de juzgado sobre la reforma", False),
        ("nombre", "Ana Pérez", True), ("¿sesgado?", "Sí", True), ("tipo principal", "Lenguaje cargado", True),
        ("dirección", "Desfavorable", True), ("intensidad", "2 moderada", True),
        ("comentario", "«se despachó» frente a «criticó»; deja mal parado al ministro", True),
    ]
    for k, (field, value, editable) in enumerate(example, start=len(lines) + 1):
        c = ws.cell(row=k, column=1, value=f"{field}:  {value}")
        c.font, c.border, c.alignment = base, border, Alignment(wrap_text=True, vertical="top")
        if editable:
            c.fill = input_fill

    # ── Anotación
    an = wb.create_sheet("Anotación")
    fixed = [("id", 7), ("doble", 7), ("fecha", 11), ("gobierno", 9), ("titular", 48),
             ("otros medios sobre el mismo hecho", 52)]
    editable = [("nombre", 14), ("¿sesgado?", 16), ("tipo principal", 24), ("dirección", 17), ("intensidad", 12),
                ("comentario", 28)]
    headers = fixed + editable + [("control", 22)]
    for j, (h, w) in enumerate(headers, start=1):
        c = an.cell(row=1, column=j, value=h)
        c.font, c.fill, c.border = bold, head_fill, border
        c.alignment = Alignment(wrap_text=True, vertical="center")
        an.column_dimensions[c.column_letter].width = w
    an.freeze_panes = "E2"
    an.row_dimensions[1].height = 30
    col = {h: an.cell(row=1, column=j).column_letter for j, (h, _) in enumerate(headers, start=1)}
    for campo, opciones in LISTAS.items():
        dv = DataValidation(type="list", formula1='"' + ",".join(opciones) + '"', allow_blank=True,
                            showErrorMessage=True, errorTitle="Opción no válida", error="Elija una opción de la lista.")
        an.add_data_validation(dv)
        dv.add(f"{col[campo]}2:{col[campo]}{n + 1}")
    s, t, d, i = col["¿sesgado?"], col["tipo principal"], col["dirección"], col["intensidad"]
    for k, r in enumerate(muestra.itertuples(), start=2):
        values = [r.id, r.doble, r.fecha, r.gobierno, r.titular, r.contexto]
        for j, v in enumerate(values, start=1):
            c = an.cell(row=k, column=j, value=v)
            c.font, c.border, c.alignment = base, border, wrap
            if r.doble == "Sí":
                c.fill = double_fill
        for j in range(len(fixed) + 1, len(fixed) + len(editable) + 1):
            c = an.cell(row=k, column=j)
            c.font, c.border, c.alignment, c.fill = base, border, wrap, input_fill
        ctrl = (f'=IF({s}{k}="","",IF({s}{k}="Sí",IF(OR({t}{k}="",{d}{k}="",{i}{k}=""),'
                f'"Falta tipo/dirección/intensidad",""),IF(OR({t}{k}<>"",{d}{k}<>"",{i}{k}<>""),'
                f'"Sobra tipo/dirección/intensidad","")))')
        c = an.cell(row=k, column=len(headers), value=ctrl)
        c.font, c.border, c.alignment = Font(name="Arial", size=10, color="C00000"), border, wrap
        lineas = max(len(str(r.titular)) / 45, sum(1 + len(x) / 50 for x in str(r.contexto).split("\n")))
        an.row_dimensions[k].height = max(28, 13 * int(np.ceil(lineas)))
    last = n + 1

    # ── Progreso
    pg = wb.create_sheet("Progreso")
    pg["A1"], pg["A1"].font = "Progreso de la anotación", title
    rng = lambda c: f"'Anotación'!{c}2:{c}{last}"  # noqa: E731
    rows = [
        ("Titulares en esta planilla", f"=COUNTA({rng('A')})"),
        ("Titulares dobles", f"=COUNTIF({rng('B')},\"Sí\")"),
        ("Anotados («¿sesgado?» lleno)", f"=COUNTA({rng(s)})"),
        ("% anotado", "=IFERROR(B5/B3,0)"),
        ("Filas con aviso en «control»", f"=COUNTIF({rng(col['control'])},\"?*\")"),
    ]
    k = 3
    for label, formula in rows:
        pg.cell(row=k, column=1, value=label).font = base
        c = pg.cell(row=k, column=2, value=formula)
        c.font = base
        if label.startswith("%"):
            c.number_format = "0.0%"
        k += 1
    for campo, opciones in LISTAS.items():
        k += 1
        pg.cell(row=k, column=1, value=f"Respuestas · {campo}").font = bold
        for o in opciones:
            k += 1
            pg.cell(row=k, column=1, value=o).font = base
            pg.cell(row=k, column=2, value=f"=COUNTIF({rng(col[campo])},A{k})").font = base
    pg.column_dimensions["A"].width = 40
    pg.column_dimensions["B"].width = 12
    wb.save(path)
    logging.info("Planilla: %s (%s titulares, %s dobles)", path, n, n_dobles)


def stage_dividir(args) -> None:
    muestra = pd.read_csv(OUT / "muestra.csv", keep_default_na=False)
    key = pd.read_csv(OUT / "clave_no_abrir.csv")
    for k, part in enumerate(split_for_two(muestra, key, args.seed), start=1):
        build_workbook(part, OUT / f"planilla_silver_persona_{k}.xlsx", persona=k)


# ── evaluar ──────────────────────────────────────────────────────────────────

RESP = ["¿sesgado?", "tipo principal", "dirección", "intensidad", "comentario", "nombre"]


def leer_planilla(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Anotación", dtype=str)
    df = df.rename(columns={c: c.strip() for c in df.columns})
    for c in RESP:
        df[c] = df[c].where(df[c].notna(), None).map(lambda x: x.strip() if isinstance(x, str) else x)
        df[c] = df[c].replace("", None)
    return df[["id", "doble"] + RESP]


def combinar(sheets: list[pd.DataFrame]) -> pd.DataFrame:
    """Una fila por titular con las respuestas de cada persona en columnas «p1 · …» y
    «p2 · …» (vacías si esa persona no lo tenía)."""
    out = None
    for k, sh in enumerate(sheets, start=1):
        sh = sh.rename(columns={c: f"p{k} · {c}" for c in RESP})
        out = sh if out is None else out.merge(sh, on=["id", "doble"], how="outer")
    return out


def _bin(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else ("Sí" if x == "Sí" else "No/NSPS")


def kappa_ponderada(a: list[int], b: list[int], k: int = 3) -> float:
    """Kappa de Cohen con pesos cuadráticos (para la intensidad ordinal 1–3)."""
    if not a:
        return float("nan")
    o = np.zeros((k, k))
    for x, y in zip(a, b):
        o[x - 1, y - 1] += 1
    o /= o.sum()
    e = np.outer(o.sum(1), o.sum(0))
    w = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)]) / (k - 1) ** 2
    den = (w * e).sum()
    return float(1 - (w * o).sum() / den) if den > 0 else 1.0


def acuerdo_especifico(a: list[str], b: list[str], campo: str) -> list[dict]:
    """Acuerdo específico por categoría: 2·n_kk / (n_k(1) + n_k(2))."""
    rows = []
    for lab in sorted(set(a) | set(b)):
        both = sum(x == lab and y == lab for x, y in zip(a, b))
        tot = a.count(lab) + b.count(lab)
        rows.append({"campo": campo, "categoria": lab, "persona_1": a.count(lab), "persona_2": b.count(lab),
                     "ambas": both, "acuerdo_especifico": 2 * both / tot if tot else np.nan})
    return rows


def acuerdo(df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    d = df.dropna(subset=["p1 · ¿sesgado?", "p2 · ¿sesgado?"])
    a, b = d["p1 · ¿sesgado?"].tolist(), d["p2 · ¿sesgado?"].tolist()
    ab, bb = [_bin(x) for x in a], [_bin(x) for x in b]
    res = {"dobles_anotadas": len(d), "acuerdo_observado_3": float(np.mean([x == y for x, y in zip(a, b)]))
           if len(d) else None,
           "kappa_sesgado_3_clases": cohen_kappa(a, b), "kappa_sesgado_binario": cohen_kappa(ab, bb)}
    sin_nsps = [(x, y) for x, y in zip(a, b) if "No se puede saber" not in (x, y)]
    res["kappa_si_no_sin_nsps"] = cohen_kappa([x for x, _ in sin_nsps], [y for _, y in sin_nsps])
    tabla = acuerdo_especifico(a, b, "¿sesgado?")
    ss = d[(d["p1 · ¿sesgado?"] == "Sí") & (d["p2 · ¿sesgado?"] == "Sí")]
    res["ambas_si"] = len(ss)
    for campo in ["tipo principal", "dirección"]:
        x = ss[f"p1 · {campo}"].fillna("(vacío)").tolist()
        y = ss[f"p2 · {campo}"].fillna("(vacío)").tolist()
        res[f"kappa_{campo.split()[0]}_si_ambas_si"] = cohen_kappa(x, y)
        tabla += acuerdo_especifico(x, y, campo)
    ii = ss.dropna(subset=["p1 · intensidad", "p2 · intensidad"])
    xi = [int(v[0]) for v in ii["p1 · intensidad"]]
    yi = [int(v[0]) for v in ii["p2 · intensidad"]]
    res["kappa_intensidad_ponderada"] = kappa_ponderada(xi, yi)
    res = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in res.items()}
    return res, pd.DataFrame(tabla)


def consolidar(df: pd.DataFrame, adjud: pd.DataFrame | None = None) -> pd.DataFrame:
    """Etiqueta consolidada por titular.

    Simple: la respuesta de la única persona (fuente «una persona»). Doble: si
    coinciden en ¿sesgado? (y, si es «Sí», en tipo y dirección) queda «acuerdo»;
    si no, «Pendiente» hasta adjudicar. Si coinciden en «Sí» pero no en tipo o
    dirección, el «Sí» se mantiene y sólo esos campos quedan pendientes. La
    intensidad de un acuerdo es la media de las dos.
    """
    rows = []
    adj = adjud.set_index("id") if adjud is not None and len(adjud) else None
    for r in df.to_dict("records"):
        s1, s2 = r.get("p1 · ¿sesgado?"), r.get("p2 · ¿sesgado?")
        s1, s2 = (None if pd.isna(s1) else s1), (None if pd.isna(s2) else s2)
        out = {"id": r["id"], "doble": r["doble"], "n_anotaciones": int(s1 is not None) + int(s2 is not None)}
        pick = lambda k, c: r.get(f"p{k} · {c}") if not pd.isna(r.get(f"p{k} · {c}")) else None  # noqa: E731
        if out["n_anotaciones"] == 0:
            out.update(sesgado=None, tipo=None, direccion=None, intensidad=None, fuente="sin anotar")
        elif out["n_anotaciones"] == 1:
            k = 1 if s1 is not None else 2
            out.update(sesgado=pick(k, "¿sesgado?"), tipo=pick(k, "tipo principal"), direccion=pick(k, "dirección"),
                       intensidad=_int(pick(k, "intensidad")), fuente="una persona")
        else:
            out["sesgado"] = s1 if s1 == s2 else "Pendiente"
            if s1 == s2 == "Sí":
                t1, t2 = pick(1, "tipo principal"), pick(2, "tipo principal")
                d1, d2 = pick(1, "dirección"), pick(2, "dirección")
                out["tipo"] = t1 if t1 == t2 else "Pendiente"
                out["direccion"] = d1 if d1 == d2 else "Pendiente"
                iv = [v for v in (_int(pick(1, "intensidad")), _int(pick(2, "intensidad"))) if v is not None]
                out["intensidad"] = float(np.mean(iv)) if iv else None
            else:
                out.update(tipo=None, direccion=None, intensidad=None)
            pend = "Pendiente" in (out["sesgado"], out["tipo"], out["direccion"])
            out["fuente"] = "desacuerdo" if pend else "acuerdo de dos"
        if adj is not None and r["id"] in adj.index:
            a = adj.loc[r["id"]]
            if not pd.isna(a.get("decisión · ¿sesgado?")):
                out["sesgado"] = a["decisión · ¿sesgado?"]
                si = out["sesgado"] == "Sí"
                out["tipo"] = a.get("decisión · tipo principal") if si else None
                out["direccion"] = a.get("decisión · dirección") if si else None
                out["intensidad"] = _int(a.get("decisión · intensidad")) if si else None
                out["fuente"] = "adjudicado"
        rows.append(out)
    res = pd.DataFrame(rows)
    res["sesgado_bin"] = res["sesgado"].map({"Sí": 1, "No": 0})
    return res


def _int(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    m = re.match(r"\s*(\d)", str(v))
    return int(m.group(1)) if m else None


def wilson_p(p: float, n: float, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson con proporción y n no enteros (n efectivo de un diseño ponderado)."""
    if n <= 0:
        return float("nan"), float("nan")
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(max(0.0, c - h)), float(min(1.0, c + h))


def tasa_ponderada(d: pd.DataFrame, poblacion_estratos: pd.DataFrame, por: list[str]) -> pd.DataFrame:
    """Tasa de «sesgado» con pesos de estrato.

    d: titulares con sesgado_bin (0/1; sin «No se puede saber» ni pendientes) y las
    columnas de `por` + estrato. Dentro de cada grupo, p = Σ_h W_h p_h con
    W_h = N_h / Σ N_h sobre los estratos con al menos un titular útil (los vacíos se
    reportan en `estratos_sin_datos` y su población en `cobertura`). IC de Wilson con
    el n efectivo de Kish, (Σ w)² / Σ w², con w = N_h / n_h por titular.
    """
    pe = poblacion_estratos.groupby(por + ["estrato"], as_index=False)["N_h"].sum()
    rows = []
    for grupo, g in d.groupby(por):
        grupo = grupo if isinstance(grupo, tuple) else (grupo,)
        popg = pe.set_index(por).loc[grupo if len(por) > 1 else grupo[0]]
        popg = popg if isinstance(popg, pd.DataFrame) else popg.to_frame().T
        N = popg.groupby("estrato")["N_h"].sum()
        st = g.groupby("estrato")["sesgado_bin"].agg(["sum", "count"])
        st = st[st["count"] > 0]
        Nh = N.reindex(st.index).fillna(0)
        W = Nh / Nh.sum()
        p = float((W * st["sum"] / st["count"]).sum())
        w = (Nh / st["count"]).reindex(g["estrato"]).to_numpy()
        n_eff = float(w.sum() ** 2 / (w ** 2).sum())
        lo, hi = wilson_p(p, n_eff)
        rows.append({**dict(zip(por, grupo)), "n": int(st["count"].sum()), "sesgados": int(st["sum"].sum()),
                     "tasa_sin_ponderar": float(st["sum"].sum() / st["count"].sum()), "tasa_ponderada": p,
                     "n_efectivo": round(n_eff, 1), "ic_bajo": lo, "ic_alto": hi,
                     "cobertura": float(Nh.sum() / N.sum()),
                     "estratos_sin_datos": " ".join(sorted(set(N[N > 0].index) - set(st.index)))})
    return pd.DataFrame(rows)


def _cargar_eval(args):
    key = pd.read_csv(OUT / "clave_no_abrir.csv")
    muestra = pd.read_csv(OUT / "muestra.csv", keep_default_na=False)
    df = combinar([leer_planilla(p) for p in args.personas])
    return key, muestra, df


def stage_evaluar(args) -> None:
    from research_stats import wilson_interval

    key, muestra, df = _cargar_eval(args)
    args.salida.mkdir(parents=True, exist_ok=True)
    adjud = pd.read_excel(args.adjudicacion, sheet_name="Adjudicación", dtype=str) if args.adjudicacion else None
    res, tabla = acuerdo(df)
    cons = consolidar(df, adjud)
    silver = (muestra[["id", "fecha", "gobierno", "titular", "contexto", "n_otros"]]
              .merge(key[["id", "article_id", "source_id", "medio", "government_id", "url", "estrato", "peso",
                          "event_id", "terminos_carga", "personaliza", "divergente"]], on="id")
              .merge(cons.drop(columns=["doble"]), on="id", how="left"))
    silver.to_csv(args.salida / "silver_standard.csv", index=False)
    util = silver.dropna(subset=["sesgado_bin"])
    pe = pd.read_csv(OUT / "poblacion_estratos.csv")
    tasas = pd.concat([
        tasa_ponderada(util, pe, ["source_id", "government_id"]),
        tasa_ponderada(util, pe, ["source_id"]).assign(government_id="ambos"),
        tasa_ponderada(util, pe, ["government_id"]).assign(source_id="todos"),
    ], ignore_index=True)
    tasas.to_csv(args.salida / "tasa_sesgo_medio_gobierno.csv", index=False)
    est = []
    for h, g in util.groupby("estrato"):
        lo, hi = wilson_interval(int(g["sesgado_bin"].sum()), len(g))
        est.append({"estrato": h, "n": len(g), "tasa": g["sesgado_bin"].mean(), "ic_bajo": lo, "ic_alto": hi})
    for crit, m in [("terminos_carga", util["terminos_carga"].fillna("") != ""), ("personaliza", util["personaliza"]),
                    ("divergente", util["divergente"])]:
        g = util[m.astype(bool)]
        if len(g):
            lo, hi = wilson_interval(int(g["sesgado_bin"].sum()), len(g))
            est.append({"estrato": f"criterio:{crit}", "n": len(g), "tasa": g["sesgado_bin"].mean(),
                        "ic_bajo": lo, "ic_alto": hi})
    pd.DataFrame(est).to_csv(args.salida / "tasa_por_estrato.csv", index=False)
    tabla.to_csv(args.salida / "acuerdo_por_categoria.csv", index=False)
    res.update({
        "titulares": int(len(silver)), "anotados": int((silver["n_anotaciones"] > 0).sum()),
        "fuente": silver["fuente"].value_counts().to_dict(),
        "sesgado": silver["sesgado"].value_counts().to_dict(),
        "pendientes_de_adjudicar": int((silver["fuente"] == "desacuerdo").sum()),
        "tipo": silver["tipo"].value_counts().to_dict(), "direccion": silver["direccion"].value_counts().to_dict(),
    })
    json.dump(res, open(args.salida / "evaluacion.json", "w"), ensure_ascii=False, indent=2, default=float)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=float))
    print(tasas.round(3).to_string(index=False))


def stage_adjudicar(args) -> None:
    """Planilla con los desacuerdos de las dobles, para decidir juntos (o una tercera
    persona). Sigue a ciegas del medio. Muestra las dos respuestas sin nombre."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    key, muestra, df = _cargar_eval(args)
    args.salida.mkdir(parents=True, exist_ok=True)
    cons = consolidar(df)
    pend = cons[cons["fuente"] == "desacuerdo"][["id"]].merge(df, on="id").merge(muestra, on=["id", "doble"])
    wb = Workbook()
    base, bold = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
    fill = PatternFill("solid", fgColor="FFFF00")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws = wb.active
    ws.title = "Instrucciones"
    for k, txt in enumerate([
        "Adjudicación de desacuerdos", "",
        f"{len(pend)} titulares dobles en los que las dos respuestas no coinciden (en ¿sesgado?, o en tipo o "
        "dirección cuando las dos dijeron «Sí»).",
        "Discútanlos juntos (o que decida una tercera persona) con las mismas definiciones de la planilla de "
        "anotación y llenen las celdas amarillas. Si tras discutir no hay acuerdo, elijan «No se puede saber».",
        "Las columnas «respuesta A» y «respuesta B» no dicen quién respondió qué, a propósito.",
        "Después: python silver.py evaluar --personas … --adjudicacion resultados_publico/silver/adjudicacion.xlsx",
    ], start=1):
        c = ws.cell(row=k, column=1, value=txt)
        c.font, c.alignment = (Font(name="Arial", size=14, bold=True) if k == 1 else base), Alignment(wrap_text=True)
    ws.column_dimensions["A"].width = 110
    ad = wb.create_sheet("Adjudicación")
    resumen = lambda r, k: " · ".join(str(r[f"p{k} · {c}"]) for c in RESP[:5]  # noqa: E731
                                      if not pd.isna(r[f"p{k} · {c}"]))
    headers = [("id", 7), ("fecha", 11), ("gobierno", 9), ("titular", 45), ("otros medios sobre el mismo hecho", 45),
               ("respuesta A", 32), ("respuesta B", 32), ("decisión · ¿sesgado?", 16),
               ("decisión · tipo principal", 22), ("decisión · dirección", 16), ("decisión · intensidad", 12),
               ("nota", 26)]
    for j, (h, w) in enumerate(headers, start=1):
        c = ad.cell(row=1, column=j, value=h)
        c.font, c.border, c.fill = bold, border, PatternFill("solid", fgColor="D9D9D9")
        c.alignment = Alignment(wrap_text=True)
        ad.column_dimensions[c.column_letter].width = w
    rng = np.random.default_rng(args.seed)
    for k, r in enumerate(pend.to_dict("records"), start=2):
        a, b = (resumen(r, 1), resumen(r, 2)) if rng.random() < 0.5 else (resumen(r, 2), resumen(r, 1))
        for j, v in enumerate([r["id"], r["fecha"], r["gobierno"], r["titular"], r["contexto"], a, b], start=1):
            c = ad.cell(row=k, column=j, value=v)
            c.font, c.border, c.alignment = base, border, Alignment(wrap_text=True, vertical="top")
        for j in range(8, 13):
            c = ad.cell(row=k, column=j)
            c.fill, c.border, c.font = fill, border, base
    for j, opciones in zip(range(8, 12), LISTAS.values()):
        dv = DataValidation(type="list", formula1='"' + ",".join(opciones) + '"', allow_blank=True)
        ad.add_data_validation(dv)
        letter = ad.cell(row=1, column=j).column_letter
        dv.add(f"{letter}2:{letter}{max(2, len(pend) + 1)}")
    ad.freeze_panes = "D2"
    wb.save(args.salida / "adjudicacion.xlsx")
    logging.info("Adjudicación: %s desacuerdos en %s", len(pend), args.salida / "adjudicacion.xlsx")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapa", choices=["muestra", "dividir", "evaluar", "adjudicar"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dobles-por-celda", type=int, default=6, help="Titulares que anotan las dos personas")
    parser.add_argument("--personas", type=Path, nargs="+",
                        default=[OUT / "planilla_silver_persona_1.xlsx", OUT / "planilla_silver_persona_2.xlsx"])
    parser.add_argument("--adjudicacion", type=Path, default=None)
    parser.add_argument("--salida", type=Path, default=OUT, help="Carpeta de resultados de evaluar/adjudicar")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    {"muestra": stage_muestra, "dividir": stage_dividir, "evaluar": stage_evaluar,
     "adjudicar": stage_adjudicar}[args.etapa](args)


if __name__ == "__main__":
    main()
