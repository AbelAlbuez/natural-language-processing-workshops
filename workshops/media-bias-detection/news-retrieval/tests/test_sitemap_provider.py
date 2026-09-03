"""Tests del SitemapProvider con XML real de los medios (§27)."""

from __future__ import annotations

import pytest

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import REPO_ROOT
from news_corpus.providers.base import Period
from news_corpus.providers.sitemap import SitemapProvider, looks_like_article
from news_corpus.utils.http import FetchError, NotFound

# Fragmento con la forma real de un sitemap de El Tiempo de 2008:
# URLs /archivo/documento/MAM-####### sin slug ni news:title.
XML_HISTORICO = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
 <url><loc>https://www.eltiempo.com/archivo/documento/MAM-2880084</loc>
      <lastmod>2008-03-31T00:00:00-05:00</lastmod></url>
 <url><loc>https://www.eltiempo.com/archivo/documento/MAM-2880290</loc>
      <lastmod>2008-03-15T10:22:00-05:00</lastmod></url>
 <url><loc>https://www.eltiempo.com/tags/politica</loc>
      <lastmod>2008-03-02T00:00:00-05:00</lastmod></url>
</urlset>"""

# Forma del sitemap actual: trae news:title.
XML_ACTUAL = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
 <url><loc>https://www.eltiempo.com/politica/reforma-tributaria-123</loc>
      <lastmod>2024-06-10T08:00:00-05:00</lastmod>
      <news:news><news:publication><news:name>ElTiempo.com</news:name>
      <news:language>es</news:language></news:publication>
      <news:title>Gobierno radica la reforma</news:title></news:news></url>
</urlset>"""


class FakeFetcher:
    """Sustituye la red. `body` puede ser texto o una excepción a lanzar."""

    def __init__(self, body):
        self.body = body
        self.calls: list[str] = []

    def get(self, url):
        self.calls.append(url)
        if isinstance(self.body, Exception):
            raise self.body
        from news_corpus.utils.http import Response

        return Response(url=url, status=200, text=self.body)

    def close(self):
        pass


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(REPO_ROOT / "config")


def test_parsea_sitemap_historico_sin_titulo(catalog):
    fetcher = FakeFetcher(XML_HISTORICO)
    provider = SitemapProvider(fetcher=fetcher)
    result = provider.discover(catalog.source("el_tiempo"), Period.month(2008, 3))

    # La URL de /tags/ se descarta: no es un artículo.
    assert len(result.items) == 2
    assert all(i.title is None for i in result.items)
    assert result.items[0].url.endswith("MAM-2880084")
    assert result.items[0].published_at.year == 2008
    assert result.items[0].raw["date_source"] == "sitemap:lastmod"


def test_pide_la_url_mensual_correcta(catalog):
    fetcher = FakeFetcher(XML_HISTORICO)
    SitemapProvider(fetcher=fetcher).discover(catalog.source("el_tiempo"), Period.month(2008, 3))
    assert fetcher.calls == ["https://www.eltiempo.com/sitemap-articles-2008-03.xml"]


def test_extrae_news_title_cuando_existe(catalog):
    fetcher = FakeFetcher(XML_ACTUAL)
    result = SitemapProvider(fetcher=fetcher).discover(
        catalog.source("el_tiempo"), Period.month(2024, 6)
    )
    assert result.items[0].title == "Gobierno radica la reforma"


def test_marca_si_la_fecha_cae_en_el_periodo(catalog):
    fetcher = FakeFetcher(XML_HISTORICO)
    result = SitemapProvider(fetcher=fetcher).discover(
        catalog.source("el_tiempo"), Period.month(2008, 3)
    )
    assert all(i.raw["date_in_period"] is True for i in result.items)

    # El mismo XML leído como si fuera el sitemap de otro mes: fuera de ventana.
    fetcher2 = FakeFetcher(XML_HISTORICO)
    result2 = SitemapProvider(fetcher=fetcher2).discover(
        catalog.source("el_tiempo"), Period.month(2013, 1)
    )
    assert all(i.raw["date_in_period"] is False for i in result2.items)


def test_404_es_un_mes_vacio_legitimo(catalog):
    """El medio no publicó ese mes: el bloque se completa, no falla."""
    fetcher = FakeFetcher(NotFound("x"))
    result = SitemapProvider(fetcher=fetcher).discover(
        catalog.source("blu_radio"), Period.month(2009, 1)
    )
    assert result.items == []
    assert result.empty_is_legitimate is True


def test_xml_invalido_es_un_fallo_no_un_mes_vacio(catalog):
    """Confundirlos marcaría el bloque como completado sin datos."""
    provider = SitemapProvider(fetcher=FakeFetcher("<html>error 502</html>"))
    with pytest.raises(FetchError):
        provider.discover(catalog.source("el_tiempo"), Period.month(2008, 3))


def test_medio_sin_sitemap_no_esta_soportado(catalog):
    provider = SitemapProvider(fetcher=FakeFetcher(""))
    assert provider.supports(catalog.source("el_tiempo")) is True
    assert provider.supports(catalog.source("semana")) is False
    with pytest.raises(ValueError, match="no soportada"):
        provider.discover(catalog.source("semana"), Period.month(2020, 1))


# ── filtro de artículos ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://www.eltiempo.com/archivo/documento/MAM-2880084",
        "https://www.eltiempo.com/politica/reforma-tributaria-123",
        "https://www.bluradio.com/sociedad/en-blu-jeans-1-de-enero-de-2013",
    ],
)
def test_reconoce_articulos(url):
    assert looks_like_article(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.eltiempo.com/tags/politica",
        "https://www.eltiempo.com/autor/juan-perez",
        "https://www.eltiempo.com/",
        "https://www.bluradio.com/videos/algo",
    ],
)
def test_descarta_lo_que_no_es_articulo(url):
    assert not looks_like_article(url)


# ── períodos ─────────────────────────────────────────────────────────────────


def test_periodo_mensual():
    p = Period.month(2013, 12)
    assert (p.start.isoformat(), p.end.isoformat()) == ("2013-12-01", "2014-01-01")
    assert p.label == "2013-12"
