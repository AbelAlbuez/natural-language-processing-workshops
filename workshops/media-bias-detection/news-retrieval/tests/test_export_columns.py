"""Contrato de columnas del export.

No hay test de integración del export porque su consulta usa `date_trunc`, que
es de Postgres: verificarla exige el contenedor, no la suite unitaria. Lo que sí
se puede fijar aquí es el contrato de campos, que es donde estuvo el fallo real:
el export nació sin `content`, `description` ni `author`, de modo que todo el
texto extraído se quedaba en la base y nunca llegaba al análisis.
"""

from __future__ import annotations

from news_corpus.pipeline.export import COLUMNS, CONTENT_COLUMNS, METADATA_COLUMNS


def test_export_lleva_los_campos_que_exige_el_taller():
    """§24 del CLAUDE.md enumera el mínimo que debe conservar el dataset."""
    exigidos = {
        "article_id", "title", "description", "author", "url",
        "source_id", "published_date", "government_id", "topics", "provider",
    }
    assert exigidos <= set(COLUMNS)


def test_el_cuerpo_viaja_en_el_export():
    assert "content" in COLUMNS
    assert "content_hash" in COLUMNS


def test_no_content_solo_quita_el_cuerpo():
    """`--no-content` alivia el archivo, no empobrece la trazabilidad."""
    assert set(COLUMNS) - set(METADATA_COLUMNS) == set(CONTENT_COLUMNS)
    assert "content_chars" in METADATA_COLUMNS, (
        "sin la longitud no se pueden filtrar los artículos analizables "
        "sin volver a exportar el cuerpo entero"
    )


def test_las_marcas_de_procedencia_no_se_pierden():
    for campo in ("title_source", "date_precision", "archive_density_month",
                  "extraction_status"):
        assert campo in METADATA_COLUMNS
