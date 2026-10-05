"""Discovery para medios SIN sitemap mensual: feeds Arc paginados e índices de sitemap.

Los cinco medios de `SitemapProvider` publican un archivo por mes, así que pedir
"marzo de 2024" es una sola petición. Estos otros no:

* **Arc XP** (El Espectador, Semana, W Radio) expone un feed paginado
  `...&from={offset}` ordenado de lo más reciente a lo más antiguo. Para llegar a
  un mes hay que paginar hacia atrás desde hoy.
* **Índice de sitemap** (Cambio) expone un `sitemapindex` con sitemaps hijos que
  no están organizados por mes. Hay que leer los hijos y filtrar por fecha.

Ambos proveedores leen el feed completo UNA vez por corrida y lo guardan en
memoria; cada bloque mensual filtra sobre esa copia. Sin el caché, recolectar 48
meses repetiría la misma paginación 48 veces.

El riesgo propio de estas fuentes es la cobertura parcial: si el feed se acaba
antes de llegar al inicio del mes pedido, el mes está incompleto. Eso NO se
disimula: si el feed no alcanza ni el final del mes, el bloque falla con un
mensaje explícito; si lo alcanza a medias, cada item queda marcado
`cobertura = parcial` en `discovery_record.raw`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from news_corpus.config.catalog import SourceConfig
from news_corpus.providers.base import (
    BaseProvider,
    DiscoveredItem,
    DiscoveryResult,
    Period,
)
from news_corpus.providers.sitemap import _NS, parse_sitemap_root, parse_urlset
from news_corpus.utils.http import FetchError, HttpFetcher, NotFound
from news_corpus.utils.logging import get_logger

logger = get_logger(__name__)


class FueraDeAlcance(FetchError):
    """El feed no llega al período pedido. Es un hueco de la fuente, no un mes vacío."""


def _day(when: datetime | None) -> date | None:
    return when.date() if isinstance(when, datetime) else when


@dataclass
class _FeedSnapshot:
    """Todo lo que el feed ofreció en esta corrida."""

    items: list[DiscoveredItem] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)
    # Fecha más antigua alcanzada. Si es posterior al inicio de un mes, ese mes
    # está cubierto sólo en parte.
    oldest: date | None = None
    exhausted: bool = False  # True si el feed se terminó (no por max_offset)

    def add(self, items: list[DiscoveredItem]) -> None:
        self.items.extend(items)
        for it in items:
            d = _day(it.published_at)
            if d and (self.oldest is None or d < self.oldest):
                self.oldest = d


class _SnapshotProvider(BaseProvider):
    """Base común: descarga el feed una vez y reparte sus items por mes."""

    strategy: str = ""

    def __init__(self, fetcher: HttpFetcher | None = None) -> None:
        self._fetcher = fetcher or HttpFetcher("sitemap")
        self._cache: dict[str, _FeedSnapshot] = {}

    def supports(self, source: SourceConfig) -> bool:
        return source.discovery.strategy == self.strategy

    def close(self) -> None:
        self._fetcher.close()

    def snapshot(self, source: SourceConfig, *, stop_before: date | None = None) -> _FeedSnapshot:
        if source.id not in self._cache:
            self._cache[source.id] = self._load(source, stop_before=stop_before)
        return self._cache[source.id]

    def _load(self, source: SourceConfig, *, stop_before: date | None) -> _FeedSnapshot:
        raise NotImplementedError

    def discover(self, source: SourceConfig, period: Period) -> DiscoveryResult:
        if not self.supports(source):
            raise ValueError(f"{source.id} usa {source.discovery.strategy!r}, no {self.strategy!r}")

        snap = self.snapshot(source, stop_before=period.start)
        request_url = f"{self.strategy}:{source.id} ({len(snap.requests)} peticiones)"

        if snap.oldest is None:
            raise FetchError(f"{source.id}: el feed no devolvió ninguna URL con fecha")

        # El feed no llega ni al último día del mes: no hay datos de ese mes.
        if snap.oldest >= period.end:
            raise FueraDeAlcance(
                f"{source.id}: el feed sólo llega hasta {snap.oldest:%Y-%m-%d}; "
                f"no cubre {period.label}"
            )

        partial = snap.oldest > period.start
        items: list[DiscoveredItem] = []
        for it in snap.items:
            d = _day(it.published_at)
            if d is None or not period.contains(d):
                continue
            raw = dict(it.raw)
            raw["period"] = period.label
            raw["date_in_period"] = True
            raw["cobertura"] = "parcial" if partial else "completa"
            items.append(
                DiscoveredItem(
                    url=it.url,
                    title=it.title,
                    published_at=it.published_at,
                    published_at_raw=it.published_at_raw,
                    raw=raw,
                )
            )

        if partial:
            logger.warning(
                "mes cubierto parcialmente",
                medio=source.id,
                periodo=period.label,
                feed_llega_hasta=str(snap.oldest),
            )
        return DiscoveryResult(items=items, request_url=request_url, empty_is_legitimate=True)


class ArcFeedProvider(_SnapshotProvider):
    """Feeds `arc/outboundfeeds/sitemap` de Arc XP (El Espectador, Semana, W Radio).

    Pagina `from = 0, page_size, 2·page_size, …` hasta que ocurra lo primero:
    el feed se acaba, se supera `max_offset`, o los items ya son anteriores a
    `stop_before` (no hace falta ir más atrás que el mes más antiguo pedido).
    """

    name = "arc"
    strategy = "arc_paginated"

    def __init__(self, fetcher: HttpFetcher | None = None, *, stop_before: date | None = None):
        super().__init__(fetcher)
        self._stop_before = stop_before

    def _load(self, source: SourceConfig, *, stop_before: date | None) -> _FeedSnapshot:
        cfg = source.discovery
        if not cfg.url_template:
            raise ValueError(f"{source.id} no define url_template")
        step = cfg.page_size or 100
        limit = cfg.max_offset if cfg.max_offset is not None else 100_000
        # El límite inferior lo fija el plan completo (CLI), no el primer mes que
        # se procese: así una sola paginación sirve para toda la ventana.
        floor = self._stop_before or stop_before

        snap = _FeedSnapshot()
        offset = 0
        seen: set[str] = set()
        while offset <= limit:
            url = cfg.url_template.format(offset=offset)
            try:
                resp = self._fetcher.get(url)
            except NotFound:
                snap.exhausted = True
                break
            snap.requests.append(url)
            root = parse_sitemap_root(resp.text, url=url)
            page = [it for it in parse_urlset(root, source=source, period=None, url=url)
                    if it.url not in seen]
            if not page:
                snap.exhausted = True  # página vacía o repetida: fin del feed
                break
            seen.update(it.url for it in page)
            snap.add(page)
            dates = [d for d in (_day(it.published_at) for it in page) if d]
            if floor and dates and max(dates) < floor:
                break  # toda la página es anterior a lo que necesitamos
            offset += step

        logger.info(
            "feed Arc leído",
            medio=source.id,
            paginas=len(snap.requests),
            urls=len(snap.items),
            llega_hasta=str(snap.oldest),
            agotado=snap.exhausted,
        )
        return snap


class SitemapIndexProvider(_SnapshotProvider):
    """Un `sitemapindex` con hijos no mensuales (Cambio).

    Recorre los hijos (y nietos, si el índice está anidado) y se queda con
    todas sus URLs. Un hijo cuyo `lastmod` es anterior al mes más antiguo
    pedido se salta: nada dentro de él pudo modificarse después.
    """

    name = "sitemap_index"
    strategy = "sitemap_index"
    _MAX_CHILDREN = 2000

    def __init__(self, fetcher: HttpFetcher | None = None, *, stop_before: date | None = None):
        super().__init__(fetcher)
        self._stop_before = stop_before

    def _load(self, source: SourceConfig, *, stop_before: date | None) -> _FeedSnapshot:
        cfg = source.discovery
        if not cfg.url_template:
            raise ValueError(f"{source.id} no define url_template")
        floor = self._stop_before or stop_before

        snap = _FeedSnapshot()
        pending = [cfg.url_template]
        visited: set[str] = set()
        while pending and len(visited) < self._MAX_CHILDREN:
            url = pending.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                resp = self._fetcher.get(url)
            except NotFound:
                logger.info("sitemap hijo inexistente", medio=source.id, url=url)
                continue
            snap.requests.append(url)
            root = parse_sitemap_root(resp.text, url=url)

            if root.tag.endswith("sitemapindex"):
                for node in root.findall("sm:sitemap", _NS):
                    loc = (node.findtext("sm:loc", namespaces=_NS) or "").strip()
                    if not loc or not _is_content_sitemap(loc):
                        continue
                    lastmod = _day(_parse(node.findtext("sm:lastmod", namespaces=_NS)))
                    if floor and lastmod and lastmod < floor:
                        continue
                    pending.append(loc)
            else:
                snap.add(parse_urlset(root, source=source, period=None, url=url))

        snap.exhausted = True  # el índice se recorrió entero
        logger.info(
            "índice de sitemap leído",
            medio=source.id,
            sitemaps=len(snap.requests),
            urls=len(snap.items),
            llega_hasta=str(snap.oldest),
        )
        return snap


def _parse(value: str | None) -> datetime | None:
    from news_corpus.providers.sitemap import _parse_lastmod

    return _parse_lastmod(value)


# Hijos de índices WordPress/Yoast que no contienen artículos.
_NON_CONTENT = ("page-sitemap", "category-sitemap", "post_tag-sitemap", "tag-sitemap",
                "author-sitemap", "attachment-sitemap", "web-story-sitemap")


def _is_content_sitemap(url: str) -> bool:
    low = url.lower()
    return not any(marker in low for marker in _NON_CONTENT)
