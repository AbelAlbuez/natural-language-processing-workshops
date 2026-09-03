"""Discovery desde los sitemaps mensuales de cada medio.

Es el proveedor principal del corpus: es el único mecanismo verificado que
cubre el horizonte completo (Fase 1, §D.1). Cinco medios publican un sitemap
por mes, lo que hace que el bloque mensual sea la unidad natural del pipeline.

Sobre las fechas: los sitemaps traen `<lastmod>`, que es *modificación*, no
publicación. Para el archivo histórico ambas coinciden casi siempre, pero un
artículo reeditado años después lleva una fecha posterior. Por eso el archivo
mensual manda sobre `lastmod` a la hora de asignar el período, y las fechas
fuera de ventana se cuentan en vez de descartarse: el archivo dice a qué mes
pertenece la nota mejor que su marca de modificación.
"""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree

from news_corpus.config.catalog import SourceConfig
from news_corpus.providers.base import (
    BaseProvider,
    DiscoveredItem,
    DiscoveryResult,
    Period,
)
from news_corpus.utils.http import FetchError, HttpFetcher, NotFound
from news_corpus.utils.logging import get_logger

logger = get_logger(__name__)

_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}

SUPPORTED_STRATEGIES = {"monthly_sitemap", "monthly_sitemap_gz"}

# Rutas que un sitemap puede listar pero que no son artículos.
_NON_ARTICLE = re.compile(
    r"/(tag|tags|autor|autores|author|seccion|secciones|galeria|galerias|"
    r"video|videos|podcast|especiales|buscar|search)(/|$)",
    re.IGNORECASE,
)


def _parse_lastmod(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        # fromisoformat maneja el offset -05:00 de los sitemaps colombianos.
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def looks_like_article(url: str) -> bool:
    """Filtro conservador: ante la duda, se conserva.

    Descartar de más en discovery es peor que de menos — un no-artículo se
    puede filtrar después, pero una nota perdida no se recupera.
    """
    if _NON_ARTICLE.search(url):
        return False
    path = url.split("//", 1)[-1]
    path = path[path.find("/") :] if "/" in path else "/"
    return len(path.strip("/")) > 0


class SitemapProvider(BaseProvider):
    name = "sitemap"

    def __init__(self, fetcher: HttpFetcher | None = None) -> None:
        self._fetcher = fetcher or HttpFetcher(self.name)

    def supports(self, source: SourceConfig) -> bool:
        return source.discovery.strategy in SUPPORTED_STRATEGIES

    def close(self) -> None:
        self._fetcher.close()

    def discover(self, source: SourceConfig, period: Period) -> DiscoveryResult:
        if not self.supports(source):
            raise ValueError(
                f"{source.id} usa la estrategia {source.discovery.strategy!r}, "
                f"no soportada por SitemapProvider"
            )

        url = source.sitemap_url(period.start.year, period.start.month)

        try:
            response = self._fetcher.get(url)
        except NotFound:
            # El medio no publicó ese mes, o su archivo no llega tan atrás.
            # Es un vacío legítimo: el bloque se completa con cero artículos.
            logger.info("sitemap inexistente", medio=source.id, periodo=period.label, url=url)
            return DiscoveryResult(items=[], request_url=url, empty_is_legitimate=True)

        items = self._parse(response.text, source=source, period=period, url=url)
        logger.info(
            "sitemap procesado",
            medio=source.id,
            periodo=period.label,
            urls=len(items),
        )
        return DiscoveryResult(items=items, request_url=url, empty_is_legitimate=True)

    # ── parsing ──────────────────────────────────────────────────────────────

    def _parse(
        self, xml: str, *, source: SourceConfig, period: Period, url: str
    ) -> list[DiscoveredItem]:
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            # XML roto no es un mes vacío: hay que reintentarlo.
            raise FetchError(f"{url}: XML inválido ({exc})") from exc

        # Una página de error del servidor suele ser XML/HTML bien formado, así
        # que parsear sin error no basta: hay que comprobar que esto sea de
        # verdad un sitemap. Si no, cero URLs se confundiría con un mes vacío y
        # el bloque quedaría completado sin datos.
        tag = root.tag.split("}")[-1]
        if tag not in {"urlset", "sitemapindex"}:
            raise FetchError(
                f"{url}: la respuesta no es un sitemap (elemento raíz <{tag}>)"
            )

        items: list[DiscoveredItem] = []
        for node in root.findall("sm:url", _NS):
            loc = node.findtext("sm:loc", namespaces=_NS)
            if not loc or not loc.strip():
                continue
            loc = loc.strip()

            if not looks_like_article(loc):
                continue

            lastmod_raw = node.findtext("sm:lastmod", namespaces=_NS)
            published_at = _parse_lastmod(lastmod_raw)

            # Los sitemaps actuales traen news:title; los históricos no.
            title = node.findtext("news:news/news:title", namespaces=_NS)

            items.append(
                DiscoveredItem(
                    url=loc,
                    title=title.strip() if title else None,
                    published_at=published_at,
                    published_at_raw=lastmod_raw,
                    raw={
                        "sitemap_url": url,
                        "source_id": source.id,
                        "period": period.label,
                        # Trazabilidad de la fecha: es lastmod, no una fecha de
                        # publicación declarada por el medio.
                        "date_source": "sitemap:lastmod",
                        "date_in_period": (
                            period.contains(published_at) if published_at else None
                        ),
                    },
                )
            )
        return items
