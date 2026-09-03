"""Tests de la derivación de título/sección y del etiquetado temático."""

from __future__ import annotations

import pytest

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import REPO_ROOT
from news_corpus.pipeline.enrich import derive_from_url
from news_corpus.pipeline.tagging import TopicTagger, normalize_text, rule_version


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(REPO_ROOT / "config")


# ── derivación desde la URL ──────────────────────────────────────────────────


def test_slug_descriptivo_da_titular_y_seccion():
    d = derive_from_url(
        "https://www.noticiascaracol.com/colombia/"
        "senado-de-estados-unidos-logra-acuerdo-para-evitar-abismo-fiscal"
    )
    assert d.section == "colombia"
    assert d.title == "Senado de estados unidos logra acuerdo para evitar abismo fiscal"


def test_sufijo_articulo_de_el_tiempo_se_elimina():
    """El Tiempo usa '+articulo+ID'. Sin quitarlo, "articulo" salía como la
    palabra más frecuente del medio y contaminaba el análisis léxico."""
    d = derive_from_url(
        "https://www.eltiempo.com/don-juan/historias/"
        "lycan-hypercar-el-auto-mas-caro-del-mundo+articulo+12567802"
    )
    assert d.title == "Lycan hypercar el auto mas caro del mundo"
    assert "articulo" not in d.title.lower()
    assert "12567802" not in d.title


@pytest.mark.parametrize(
    "url",
    [
        "https://www.eltiempo.com/archivo/documento/MAM-2880084",
        "https://www.eltiempo.com/archivo/documento/CMS-16551020",
    ],
)
def test_identificadores_puros_no_dan_titular(url):
    """Inventar un título a partir de 'CMS-16551020' sería fabricar datos."""
    d = derive_from_url(url)
    assert d.title is None
    assert d.section == "archivo"


def test_id_numerico_al_final_se_quita():
    d = derive_from_url("https://www.eltiempo.com/politica/reforma-tributaria-123456")
    assert d.title == "Reforma tributaria"


def test_seccion_solo_si_es_conocida():
    """Un primer segmento desconocido puede ser parte del slug, no una sección."""
    assert derive_from_url("https://x.co/politica/algo-aqui").section == "politica"
    assert derive_from_url("https://x.co/xyzzy/algo-aqui").section is None


def test_url_sin_path_no_rompe():
    d = derive_from_url("https://www.eltiempo.com/")
    assert d.title is None and d.section is None


# ── etiquetado temático ──────────────────────────────────────────────────────


def test_normalize_text_quita_tildes():
    assert normalize_text("Elección Política") == "eleccion politica"


def test_etiqueta_por_titulo(catalog):
    tagger = TopicTagger(catalog)
    matches = tagger.match(
        title="Gobierno radica la reforma tributaria en el Congreso",
        url="https://x.co/a",
        section=None,
    )
    ids = {m.topic_id for m in matches}
    assert {"gobierno", "reformas", "congreso"} <= ids


def test_etiquetado_es_multietiqueta(catalog):
    tagger = TopicTagger(catalog)
    matches = tagger.match(
        title="Farc y narcotrafico en la frontera con Venezuela",
        url="https://x.co/a",
        section=None,
    )
    ids = {m.topic_id for m in matches}
    assert {"guerrillas", "narcotrafico", "venezuela"} <= ids


def test_limite_de_palabra_evita_falsos_positivos(catalog):
    """'paz' no debe emparejar dentro de 'capaz'."""
    tagger = TopicTagger(catalog)
    matches = tagger.match(title="Un equipo capaz de todo", url="https://x.co/a", section=None)
    ids = {m.topic_id for m in matches}
    assert "conflicto_armado" not in ids


def test_titulo_sin_tema_no_produce_etiquetas(catalog):
    tagger = TopicTagger(catalog)
    assert tagger.match(title="Receta de arepas rellenas", url="https://x.co/a", section=None) == []


def test_registra_el_campo_y_la_palabra_que_emparejaron(catalog):
    """Sin esto no se puede auditar por qué un artículo quedó en un tema."""
    tagger = TopicTagger(catalog)
    matches = tagger.match(title="Aumenta la inflacion", url="https://x.co/a", section=None)
    m = next(m for m in matches if m.topic_id == "inflacion")
    assert m.field == "title" and m.keyword == "inflacion"


def test_rule_version_cambia_con_las_keywords(catalog):
    """Permite re-etiquetar cuando cambia topics.yaml y saber qué reglas se usaron."""
    v1 = rule_version(catalog)
    topic = next(t for t in catalog.topics if t.id == "protestas")
    topic.keywords = [*topic.keywords, "cacerolazo"]
    assert rule_version(catalog) != v1
