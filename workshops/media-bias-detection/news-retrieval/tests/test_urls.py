"""Tests de normalización de URLs — la base de la deduplicación (§17, §27)."""

from __future__ import annotations

import pytest

from news_corpus.utils.urls import domain_of, hash_url, normalize_url


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("http://www.eltiempo.com/politica/nota-123", "https://eltiempo.com/politica/nota-123"),
        ("https://eltiempo.com/politica/nota-123/", "https://eltiempo.com/politica/nota-123"),
        ("HTTPS://WWW.ELTIEMPO.COM/Politica/Nota-123", "https://eltiempo.com/Politica/Nota-123"),
        ("https://eltiempo.com/nota#comentarios", "https://eltiempo.com/nota"),
        ("  https://eltiempo.com/nota  ", "https://eltiempo.com/nota"),
    ],
)
def test_normalizacion_basica(crudo, esperado):
    assert normalize_url(crudo) == esperado


def test_el_path_conserva_mayusculas():
    """El path identifica el artículo: bajarlo a minúsculas perdería registros."""
    assert normalize_url("https://eltiempo.com/ARTICULO-WEB-NEW_NOTA-8449220.html").endswith(
        "/ARTICULO-WEB-NEW_NOTA-8449220.html"
    )


def test_se_eliminan_parametros_de_campana():
    assert (
        normalize_url("https://semana.com/nota?utm_source=twitter&utm_medium=social")
        == "https://semana.com/nota"
    )


def test_se_conservan_parametros_significativos():
    """`from` es paginación real en los feeds Arc: no es tracking."""
    assert "from=100" in normalize_url("https://semana.com/feed?from=100")


def test_orden_de_parametros_no_altera_la_identidad():
    a = normalize_url("https://eltiempo.com/n?b=2&a=1")
    b = normalize_url("https://eltiempo.com/n?a=1&b=2")
    assert a == b


def test_http_y_https_son_el_mismo_articulo():
    """Las URLs de Common Crawl de 2013 son http; las de sitemap, https."""
    assert hash_url("http://www.eltiempo.com/nota") == hash_url("https://eltiempo.com/nota")


def test_articulos_distintos_no_colisionan():
    assert hash_url("https://eltiempo.com/nota-1") != hash_url("https://eltiempo.com/nota-2")


def test_hash_es_estable_y_hexadecimal():
    h = hash_url("https://eltiempo.com/nota")
    assert h == hash_url("https://eltiempo.com/nota")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_domain_of():
    assert domain_of("https://www.noticiascaracol.com/a/b") == "noticiascaracol.com"
    assert domain_of("https://cambiocolombia.com/x") == "cambiocolombia.com"
