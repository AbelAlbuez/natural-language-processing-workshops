"""Tests del catálogo: validan la configuración real del proyecto (§27)."""

from __future__ import annotations

from datetime import date

import pytest

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "config"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CONFIG_DIR)


def test_config_loads_and_validates(catalog):
    """Si esto falla, load_catalog encontró IDs duplicados, dominios ambiguos,
    huecos entre gobiernos o temas huérfanos."""
    assert catalog.sources
    assert catalog.governments
    assert catalog.topics


def test_los_diez_medios_del_alcance_estan(catalog):
    esperados = {
        "el_tiempo", "el_espectador", "semana", "la_republica", "noticias_caracol",
        "noticias_rcn", "w_radio", "blu_radio", "cambio", "rtvc",
    }
    assert esperados <= {s.id for s in catalog.sources}


def test_gobiernos_cubren_el_horizonte_sin_huecos(catalog):
    """Cinco gobiernos consecutivos, 2006-08-07 → 2026-08-07 (§6, §30)."""
    ordenados = sorted(catalog.governments, key=lambda g: g.start_date)
    assert len(ordenados) == 5
    assert ordenados[0].start_date == date(2006, 8, 7)
    assert ordenados[-1].end_date == date(2026, 8, 7)
    for prev, nxt in zip(ordenados, ordenados[1:], strict=False):
        assert prev.end_date == nxt.start_date, "no debe haber huecos ni solapes"


@pytest.mark.parametrize(
    ("cuando", "esperado"),
    [
        (date(2006, 8, 7), "uribe_2"),    # el día de posesión pertenece al que entra
        (date(2010, 8, 6), "uribe_2"),    # último día del período anterior
        (date(2010, 8, 7), "santos_1"),   # frontera exacta
        (date(2013, 5, 20), "santos_1"),
        (date(2019, 1, 1), "duque"),
        (date(2023, 6, 15), "petro"),
    ],
)
def test_resolucion_de_gobierno_por_fecha(catalog, cuando, esperado):
    gov = catalog.government_at(cuando)
    assert gov is not None and gov.id == esperado


def test_fecha_fuera_del_horizonte_no_tiene_gobierno(catalog):
    """2026-08-07 abre un período que está fuera del alcance a propósito."""
    assert catalog.government_at(date(2026, 8, 7)) is None
    assert catalog.government_at(date(2001, 1, 1)) is None


def test_mapeo_dominio_a_medio_ignora_www(catalog):
    assert catalog.source_for_domain("www.eltiempo.com").id == "el_tiempo"
    assert catalog.source_for_domain("eltiempo.com").id == "el_tiempo"
    assert catalog.source_for_domain("ELTIEMPO.COM").id == "el_tiempo"


def test_rtvc_resuelve_desde_su_dominio_nuevo(catalog):
    """rtvc.gov.co redirige a inravision.gov.co: ambos deben mapear al medio."""
    assert catalog.source_for_domain("rtvc.gov.co").id == "rtvc"
    assert catalog.source_for_domain("inravision.gov.co").id == "rtvc"


def test_cambio_responde_sin_www(catalog):
    assert catalog.source_for_domain("cambiocolombia.com").id == "cambio"


def test_dominio_desconocido_devuelve_none(catalog):
    assert catalog.source_for_domain("nytimes.com") is None


def test_rtvc_esta_inactivo(catalog):
    """Se desactivó a propósito: no se identificó discovery utilizable."""
    assert catalog.source("rtvc").active is False


def test_plantillas_de_sitemap_mensual(catalog):
    """Las plantillas verificadas en Fase 1 deben resolverse tal cual."""
    assert (
        catalog.source("el_tiempo").sitemap_url(2008, 3)
        == "https://www.eltiempo.com/sitemap-articles-2008-03.xml"
    )
    assert (
        catalog.source("noticias_caracol").sitemap_url(2008, 11)
        == "https://www.noticiascaracol.com/sitemap-200811.xml"
    )
    assert (
        catalog.source("blu_radio").sitemap_url(2012, 9)
        == "https://www.bluradio.com/sitemap-201209.xml"
    )


def test_plantilla_con_mes_en_ingles(catalog):
    """La República y RCN nombran el sitemap con el mes en inglés."""
    assert (
        catalog.source("la_republica").sitemap_url(2026, 8)
        == "https://www.larepublica.co/sitemaps/articles_August_2026.xml.gz"
    )
    assert (
        catalog.source("noticias_rcn").sitemap_url(2013, 1)
        == "https://www.noticiasrcn.com/sitemaps/articles_January_2013.xml.gz"
    )


def test_el_tiempo_distingue_archivo_de_archivo_fiable(catalog):
    """El sitemap llega a 1990 pero sólo es denso desde 2016. La diferencia
    entre ambas fechas es la defensa contra el sesgo de archivo (riesgo #2)."""
    et = catalog.source("el_tiempo")
    assert et.discovery.archive_from == date(1990, 1, 1)
    assert et.discovery.reliable_from == date(2016, 3, 1)
    assert et.discovery.archive_from < et.discovery.reliable_from


def test_medios_arc_declaran_fallback(catalog):
    """Semana, El Espectador y W Radio no tienen archivo propio profundo:
    deben declarar de dónde se completa."""
    for sid in ("semana", "el_espectador", "w_radio"):
        s = catalog.source(sid)
        assert s.discovery.archive_from is None
        assert s.discovery.fallback, f"{sid} debe declarar fallback"


def test_jerarquia_de_temas(catalog):
    ids = {t.id for t in catalog.topics}
    raices = [t for t in catalog.topics if t.parent_id is None]
    assert {"politica", "economia", "seguridad", "justicia"} <= ids
    assert len(raices) == 7
    protestas = next(t for t in catalog.topics if t.id == "protestas")
    assert protestas.parent_id == "sociedad"
    assert "disturbios" in protestas.keywords and "manifestacion" in protestas.keywords
