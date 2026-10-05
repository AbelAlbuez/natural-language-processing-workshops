"""Tests de ArcFeedProvider y SitemapIndexProvider (medios sin sitemap mensual)."""

from __future__ import annotations

from datetime import date

import pytest

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import REPO_ROOT
from news_corpus.providers import COLLECTABLE_STRATEGIES, ProviderPool
from news_corpus.providers.base import Period
from news_corpus.providers.indexed import (
    ArcFeedProvider,
    FueraDeAlcance,
    SitemapIndexProvider,
)
from news_corpus.providers.sitemap import SitemapProvider
from news_corpus.utils.http import NotFound, Response

NS = (
    'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"'
)


def urlset(*entries: tuple[str, str, str | None]) -> str:
    body = ""
    for loc, lastmod, title in entries:
        news = f"<news:news><news:title>{title}</news:title></news:news>" if title else ""
        body += f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>{news}</url>"
    return f'<?xml version="1.0"?><urlset {NS}>{body}</urlset>'


class RoutedFetcher:
    """Responde según la URL; las no registradas dan 404."""

    def __init__(self, routes: dict[str, str]):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url):
        self.calls.append(url)
        if url not in self.routes:
            raise NotFound(url)
        return Response(url=url, status=200, text=self.routes[url])

    def close(self):
        pass


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(REPO_ROOT / "config")


# ── Arc ──────────────────────────────────────────────────────────────────────

ARC = "https://www.semana.com/arc/outboundfeeds/sitemap/?outputType=xml&from={}"


def arc_routes() -> dict[str, str]:
    # Feed de lo más reciente a lo más antiguo, 2 URLs por página (page_size=100
    # en la config; el offset real no importa, sólo que avance).
    return {
        ARC.format(0): urlset(
            ("https://www.semana.com/nacion/a-1/", "2024-03-20T10:00:00-05:00", "Titular A"),
            ("https://www.semana.com/nacion/b-2/", "2024-03-02T10:00:00-05:00", "Titular B"),
        ),
        ARC.format(100): urlset(
            ("https://www.semana.com/nacion/congreso-aprueba-reforma-pensional-3/", "2024-02-15T10:00:00-05:00", None),
            ("https://www.semana.com/tags/politica/", "2024-02-10T10:00:00-05:00", None),
        ),
        ARC.format(200): urlset(
            ("https://www.semana.com/nacion/d-4/", "2024-01-05T10:00:00-05:00", None),
        ),
        ARC.format(300): urlset(),  # fin del feed
    }


def test_arc_reparte_por_mes_y_pagina_una_sola_vez(catalog):
    fetcher = RoutedFetcher(arc_routes())
    provider = ArcFeedProvider(fetcher, stop_before=date(2024, 1, 1))
    semana = catalog.source("semana")

    marzo = provider.discover(semana, Period.month(2024, 3))
    febrero = provider.discover(semana, Period.month(2024, 2))

    assert [i.title for i in marzo.items] == ["Titular A", "Titular B"]
    # /tags/ se filtra como no-artículo
    assert [i.url for i in febrero.items] == ["https://www.semana.com/nacion/congreso-aprueba-reforma-pensional-3/"]
    assert all(i.raw["cobertura"] == "completa" for i in marzo.items + febrero.items)
    # el feed se pagina una vez para todos los meses
    assert len(fetcher.calls) == 4


def test_arc_detiene_la_paginacion_al_pasar_el_piso(catalog):
    fetcher = RoutedFetcher(arc_routes())
    provider = ArcFeedProvider(fetcher, stop_before=date(2024, 3, 1))
    provider.discover(catalog.source("semana"), Period.month(2024, 3))
    # la página 2 ya es toda anterior a marzo: no se pide la 3
    assert len(fetcher.calls) == 2


def test_arc_mes_fuera_de_alcance_falla_explicitamente(catalog):
    routes = {ARC.format(0): arc_routes()[ARC.format(0)], ARC.format(100): urlset()}
    provider = ArcFeedProvider(RoutedFetcher(routes))
    with pytest.raises(FueraDeAlcance):
        provider.discover(catalog.source("semana"), Period.month(2023, 12))


