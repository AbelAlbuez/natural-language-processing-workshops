"""Pruebas de app/solr_backend.py sin Solr real: se sustituye la capa HTTP (_llamar)."""
from unittest import mock

import pytest

from app import solr_backend as sb


def test_limpiar_consulta_quita_sintaxis_de_solr():
    assert sb.limpiar_consulta('a+b "c" (d) e:f /g') == "a b c d e f g"
    assert sb.limpiar_consulta("  ¿Qué   es?  ") == "¿Qué es"
    assert sb.limpiar_consulta(None) == ""


def test_documento_solr_enruta_el_texto_por_idioma():
    es = sb.a_documento_solr({"chunk_id": "c1", "document_id": "d", "text": "hola", "lang": "es"})
    en = sb.a_documento_solr({"chunk_id": "c2", "document_id": "d", "text": "hello", "lang": "en"})
    assert es["id"] == "c1" and es["text_es"] == "hola" and "text_en" not in es
    assert en["text_en"] == "hello" and "text_es" not in en
    largo = sb.a_documento_solr({"chunk_id": "c3", "document_id": "d", "url": "u" * 5000, "lang": "es"})
    assert len(largo["url"]) == 2000


def test_retrieve_ordena_y_mapea_campos():
    respuesta = {"response": {"docs": [
        {"id": "b", "score": 1.5, "document_id": "d2", "lang": "en", "text_en": "second", "token_count": 7},
        {"id": "a", "score": 9.0, "document_id": "d1", "lang": "es", "text_es": "primero", "token_count": 5}]}}
    with mock.patch.object(sb, "_llamar", return_value=respuesta) as llamar:
        frag = sb.retrieve("¿Dónde (Cali)?", 2, url="http://x/solr", core="c")
    assert [f["chunk_id"] for f in frag] == ["a", "b"]
    assert frag[0]["text"] == "primero" and frag[1]["text"] == "second" and frag[0]["token_count"] == 5
    datos = llamar.call_args.kwargs["data"]
    assert datos["q"] == "¿Dónde Cali"
    assert datos["rows"] == 2 and datos["defType"] == "edismax" and datos["qf"] == "text_es text_en"


def test_retrieve_con_consulta_vacia_no_llama_a_solr():
    with mock.patch.object(sb, "_llamar") as llamar:
        assert sb.retrieve("+-()", 3, url="u", core="c") == []
    llamar.assert_not_called()


def test_ensure_schema_es_idempotente():
    llamadas = []

    def falso(metodo, url, **kw):
        llamadas.append((metodo, url))
        if metodo == "GET":
            return {"fields": [{"name": "document_id"}, {"name": "lang"}]}
        return {}

    with mock.patch.object(sb, "_llamar", side_effect=falso):
        creados = sb.ensure_schema("http://x/solr", "c")
    assert "document_id" not in creados and "lang" not in creados and "text_es" in creados
    assert sum(1 for m, _ in llamadas if m == "POST") == len(creados)


def test_health_degrada_si_solr_falla():
    with mock.patch.object(sb, "_llamar", side_effect=sb.SolrUnavailable("caído")):
        h = sb.health("http://x/solr", "c")
    assert h["ok"] is False and "caído" in h["error"]
