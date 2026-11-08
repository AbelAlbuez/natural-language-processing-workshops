import numpy as np
import pandas as pd
import pytest

from silver_analisis import etiquetas, pesos


def _planilla(ids, sesgado, doble):
    return pd.DataFrame({"id": ids, "doble": doble, "¿sesgado?": sesgado,
                         "tipo principal": [("Lenguaje cargado" if s == "Sí" else None) for s in sesgado],
                         "dirección": [("Desfavorable" if s == "Sí" else None) for s in sesgado],
                         "intensidad": None, "comentario": None, "nombre": "x"})


def _key(ids):
    return pd.DataFrame({"id": ids, "source_id": "el_tiempo", "government_id": "petro", "estrato": "S_resto",
                         "terminos_carga": "", "personaliza": False, "divergente": False})


def test_combinado_laxo_y_estricto_en_desacuerdo():
    ids = ["T1", "T2", "T3", "T4"]
    p1 = _planilla(["T1", "T2", "T3"], ["Sí", "Sí", "No"], ["Sí", "Sí", "No"])
    p2 = _planilla(["T1", "T2", "T4"], ["Sí", "No", "No se puede saber"], ["Sí", "Sí", "No"])
    muestra = pd.DataFrame({"id": ids, "titular": "t", "gobierno": "Petro"})
    lab = etiquetas(p1, p2, _key(ids), muestra).set_index(["definicion", "id"])["y"]
    assert lab["combinado_laxo", "T1"] == 1 and lab["combinado_estricto", "T1"] == 1   # acuerdo
    assert lab["combinado_laxo", "T2"] == 1 and lab["combinado_estricto", "T2"] == 0   # desacuerdo
    assert lab["combinado_laxo", "T3"] == 0                                              # simple
    assert np.isnan(lab["combinado_laxo", "T4"])                                         # «No se puede saber»
    assert lab["humano", "T2"] == 1 and lab["ia", "T2"] == 0


def test_pesos_dentro_de_la_definicion():
    d = pd.DataFrame({"id": ["a", "b", "c"], "source_id": "el_tiempo", "government_id": "petro",
                      "estrato": ["S_resto", "S_resto", "E_lexico"]})
    pe = pd.DataFrame({"source_id": "el_tiempo", "government_id": "petro", "estrato": ["S_resto", "E_lexico"],
                       "N_h": [1000, 10]})
    w = pesos(d, pe)
    assert w.tolist() == pytest.approx([500, 500, 10])
