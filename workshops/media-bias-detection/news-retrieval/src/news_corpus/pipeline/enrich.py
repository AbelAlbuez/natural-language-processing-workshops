"""Deriva campos analizables a partir de la URL.

Los sitemaps históricos entregan URL y poco más. Pero la URL de estos medios no
es opaca: el slug es el titular y el primer segmento del path es la sección.

    https://www.noticiascaracol.com/colombia/senado-de-estados-unidos-logra-acuerdo
                                   └ sección ┘└──────────── titular ─────────────┘

Nada de esto se inventa: se marca con `title_source = slug` para que el análisis
sepa que está leyendo una reconstrucción y no el titular publicado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from news_corpus.db.models import Article, TitleSource

# Colas de identificador que estos CMS pegan al slug. El Tiempo usa '+' como
# separador ('...-del-mundo+articulo+12567802'), no sólo '-' o '_'; sin esto el
# titular derivado arrastra "articulo 12567802" y ensucia cualquier conteo de
# frecuencias — de hecho "articulo" salía como la palabra más común del medio.
_ID_TAIL = re.compile(
    r"[-_+](?:articulo|nota|galeria|video)?[-_+]?\d{4,}$", re.IGNORECASE
)
_EXTENSION = re.compile(r"\.(html?|amp|php)$", re.IGNORECASE)
_LEGACY_PREFIX = re.compile(
    r"^(articulo|articulo-web|web|nota|cms|mam)[-_+](web[-_+])?", re.IGNORECASE
)
# Restos de plantilla del CMS que no son palabras del titular.
_CMS_NOISE = {"articulo", "web", "new", "nota", "interior", "plant", "cms", "mam", "documento"}

# Secciones reales de los medios del corpus. Un primer segmento que no esté
# aquí puede ser parte del slug, así que sólo se acepta lo reconocible.
KNOWN_SECTIONS = {
    "politica", "economia", "colombia", "mundo", "deportes", "cultura",
    "tecnologia", "salud", "justicia", "bogota", "medellin", "cali",
    "opinion", "internacional", "nacional", "sociedad", "vida", "unidad-investigativa",
    "archivo", "entretenimiento", "gente", "ciencia", "medio-ambiente",
    "judicial", "seguridad", "elecciones", "negocios", "finanzas", "empresas",
}


@dataclass
class Derived:
    title: str | None
    section: str | None


def derive_from_url(url: str) -> Derived:
    path = unquote(urlsplit(url).path).strip("/")
    if not path:
        return Derived(title=None, section=None)

    segments = [s for s in path.split("/") if s]
    if not segments:
        return Derived(title=None, section=None)

    section = segments[0].lower() if segments[0].lower() in KNOWN_SECTIONS else None

    slug = segments[-1]
    slug = _EXTENSION.sub("", slug)
    slug = _LEGACY_PREFIX.sub("", slug)
    slug = _ID_TAIL.sub("", slug)

    words = [w for w in re.split(r"[-_+]+", slug) if w]
    # Quitar dígitos sueltos y boilerplate del CMS, conservando el resto.
    words = [w for w in words if not w.isdigit() and w.lower() not in _CMS_NOISE]

    # Un slug que sólo era un identificador (MAM-2880084, CMS-16551020) no da
    # titular: sólo la extracción de contenido podrá recuperarlo.
    if not words:
        return Derived(title=None, section=section)

    text = " ".join(words).strip()
    if len(text) < 8:
        return Derived(title=None, section=section)

    return Derived(title=text[0].upper() + text[1:], section=section)


def enrich_articles(session: Session, *, only_missing: bool = True) -> dict[str, int]:
    """Rellena `title` (desde el slug) y `section` donde falten."""
    stmt = select(Article)
    if only_missing:
        stmt = stmt.where(Article.title.is_(None))

    stats = {"revisados": 0, "titulos": 0, "secciones": 0, "sin_titulo": 0}

    for article in session.scalars(stmt).yield_per(1000):
        stats["revisados"] += 1
        derived = derive_from_url(article.url)

        if derived.title and article.title is None:
            article.title = derived.title
            article.title_source = TitleSource.SLUG
            stats["titulos"] += 1
        elif article.title is None:
            # URLs como /archivo/documento/MAM-2880084: sólo la extracción de
            # contenido podrá darles titular.
            stats["sin_titulo"] += 1

        if derived.section and article.section is None:
            article.section = derived.section
            stats["secciones"] += 1

    return stats
