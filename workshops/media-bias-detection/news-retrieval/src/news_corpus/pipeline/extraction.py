"""Lee la página del artículo para obtener el titular real (§15, §19).

El discovery deja 4.852 artículos sin título porque su URL es un identificador
(`/archivo/documento/CMS-16551020`). Esas páginas siguen en línea y sí traen el
titular con tildes, la fecha de publicación y el cuerpo.

Se extrae todo en la misma petición a propósito: volver a rastrear los mismos
sitios más adelante para pedir el cuerpo duplicaría la carga sobre medios que
nos la están dando gratis.

Ganancia secundaria pero importante: `article:published_time` da la fecha real,
lo que sube `date_precision` de `month` a `day` y permite asignar gobierno a
artículos que antes quedaban sin él.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import urllib.robotparser
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from news_corpus.config.catalog import Catalog
from news_corpus.config.settings import get_settings
from news_corpus.db.models import Article, DatePrecision, ExtractionStatus, TitleSource
from news_corpus.utils.http import FetchError, HttpFetcher, NotFound
from news_corpus.utils.logging import get_logger

logger = get_logger(__name__)


# ── parsing ──────────────────────────────────────────────────────────────────

_META = r'<meta[^>]+(?:property|name)=["\']{key}["\'][^>]+content=["\']([^"\']*)["\']'
_META_REV = r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{key}["\']'


def _meta(html: str, key: str) -> str | None:
    for pattern in (_META, _META_REV):
        m = re.search(pattern.format(key=re.escape(key)), html, re.IGNORECASE)
        if m and m.group(1).strip():
            return html_mod.unescape(m.group(1)).strip()
    return None


def _strip_tags(text: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _json_ld(html: str) -> dict:
    """Primer bloque JSON-LD que parezca un artículo."""
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.S | re.I,
    ):
        try:
            data = json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        candidates = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and "@graph" in data:
            candidates = data["@graph"]
        for c in candidates:
            if isinstance(c, dict) and ("headline" in c or "datePublished" in c):
                return c
    return {}


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


# Titulares que no lo son. Algunas páginas de archivo de El Tiempo traen
# og:title, h1, JSON-LD y <title> todos con el mismo texto de navegación
# (verificado en /archivo/documento/MAM-5920374, cuyo og:title es "Síganos").
# No es un fallo del parser: es la página. Registrar eso como titular
# contaminaría cualquier análisis léxico, así que se prefiere no tener título.
_BOILERPLATE_TITLES = {
    "siganos", "suscribase", "suscribete", "inicio", "home", "portada",
    "eltiempo com", "el tiempo", "noticias", "sin titulo", "untitled",
    "pagina no encontrada", "error", "acceso", "login", "menu",
}


def is_boilerplate_title(title: str) -> bool:
    normalizado = re.sub(r"[^a-z0-9 ]+", " ", _fold(title.lower())).strip()
    normalizado = re.sub(r"\s+", " ", normalizado)
    return normalizado in _BOILERPLATE_TITLES


def _fold(text: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


# ── limpieza del cuerpo ──────────────────────────────────────────────────────

# Líneas que son cromo de la página, no texto publicado. Se quitan porque un
# análisis léxico las contaría como vocabulario del medio: "Publicidad" aparece
# una vez por cada slot de anuncio intercalado en el cuerpo de Noticias Caracol,
# de modo que sería uno de los términos más frecuentes de ese medio sin que
# ningún periodista lo haya escrito nunca.
_LINEA_RUIDO = re.compile(
    r"^(?:publicidad|actualizado:.*|s[ií]guenos.*|s[ií]ganos"
    r"|lea (?:tambi[eé]n|adem[aá]s).*|le puede interesar.*"
    r"|[.()\[\]|·—–\-*]+)$",
    re.IGNORECASE,
)


def clean_content(text: str | None) -> str | None:
    """Quita las líneas de interfaz y colapsa los huecos que dejan.

    Sólo elimina líneas completas que coinciden con el patrón: nunca recorta
    dentro de una frase. Un párrafo que *menciona* la publicidad se conserva;
    la línea que sólo dice "Publicidad" no.
    """
    if not text:
        return None
    limpias = [
        linea.rstrip()
        for linea in text.split("\n")
        if not _LINEA_RUIDO.match(linea.strip())
    ]
    resultado = re.sub(r"\n{3,}", "\n\n", "\n".join(limpias)).strip()
    return resultado or None


@dataclass
class Extracted:
    title: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    description: str | None = None
    section: str | None = None
    content: str | None = None


def parse_article(html: str) -> Extracted:
    """Saca los campos del HTML.

    El orden de preferencia del titular no es arbitrario: `<title>` suele traer
    una versión abreviada para la pestaña (se vio "Frustan robo de bebé en Cali"
    donde el titular real era "Policía rescata a bebé robado a una mujer en
    ladera del sur de Cali"), así que queda de último recurso.
    """
    ld = _json_ld(html)

    title = _meta(html, "og:title")
    if not title:
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
        title = _strip_tags(h1.group(1)) if h1 else None
    if not title and isinstance(ld.get("headline"), str):
        title = ld["headline"].strip()
    if not title:
        t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        title = _strip_tags(t.group(1)) if t else None

    if title and is_boilerplate_title(title):
        title = None

    ld_date = ld.get("datePublished")
    published = (
        _parse_date(_meta(html, "article:published_time"))
        or _parse_date(ld_date if isinstance(ld_date, str) else None)
        or _parse_date(_meta(html, "date"))
    )

    author = _meta(html, "article:author") or _meta(html, "author")
    if not author:
        a = ld.get("author")
        if isinstance(a, dict):
            author = a.get("name")
        elif isinstance(a, list) and a and isinstance(a[0], dict):
            author = a[0].get("name")

    content = None
    try:
        import trafilatura

        content = trafilatura.extract(html, include_comments=False, favor_precision=True)
    except Exception as exc:  # el cuerpo es opcional; nunca debe tumbar la extracción
        logger.debug("trafilatura falló", error=str(exc))

    return Extracted(
        title=title or None,
        published_at=published,
        author=author.strip() if author else None,
        description=_meta(html, "og:description") or _meta(html, "description"),
        section=_meta(html, "article:section"),
        content=clean_content(content),
    )


# ── robots.txt ───────────────────────────────────────────────────────────────


class RobotsCache:
    """Comprueba robots.txt una vez por dominio (§19)."""

    def __init__(self, user_agent: str) -> None:
        self._ua = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        host = urlsplit(url).netloc
        if host not in self._cache:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"https://{host}/robots.txt")
            try:
                parser.read()
            except Exception as exc:
                # Sin robots.txt legible se continúa: no se puede afirmar que
                # esté prohibido. Queda registrado.
                logger.warning("robots.txt ilegible", host=host, error=str(exc))
                parser = None
            self._cache[host] = parser

        parser = self._cache[host]
        return True if parser is None else parser.can_fetch(self._ua, url)


# ── ejecución ────────────────────────────────────────────────────────────────


def extract_pending(
    session: Session,
    catalog: Catalog,
    *,
    limit: int = 100,
    source_id: str | None = None,
    only_missing_title: bool = True,
    retry_failed: bool = False,
    commit_every: int = 25,
) -> dict[str, int]:
    """Extrae en tandas cortas, confirmando cada `commit_every` artículos.

    El commit incremental no es un detalle de rendimiento: una tanda de 150
    artículos a 1 req/s mantiene la transacción abierta ~2,5 minutos, y un
    corte de conexión la pierde entera. Pasó de verdad — recrear el contenedor
    de Postgres tumbó la conexión y se perdieron 150 artículos ya descargados.
    Confirmar cada 25 acota esa pérdida y evita repetir peticiones a los medios.
    """
    settings = get_settings()
    fetcher = HttpFetcher("extraction", rate_per_sec=1.0)
    robots = RobotsCache(settings.user_agent)

    stmt = select(Article)
    if retry_failed:
        # Un reintento no se filtra además por "le falta el título": el artículo
        # falló por red, y la mayoría de los que fallan ya tienen un título
        # derivado del slug. Combinar ambos filtros hacía que `--retry` no
        # encontrara nada y los fallos se quedaran sin reintentar en silencio.
        stmt = stmt.where(Article.extraction_status == ExtractionStatus.FAILED)
    else:
        stmt = stmt.where(Article.extraction_status.is_(None))
        if only_missing_title:
            stmt = stmt.where(Article.title.is_(None))
    if source_id:
        stmt = stmt.where(Article.source_id == source_id)
    stmt = stmt.order_by(Article.published_date, Article.id).limit(limit)

    stats = {
        "intentados": 0, "ok": 0, "sin_titulo": 0, "http_error": 0,
        "fallidos": 0, "robots": 0, "fechas_mejoradas": 0, "con_cuerpo": 0,
    }

    try:
        for article in session.scalars(stmt).all():
            stats["intentados"] += 1
            if stats["intentados"] % commit_every == 0:
                session.commit()

            if not robots.allowed(article.url):
                article.extraction_status = ExtractionStatus.ROBOTS_DENIED
                stats["robots"] += 1
                continue

            try:
                response = fetcher.get(article.url)
            except NotFound:
                # El artículo ya no existe. Se marca, no se borra: la fila
                # sigue documentando que el medio lo publicó.
                article.extraction_status = ExtractionStatus.HTTP_ERROR
                article.http_status = 404
                stats["http_error"] += 1
                continue
            except FetchError as exc:
                article.extraction_status = ExtractionStatus.FAILED
                stats["fallidos"] += 1
                logger.warning("extracción fallida", url=article.url, error=str(exc))
                continue

            article.http_status = response.status
            article.extracted_at = datetime.now(UTC)
            data = parse_article(response.text)

            if not data.title:
                article.extraction_status = ExtractionStatus.NO_TITLE
                stats["sin_titulo"] += 1
                continue

            # El titular extraído gana siempre: es el publicado, con tildes y
            # puntuación, frente a la reconstrucción del slug.
            article.title = data.title
            article.title_source = TitleSource.EXTRACTED
            article.extraction_status = ExtractionStatus.OK
            stats["ok"] += 1

            if data.author:
                article.author = data.author
            if data.description:
                article.description = data.description
            if data.section and not article.section:
                article.section = data.section

            if data.content:
                article.content = data.content
                article.content_hash = hashlib.sha256(
                    data.content.encode("utf-8")
                ).hexdigest()
                stats["con_cuerpo"] += 1

            # Fecha real: sube la precisión y permite asignar gobierno.
            if data.published_at:
                article.published_at = data.published_at
                article.published_date = data.published_at.date()
                if article.date_precision != DatePrecision.DAY:
                    stats["fechas_mejoradas"] += 1
                article.date_precision = DatePrecision.DAY
                gov = catalog.government_at(article.published_date)
                article.government_id = gov.id if gov else None
    finally:
        fetcher.close()

    return stats


def reclean_stored_content(session: Session, *, commit_every: int = 500) -> dict[str, int]:
    """Aplica `clean_content` al texto ya guardado y recalcula su hash.

    Existe porque la limpieza se añadió después de las primeras extracciones:
    sin esta pasada el corpus quedaría con dos criterios de limpieza según la
    fecha en que se extrajo cada artículo, que es justo el tipo de
    inconsistencia que arruina una comparación entre medios.
    """
    stats = {"revisados": 0, "modificados": 0, "vaciados": 0}

    for article in session.scalars(
        select(Article).where(Article.content.is_not(None)).order_by(Article.id)
    ):
        stats["revisados"] += 1
        limpio = clean_content(article.content)
        if limpio == article.content:
            continue

        article.content = limpio
        article.content_hash = (
            hashlib.sha256(limpio.encode("utf-8")).hexdigest() if limpio else None
        )
        stats["modificados"] += 1
        if limpio is None:
            stats["vaciados"] += 1

        if stats["modificados"] % commit_every == 0:
            session.commit()

    return stats
