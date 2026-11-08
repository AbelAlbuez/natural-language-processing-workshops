"""Deriva campos analizables a partir de la URL.

Los sitemaps históricos entregan URL y poco más. Pero la URL de estos medios no
es opaca: el slug es el titular y el primer segmento del path es la sección.

    https://www.noticiascaracol.com/colombia/senado-de-estados-unidos-logra-acuerdo
                                   └ sección ┘└──────────── titular ─────────────┘

Nada de esto se inventa: se marca con `title_source = slug` para que el análisis
sepa que está leyendo una reconstrucción y no el titular publicado.

Además se marca con `non_news_reason` lo que no es una pieza informativa
(emisiones, caricaturas, horóscopos, "precio del dólar hoy"…). No se borra: el
análisis decide si lo filtra. El procedimiento y sus cifras están en
docs/07-tratamiento-del-slug.md.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from news_corpus.db.models import Article, NonNewsReason, TitleSource

# Colas de identificador que estos CMS pegan al slug. El Tiempo usa '+' como
# separador ('...-del-mundo+articulo+12567802'), no sólo '-' o '_'; sin esto el
# titular derivado arrastra "articulo 12567802" y ensucia cualquier conteo de
# frecuencias — de hecho "articulo" salía como la palabra más común del medio.
_ID_TAIL = re.compile(
    r"[-_+](?:articulo|nota|galeria|video)?[-_+]?\d{4,}$", re.IGNORECASE
)
# Blu Radio y Caracol (mismo CMS) cierran el slug con un código de dos letras y
# dos dígitos: '...-tregua-en-gaza-cb20', '...-programa-completo-pr30'. Lo
# llevaban el 58% de las URLs de Blu y el 49% de las de Caracol, y sin quitarlo
# 'rg', 'so', 'cb' salen entre las palabras más frecuentes de esos medios.
# Se limita a esos dominios y a los prefijos observados porque hay colas
# legítimas con la misma forma: 'asteroide-da14', 'mh17', 'ub40', 'bb10'.
_CMS_CODE_HOSTS = ("bluradio.com", "noticiascaracol.com")
# A veces va repetido ('...-rg10-rg10', '...-so35-rg10'): se quitan todos.
_CMS_CODE_TAIL = re.compile(r"(?:-(?:rg|so|cb|pr|rs|ex|cm|ah|si)\d{2})+$", re.IGNORECASE)
_EXTENSION = re.compile(r"\.(html?|amp|php)$", re.IGNORECASE)
_LEGACY_PREFIX = re.compile(
    r"^(articulo|articulo-web|web|nota|cms|mam)[-_+](web[-_+])?", re.IGNORECASE
)
# Restos de plantilla del CMS que no son palabras del titular.
_CMS_NOISE = {"articulo", "web", "new", "nota", "interior", "plant", "cms", "mam", "documento"}

# Secciones reales de los medios del corpus. Sólo se usan cuando la URL tiene un
# único segmento (p. ej. '/politica'): ahí ese segmento podría ser el slug, así
# que sólo se acepta lo reconocible. Con dos o más segmentos el primero nunca es
# el slug y se toma tal cual (ver `_section_from`).
KNOWN_SECTIONS = {
    "politica", "economia", "colombia", "mundo", "deportes", "cultura",
    "tecnologia", "salud", "justicia", "bogota", "medellin", "cali",
    "opinion", "internacional", "nacional", "sociedad", "vida", "unidad-investigativa",
    "archivo", "entretenimiento", "gente", "ciencia", "medio-ambiente",
    "judicial", "seguridad", "elecciones", "negocios", "finanzas", "empresas",
}
# Primeros segmentos que son plantilla del CMS o URLs mal formadas, no secciones
# ('/documento/CMS-…', '/articulo/…', 'don-juanhttps:' en El Tiempo).
_NOT_SECTIONS = {"documento", "articulo", "event", "amp"}

# ── piezas no informativas ───────────────────────────────────────────────────
# Por sección: el medio mismo las clasifica fuera de su flujo de noticias.
# Quedan fuera a propósito, tras revisar muestras: 'videos-eltiempo' y
# 'eltiempoplay' (traen notas de video que sí son noticias: "corte suprema de
# EE. UU. rechaza…") y 'obituarios' de La República (notas sobre la muerte de
# figuras públicas, no avisos pagados).
_NON_NEWS_SECTIONS = {
    "emisiones": NonNewsReason.EMISION,
    "podcast-espanol-el-espectador": NonNewsReason.MULTIMEDIA,
    "contenido-comercial": NonNewsReason.COMERCIAL,
    "contenido-patrocinado": NonNewsReason.COMERCIAL,
    "publicidad-politica-pagada": NonNewsReason.COMERCIAL,
    "apuestas-deportivas": NonNewsReason.COMERCIAL,
    "corporativo": NonNewsReason.COMERCIAL,
    "condolencias": NonNewsReason.OBITUARIO,
    "loterias": NonNewsReason.SERVICIO,
}
# Por slug: se aplican al titular derivado, ya en minúsculas y sin tildes. Son
# los titulares que más se repetían en el corpus (p. ej. "caricatura de rodrigo
# guerreros" 362 veces, "emision p m … de" en RCN).
_NON_NEWS_SLUG = [
    (re.compile(r"^emision\b|\bprograma completo\b|^reviva el capitulo\b"), NonNewsReason.EMISION),
    (re.compile(r"^video (titulares|entretenimiento) de\b"), NonNewsReason.MULTIMEDIA),
    (re.compile(r"^caricaturas? de\b"), NonNewsReason.CARICATURA),
    (re.compile(r"\bhoroscopo\b"), NonNewsReason.SERVICIO),
    # Sólo al inicio: "pico y placa en Bogotá para el lunes…" es el boletín;
    # "cambios y multas en el pico y placa de Medellín" es una noticia.
    (re.compile(r"^(revise |revisa |asi funciona el )?(el )?pico y placa\b"), NonNewsReason.SERVICIO),
    # Resultados de juegos de azar: nombre del juego + resultado/ganador/sorteo,
    # en cualquier orden.
    # Pedir las dos cosas deja fuera "así será el sorteo de la Libertadores" y
    # noticias sobre loterías que no son el boletín de resultados.
    (re.compile(r"(?=.*\b(loterias?|chance|baloto|revancha|miloto|colorloto|chontico|paisita"
                r"|caribena|antioquenita|sinuano|super astro|astro (sol|luna)"
                r"|dorado (manana|tarde|noche))\b)"
                r"(?=.*\b(resultados?|ganador(es|a)?|sorteo)\b)"),
     NonNewsReason.SERVICIO),
    (re.compile(r"\b(precios?|cotizacion) del? (la )?(dolar|oro|petroleo|euro|bitcoin)\b.*\bhoy\b"
                r"|^(dolar|oro) hoy\b"),
     NonNewsReason.INDICADOR),
]


@dataclass
class Derived:
    title: str | None
    section: str | None
    non_news_reason: NonNewsReason | None = None


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _section_from(segments: list[str]) -> str | None:
    # Sin tildes: Caracol y Blu publican a la vez '/politica' y '/política'.
    first = _strip_accents(segments[0].lower())
    if len(segments) == 1:
        return first if first in KNOWN_SECTIONS else None
    if first in _NOT_SECTIONS or first.isdigit() or ":" in first or "." in first:
        return None
    return first


def classify_non_news(section: str | None, title: str | None) -> NonNewsReason | None:
    """Motivo por el que la URL no es una pieza informativa, o None."""
    # La sección de un artículo extraído viene de la página ('Emisiones').
    section = _strip_accents(section.lower()) if section else None
    if section in _NON_NEWS_SECTIONS:
        return _NON_NEWS_SECTIONS[section]
    if title:
        text = _strip_accents(title.lower())
        for pattern, reason in _NON_NEWS_SLUG:
            if pattern.search(text):
                return reason
    return None


def derive_from_url(url: str) -> Derived:
    parts = urlsplit(url)
    path = unquote(parts.path).strip("/")
    if not path:
        return Derived(title=None, section=None)

    segments = [s for s in path.split("/") if s]
    if not segments:
        return Derived(title=None, section=None)

    section = _section_from(segments)

    slug = segments[-1]
    slug = _EXTENSION.sub("", slug)
    slug = _LEGACY_PREFIX.sub("", slug)
    if parts.hostname and parts.hostname.endswith(_CMS_CODE_HOSTS):
        slug = _CMS_CODE_TAIL.sub("", slug)
    slug = _ID_TAIL.sub("", slug)

    words = [w for w in re.split(r"[-_+]+", slug) if w]
    # Quitar dígitos sueltos y boilerplate del CMS, conservando el resto.
    words = [w for w in words if not w.isdigit() and w.lower() not in _CMS_NOISE]

    # Un slug que sólo era un identificador (MAM-2880084, CMS-16551020) no da
    # titular: sólo la extracción de contenido podrá recuperarlo.
    title = None
    text = " ".join(words).strip()
    if words and len(text) >= 8:
        title = text[0].upper() + text[1:]

    return Derived(
        title=title, section=section, non_news_reason=classify_non_news(section, title)
    )


_BATCH = 10_000


def enrich_articles(session: Session, *, only_missing: bool = True) -> dict[str, int]:
    """Rellena `title` (desde el slug), `section` y `non_news_reason`.

    Con `only_missing=False` además vuelve a derivar los títulos que ya venían
    del slug, para que todo el corpus quede con la misma versión de las reglas.
    Los títulos `extracted`/`sitemap` nunca se tocan: son el titular publicado.

    Recorre por lotes de id y actualiza sólo las columnas que cambian: con 1,7 M
    de artículos, cargar entidades ORM completas agota la memoria.
    """
    stats = {
        "revisados": 0, "titulos": 0, "rederivados": 0, "secciones": 0,
        "sin_titulo": 0, "no_noticia": 0,
    }
    cols = (
        Article.id, Article.url, Article.title, Article.title_source,
        Article.section, Article.non_news_reason,
    )
    last_id = 0

    while True:
        stmt = select(*cols).where(Article.id > last_id).order_by(Article.id).limit(_BATCH)
        if only_missing:
            stmt = stmt.where(Article.title.is_(None))
        rows = session.execute(stmt).all()
        if not rows:
            break
        last_id = rows[-1].id

        changes = []
        for row in rows:
            stats["revisados"] += 1
            derived = derive_from_url(row.url)
            change: dict = {}

            if row.title is None:
                if derived.title:
                    change.update(title=derived.title, title_source=TitleSource.SLUG)
                    stats["titulos"] += 1
                else:
                    # URLs como /archivo/documento/MAM-2880084: sólo la
                    # extracción de contenido podrá darles titular.
                    stats["sin_titulo"] += 1
            elif row.title_source == TitleSource.SLUG and derived.title != row.title:
                change.update(
                    title=derived.title,
                    title_source=TitleSource.SLUG if derived.title else None,
                )
                stats["rederivados"] += 1

            if derived.section and row.section is None:
                change["section"] = derived.section
                stats["secciones"] += 1

            # Con un titular extraído, la clasificación se hace sobre él: es el
            # texto que verá el análisis.
            title = change.get("title", row.title)
            reason = classify_non_news(row.section or derived.section, title)
            if reason:
                stats["no_noticia"] += 1
            if reason != row.non_news_reason:
                change["non_news_reason"] = reason

            if change:
                change["id"] = row.id
                changes.append(change)

        if changes:
            # Bulk UPDATE por clave primaria: agrupa por conjunto de columnas.
            by_keys: dict[tuple, list[dict]] = {}
            for c in changes:
                by_keys.setdefault(tuple(sorted(c)), []).append(c)
            for group in by_keys.values():
                session.execute(update(Article), group)

    return stats
