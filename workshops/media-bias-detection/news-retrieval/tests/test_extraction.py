"""Tests del parser de artículos."""

from __future__ import annotations

from news_corpus.pipeline.extraction import is_boilerplate_title, parse_article

# Forma real de una página de archivo de El Tiempo: og:title y <title> no
# coinciden — <title> trae la versión corta de la pestaña.
HTML_ARTICULO = """<html><head>
<title>Frustan robo de bebé en Cali</title>
<meta property="og:title" content="Policía rescata a bebé robado a una mujer en ladera del sur de Cali"/>
<meta property="og:description" content="El caso ocurrió en el barrio Siloé."/>
<meta property="article:published_time" content="2016-03-31T17:16:21-05:00"/>
<meta property="article:section" content="Colombia"/>
<meta name="author" content="Redacción El Tiempo"/>
<script type="application/ld+json">
{"@type":"NewsArticle","headline":"Polic\\u00eda rescata a beb\\u00e9",
 "datePublished":"2016-03-31T17:16:21-05:00"}
</script>
</head><body><h1>Policía rescata a bebé robado</h1>
<article><p>El hecho ocurrió la tarde del jueves en la ladera de Cali.</p></article>
</body></html>"""


def test_prefiere_og_title_sobre_title():
    """<title> suele ser la versión abreviada para la pestaña del navegador."""
    d = parse_article(HTML_ARTICULO)
    assert d.title == "Policía rescata a bebé robado a una mujer en ladera del sur de Cali"


def test_conserva_las_tildes():
    """Es la ventaja principal frente al título derivado del slug."""
    d = parse_article(HTML_ARTICULO)
    assert "í" in d.title and "é" in d.title


def test_extrae_fecha_autor_descripcion_y_seccion():
    d = parse_article(HTML_ARTICULO)
    assert d.published_at is not None
    assert d.published_at.date().isoformat() == "2016-03-31"
    assert d.author == "Redacción El Tiempo"
    assert d.description == "El caso ocurrió en el barrio Siloé."
    assert d.section == "Colombia"


def test_cae_a_h1_sin_og_title():
    html = HTML_ARTICULO.replace(
        '<meta property="og:title" content="Policía rescata a bebé robado a una mujer '
        'en ladera del sur de Cali"/>',
        "",
    )
    assert parse_article(html).title == "Policía rescata a bebé robado"


def test_cae_a_json_ld_sin_og_ni_h1():
    html = HTML_ARTICULO.replace(
        '<meta property="og:title" content="Policía rescata a bebé robado a una mujer '
        'en ladera del sur de Cali"/>',
        "",
    ).replace("<h1>Policía rescata a bebé robado</h1>", "")
    assert parse_article(html).title == "Policía rescata a bebé"


def test_fecha_desde_json_ld_si_falta_el_meta():
    html = HTML_ARTICULO.replace(
        '<meta property="article:published_time" content="2016-03-31T17:16:21-05:00"/>', ""
    )
    d = parse_article(html)
    assert d.published_at is not None
    assert d.published_at.date().isoformat() == "2016-03-31"


def test_pagina_sin_titulo_no_inventa_uno():
    assert parse_article("<html><head></head><body><p>hola</p></body></html>").title is None


def test_rechaza_titulos_de_navegacion():
    """El Tiempo sirve páginas de archivo cuyo og:title es 'Síganos'. No es un
    fallo del parser: es la página. Preferimos no tener título a registrar
    un elemento de navegación como titular."""
    html = '<html><head><meta property="og:title" content="Síganos"/></head><body></body></html>'
    assert parse_article(html).title is None


def test_deteccion_de_boilerplate():
    assert is_boilerplate_title("Síganos")
    assert is_boilerplate_title("SUSCRÍBASE")
    assert is_boilerplate_title("Portada")
    # Un titular corto pero real no debe caer en el filtro.
    assert not is_boilerplate_title("Hace 25 años")
    assert not is_boilerplate_title("Praco Didacol ampliará plan de inversiones")


def test_html_roto_no_revienta():
    for basura in ["", "<html", "no es html", "<html><head><title></title></head>"]:
        assert parse_article(basura).title is None


# ── limpieza del cuerpo ──────────────────────────────────────────────────────


def test_clean_content_quita_lineas_de_interfaz():
    from news_corpus.pipeline.extraction import clean_content

    sucio = "Primer párrafo.\nPublicidad\nSegundo párrafo.\nSíguenos en:"
    assert clean_content(sucio) == "Primer párrafo.\nSegundo párrafo."


def test_clean_content_no_recorta_dentro_de_una_frase():
    """La palabra dentro de un párrafo es contenido; la línea suelta no lo es."""
    from news_corpus.pipeline.extraction import clean_content

    texto = "La publicidad engañosa fue sancionada por la SIC."
    assert clean_content(texto) == texto


def test_clean_content_devuelve_none_cuando_todo_era_interfaz():
    """Las notas que sólo son audio dejan un cuerpo que no es cuerpo.

    Verificado en Blu Radio 2013: la página completa aporta 'Actualizado: 28 de
    abr, 2016' y 'Publicidad'. Guardar eso como texto del artículo haría que un
    conteo de palabras del medio midiera su plantilla.
    """
    from news_corpus.pipeline.extraction import clean_content

    assert clean_content("Actualizado: 28 de abr, 2016\nPublicidad") is None
    assert clean_content("") is None
    assert clean_content(None) is None


def test_clean_content_colapsa_los_huecos_que_deja():
    from news_corpus.pipeline.extraction import clean_content

    sucio = "Uno.\nPublicidad\n\nLea también: otra nota\n\nDos."
    assert clean_content(sucio) == "Uno.\n\nDos."


def test_parse_article_entrega_el_cuerpo_ya_limpio():
    from news_corpus.pipeline.extraction import parse_article

    html = (
        '<html><head><meta property="og:title" content="Un titular real">'
        "</head><body><article><p>El hecho ocurrió el martes en Bogotá y dejó "
        "tres personas heridas según las autoridades locales.</p>"
        "<p>Publicidad</p></article></body></html>"
    )
    resultado = parse_article(html)
    assert resultado.title == "Un titular real"
    if resultado.content:  # trafilatura es opcional
        assert "Publicidad" not in resultado.content.split("\n")


def test_retry_no_se_filtra_por_titulo_ausente():
    """`--retry` debe encontrar los fallos de red aunque ya tengan título.

    Los artículos que fallan por red suelen conservar el título derivado del
    slug, así que exigir `title IS NULL` en el reintento dejaba los fallos sin
    reintentar y `--retry` respondía 'Nada pendiente'.
    """
    import inspect

    from news_corpus.pipeline import extraction

    fuente = inspect.getsource(extraction.extract_pending)
    tras_retry = fuente.split("if retry_failed:", 1)[1].split("else:", 1)[0]
    assert "only_missing_title" not in tras_retry
