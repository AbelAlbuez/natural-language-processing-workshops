"""Calibración del umbral con un caso sintético de 5 filas (4 respondibles y 1 no respondible)."""
import pytest

from scripts import calibrar_umbral as cu

RESP = [0.90, 0.88, 0.86, 0.84]  # scores máximos de las respondibles


def test_umbral_factible():
    p = cu.proponer_umbral(RESP, [0.83], min_respondidas=0.9)
    assert p["necesarias"] == 4                      # ceil(0,9 · 4)
    assert p["umbral_min_abstencion"] == 0.831       # estrictamente por encima de 0,83
    assert p["umbral_max_respuesta"] == 0.84         # la cuarta respondible
    assert p["factible"] and p["propuesta"] == 0.831
    e = p["con_umbral_min_abstencion"]
    assert (e["respondibles_respondidas"], e["no_respondibles_abstenidas"]) == (4, 1)


def test_umbral_no_factible():
    p = cu.proponer_umbral(RESP, [0.87], min_respondidas=0.9)
    assert p["umbral_min_abstencion"] == 0.871 and p["umbral_max_respuesta"] == 0.84
    assert not p["factible"] and p["propuesta"] is None
    e = p["con_umbral_min_abstencion"]
    assert (e["respondibles_respondidas"], e["no_respondibles_abstenidas"]) == (2, 1)


def test_umbral_exacto_no_abstiene():
    # Si el score de la no respondible coincide con un múltiplo del paso, el umbral debe superarlo.
    p = cu.proponer_umbral(RESP, [0.84], min_respondidas=0.75)
    assert p["umbral_min_abstencion"] == 0.841 and p["necesarias"] == 3
    assert p["factible"] and p["propuesta"] == 0.841


def test_evaluar_umbral_y_validaciones():
    e = cu.evaluar_umbral(RESP, [0.83], 0.85)
    assert (e["respondibles_respondidas"], e["respondibles"], e["no_respondibles_abstenidas"], e["no_respondibles"]) == (3, 4, 1, 1)
    with pytest.raises(ValueError):
        cu.proponer_umbral(RESP, [], 0.9)
