"""Tests de la resolución de fechas y gobierno.

Estos tests existen por un fallo real encontrado en la primera recolección:
los sitemaps de Blu Radio de 2013 traen `lastmod` de 2016-2024 (el 100% de los
registros), y los de Caracol un 73%. Son marcas de una migración masiva del
CMS, no fechas de publicación. Los slugs lo prueban:
`.../en-blu-jeans-1-de-enero-de-2013` con lastmod 2016-04-28.

Si esta lógica se rompe, el eje temporal del corpus —la variable de análisis
del proyecto— queda corrompido en silencio.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import REPO_ROOT
from news_corpus.db.models import DatePrecision
from news_corpus.pipeline.collector import resolve_government, resolve_publication_date
from news_corpus.providers.base import DiscoveredItem, Period


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(REPO_ROOT / "config")


def _item(lastmod: str | None) -> DiscoveredItem:
    dt = datetime.fromisoformat(lastmod) if lastmod else None
    return DiscoveredItem(url="https://x.co/a", published_at=dt, published_at_raw=lastmod)


# ── Fecha ────────────────────────────────────────────────────────────────────


def test_lastmod_dentro_del_mes_se_cree():
    period = Period.month(2013, 1)
    at, d, prec = resolve_publication_date(_item("2013-01-15T10:00:00"), period)
    assert prec == DatePrecision.DAY
    assert d.isoformat() == "2013-01-15"
    assert at is not None


def test_lastmod_de_otra_epoca_se_degrada_al_mes_del_sitemap():
    """El caso Blu Radio: sitemap de enero de 2013 con lastmod de abril de 2016."""
    period = Period.month(2013, 1)
    at, d, prec = resolve_publication_date(_item("2016-04-28T00:55:33"), period)
    assert prec == DatePrecision.MONTH
    assert d.isoformat() == "2013-01-01", "manda el mes del archivo, no el lastmod"
    assert at is None, "no se puede afirmar una hora que no se conoce"


def test_sin_lastmod_queda_precision_de_mes():
    at, d, prec = resolve_publication_date(_item(None), Period.month(2008, 3))
    assert prec == DatePrecision.MONTH
    assert d.isoformat() == "2008-03-01"
    assert at is None


def test_frontera_del_mes():
    """El último instante del mes cuenta; el primero del siguiente, no."""
    period = Period.month(2013, 1)
    assert resolve_publication_date(_item("2013-01-31T23:59:59"), period)[2] is DatePrecision.DAY
    assert resolve_publication_date(_item("2013-02-01T00:00:00"), period)[2] is DatePrecision.MONTH


# ── Gobierno ─────────────────────────────────────────────────────────────────


def test_gobierno_con_precision_de_dia(catalog):
    period = Period.month(2013, 5)
    _, d, prec = resolve_publication_date(_item("2013-05-20T09:00:00"), period)
    gov = resolve_government(catalog, d, prec, period)
    assert gov is not None and gov.id == "santos_1"


def test_gobierno_con_precision_de_mes_no_ambiguo(catalog):
    """Enero de 2013 cae entero dentro de Santos I: se puede asignar."""
    period = Period.month(2013, 1)
    _, d, prec = resolve_publication_date(_item("2016-04-28T00:00:00"), period)
    gov = resolve_government(catalog, d, prec, period)
    assert prec is DatePrecision.MONTH
    assert gov is not None and gov.id == "santos_1"


@pytest.mark.parametrize("year", [2010, 2014, 2018, 2022])
def test_mes_de_transicion_con_precision_de_mes_no_asigna_gobierno(catalog, year):
    """Agosto de posesión contiene dos gobiernos: elegir uno sería inventarlo."""
    period = Period.month(year, 8)
    _, d, prec = resolve_publication_date(_item(None), period)
    assert prec is DatePrecision.MONTH
    assert resolve_government(catalog, d, prec, period) is None


def test_mes_de_transicion_con_precision_de_dia_si_asigna(catalog):
    """Con día exacto no hay ambigüedad, ni siquiera en el mes de posesión."""
    period = Period.month(2010, 8)
    for dia, esperado in (("2010-08-06", "uribe_2"), ("2010-08-08", "santos_1")):
        _, d, prec = resolve_publication_date(_item(f"{dia}T12:00:00"), period)
        gov = resolve_government(catalog, d, prec, period)
        assert prec is DatePrecision.DAY
        assert gov is not None and gov.id == esperado


def test_periodo_fuera_del_horizonte_no_tiene_gobierno(catalog):
    period = Period.month(2003, 5)
    _, d, prec = resolve_publication_date(_item(None), period)
    assert resolve_government(catalog, d, prec, period) is None