def test_arc_mes_cubierto_a_medias_queda_marcado_parcial(catalog):
    routes = {ARC.format(0): arc_routes()[ARC.format(0)], ARC.format(100): urlset()}
    provider = ArcFeedProvider(RoutedFetcher(routes))
    res = provider.discover(catalog.source("semana"), Period.month(2024, 3))
    # el feed sólo llega al 2 de marzo: falta el 1 de marzo
    assert {i.raw["cobertura"] for i in res.items} == {"parcial"}


def test_arc_respeta_max_offset(catalog):
    semana = catalog.source("semana").model_copy(deep=True)
    semana.discovery.max_offset = 100
    fetcher = RoutedFetcher(arc_routes())
    ArcFeedProvider(fetcher).snapshot(semana)
    assert len(fetcher.calls) == 2  # offsets 0 y 100


# ── Índice de sitemap ────────────────────────────────────────────────────────

IDX = "https://cambiocolombia.com/sitemap.xml"


def index_routes() -> dict[str, str]:
    return {
        IDX: f"""<?xml version="1.0"?><sitemapindex {NS}>
          <sitemap><loc>https://cambiocolombia.com/post-sitemap1.xml</loc>
                   <lastmod>2023-01-10T00:00:00+00:00</lastmod></sitemap>
          <sitemap><loc>https://cambiocolombia.com/post-sitemap2.xml</loc>
                   <lastmod>2024-05-01T00:00:00+00:00</lastmod></sitemap>
          <sitemap><loc>https://cambiocolombia.com/category-sitemap.xml</loc>
                   <lastmod>2024-05-01T00:00:00+00:00</lastmod></sitemap>
        </sitemapindex>""",
        "https://cambiocolombia.com/post-sitemap1.xml": urlset(
            ("https://cambiocolombia.com/pais/viejo", "2022-12-01T00:00:00+00:00", None),
        ),
        "https://cambiocolombia.com/post-sitemap2.xml": urlset(
            ("https://cambiocolombia.com/pais/nuevo-1", "2024-04-11T00:00:00+00:00", None),
            ("https://cambiocolombia.com/pais/nuevo-2", "2024-05-01T00:00:00+00:00", None),
        ),
    }


def test_indice_recorre_hijos_y_filtra_por_mes(catalog):
    fetcher = RoutedFetcher(index_routes())
    provider = SitemapIndexProvider(fetcher)
    abril = provider.discover(catalog.source("cambio"), Period.month(2024, 4))
    assert [i.url for i in abril.items] == ["https://cambiocolombia.com/pais/nuevo-1"]
    assert "https://cambiocolombia.com/category-sitemap.xml" not in fetcher.calls


def test_indice_salta_hijos_anteriores_al_piso(catalog):
    fetcher = RoutedFetcher(index_routes())
    SitemapIndexProvider(fetcher, stop_before=date(2024, 1, 1)).snapshot(catalog.source("cambio"))
    assert "https://cambiocolombia.com/post-sitemap1.xml" not in fetcher.calls


# ── Fecha de publicación y registro ──────────────────────────────────────────


def test_publication_date_tiene_prioridad_sobre_lastmod(catalog):
    xml = f"""<?xml version="1.0"?><urlset {NS}><url>
      <loc>https://www.eltiempo.com/politica/nota-1</loc>
      <lastmod>2024-07-01T00:00:00-05:00</lastmod>
      <news:news><news:publication_date>2024-06-10T08:00:00-05:00</news:publication_date>
      <news:title>Titular</news:title></news:news></url></urlset>"""
    url = catalog.source("el_tiempo").sitemap_url(2024, 6)
    provider = SitemapProvider(RoutedFetcher({url: xml}))
    (item,) = provider.discover(catalog.source("el_tiempo"), Period.month(2024, 6)).items
    assert item.published_at.date() == date(2024, 6, 10)
    assert item.raw["date_source"] == "sitemap:news_publication_date"
    assert item.raw["date_in_period"] is True


def test_pool_cubre_todas_las_estrategias_activas_salvo_rtvc(catalog):
    pool = ProviderPool()
    activos = [s for s in catalog.active_sources()]
    assert len(activos) >= 9
    for s in activos:
        assert s.discovery.strategy in COLLECTABLE_STRATEGIES
        pool.for_strategy(s.discovery.strategy)
