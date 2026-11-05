"""Tests de la derivación de título/sección y del etiquetado temático."""

from __future__ import annotations

import pytest

from news_corpus.config.catalog import load_catalog
from news_corpus.config.settings import REPO_ROOT
from news_corpus.db.models import NonNewsReason
from news_corpus.pipeline.enrich import classify_non_news, derive_from_url
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


def test_un_solo_segmento_solo_es_seccion_si_es_conocida():
    """Con un único segmento, ese segmento puede ser el slug y no una sección."""
    assert derive_from_url("https://x.co/politica").section == "politica"
    assert derive_from_url("https://x.co/algo-aqui-largo").section is None


@pytest.mark.parametrize(
    ("url", "seccion"),
    [
        ("https://www.bluradio.com/nacion/algo-aqui", "nacion"),
        ("https://www.larepublica.co/globoeconomia/algo-aqui-3942567", "globoeconomia"),
        ("https://cambiocolombia.com/poder/articulo/2025/6/algo-aqui", "poder"),
        ("https://www.noticiasrcn.com/tendencias/algo-aqui-423798", "tendencias"),
    ],
)
def test_con_varios_segmentos_el_primero_es_la_seccion(url, seccion):
    """La lista cerrada dejaba sin sección a 'nacion' (60k URLs de Blu) o a
    'globoeconomia' (66k de La República): con dos o más segmentos el primero
    nunca es el slug, así que no hace falta conocerlo de antemano."""
    assert derive_from_url(url).section == seccion


def test_seccion_sin_tildes():
    """Caracol publica a la vez '/politica/' y '/política/'."""
    assert derive_from_url("https://www.noticiascaracol.com/pol%C3%ADtica/algo").section == "politica"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.eltiempo.com/documento/CMS-16551020",
        "https://www.eltiempo.com/2013/01/algo-aqui",
        "https://www.eltiempo.com/don-juanhttps:/algo-aqui",
    ],
)
def test_plantilla_o_url_rota_no_es_seccion(url):
    assert derive_from_url(url).section is None


# ── códigos del CMS de Blu Radio y Caracol ───────────────────────────────────


@pytest.mark.parametrize(
    ("url", "titulo"),
    [
        ("https://www.bluradio.com/mundo/rusia-y-china-vetan-resolucion-de-eeuu-para-tregua-en-gaza-cb20",
         "Rusia y china vetan resolucion de eeuu para tregua en gaza"),
        ("https://www.noticiascaracol.com/politica/no-apoyamos-la-prorroga-para-nosotros-mininterior-rg10",
         "No apoyamos la prorroga para nosotros mininterior"),
        ("https://www.bluradio.com/entretenimiento/un-colombiano-encargado-de-produccion-so35",
         "Un colombiano encargado de produccion"),
        ("https://www.bluradio.com/hjck/edgar-allan-poe-el-maestro-del-terror-rg10-rg10",
         "Edgar allan poe el maestro del terror"),
        ("https://www.noticiascaracol.com/septimo-dia/capitulos/violencia-digital-contra-las-mujeres-so35-rg10",
         "Violencia digital contra las mujeres"),
    ],
)
def test_codigo_del_cms_se_quita(url, titulo):
    """Lo llevaban el 58% de las URLs de Blu y el 49% de las de Caracol."""
    assert derive_from_url(url).title == titulo


@pytest.mark.parametrize(
    "url",
    [
        "https://www.bluradio.com/mundo/lo-que-necesita-saber-sobre-el-asteroide-da14",
        "https://www.bluradio.com/mundo/rusia-niega-toda-implicacion-en-el-derribo-del-mh17",
        "https://www.noticiascaracol.com/entretenimiento/gran-concierto-de-ub40",
    ],
)
def test_colas_legitimas_con_la_misma_forma_se_conservan(url):
    """'da14' es un asteroide, 'mh17' un vuelo, 'ub40' una banda."""
    assert derive_from_url(url).title.split()[-1] in {"da14", "mh17", "ub40"}


def test_codigo_del_cms_solo_en_sus_dominios():
    d = derive_from_url("https://www.eltiempo.com/mundo/algo-que-paso-en-el-pais-rg10")
    assert d.title.endswith("rg10")


# ── piezas no informativas ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "motivo"),
    [
        ("https://www.noticiasrcn.com/emisiones/emision-noticias-rcn-12-30-p-m-viernes-12-de-enero-de-2024-462845",
         NonNewsReason.EMISION),
        ("https://www.bluradio.com/bla-bla-blu/19-de-abril-de-2022-bla-bla-blu-programa-completo-pr30",
         NonNewsReason.EMISION),
        ("https://www.noticiascaracol.com/los-informantes/reviva-el-capitulo-de-los-informantes-pr30",
         NonNewsReason.EMISION),
        ("https://www.eltiempo.com/opinion/caricaturistas/caricatura-de-beto-barreto-123456",
         NonNewsReason.CARICATURA),
        ("https://www.eltiempo.com/vida/horoscopo-de-hoy-12-de-julio-123456",
         NonNewsReason.SERVICIO),
        ("https://www.bluradio.com/economia/juegos-de-azar/chontico-dia-resultado-del-ultimo-sorteo-hoy-jueves-17-de-julio-de-2025-so35",
         NonNewsReason.SERVICIO),
        ("https://www.eltiempo.com/colombia/loteria-de-bogota-resultados-y-numeros-ganadores-del-sorteo-del-9-de-enero-123456",
         NonNewsReason.SERVICIO),
        ("https://www.bluradio.com/regiones/pico-y-placa-en-bucaramanga-para-el-martes-8-de-abril-de-2025-rg10",
         NonNewsReason.SERVICIO),
        ("https://www.larepublica.co/economia/precios-del-dolar-y-del-petroleo-hoy-2-de-enero-3942567",
         NonNewsReason.INDICADOR),
        ("https://www.eltiempo.com/contenido-comercial/algo-patrocinado-123456",
         NonNewsReason.COMERCIAL),
        ("https://www.eltiempo.com/condolencias/aviso-de-condolencia-familia-perez-123456",
         NonNewsReason.OBITUARIO),
    ],
)
def test_no_noticias_se_marcan(url, motivo):
    assert derive_from_url(url).non_news_reason == motivo


@pytest.mark.parametrize(
    "url",
    [
        "https://www.noticiascaracol.com/politica/senado-aprueba-reforma-pensional-rg10",
        "https://www.larepublica.co/economia/el-dolar-cerro-al-alza-por-tensiones-comerciales-3942567",
        "https://www.noticiasrcn.com/deportes/momentos-de-tension-duro-golpe-video-831499",
        "https://www.eltiempo.com/deportes/asi-sera-el-sorteo-de-las-copas-libertadores-y-sudamericana-123456",
        "https://www.eltiempo.com/colombia/medellin/cambios-y-multas-en-el-pico-y-placa-de-medellin-123456",
        # Notas de video y obituarios de figuras públicas sí son noticias.
        "https://www.eltiempo.com/videos-eltiempo/corte-suprema-rechaza-intento-de-trump-3568248",
        "https://www.larepublica.co/obituarios/fallecio-el-papa-francisco-4114535",
    ],
)
def test_noticias_no_se_marcan(url):
    """Una noticia SOBRE el dólar no es el boletín diario del precio."""
    assert derive_from_url(url).non_news_reason is None


def test_seccion_extraida_se_normaliza_al_clasificar():
    assert classify_non_news("Emisiones", "Lo que sea") == NonNewsReason.EMISION


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
