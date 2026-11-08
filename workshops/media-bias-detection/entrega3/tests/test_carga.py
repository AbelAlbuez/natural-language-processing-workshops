import numpy as np
import pandas as pd

from carga import (cambio_gobiernos, coincidencias, compilar, detectar, emparejado, eventos_longitud_similar,
                   indicadores, leer_lexico, matriz_entradas, menciona_gobierno)
from core import normalize

LEX = compilar(leer_lexico())
POR_ID = {e.id: e for e in LEX}


def _det(titulo):
    return detectar(normalize(titulo), LEX)


# ── léxico ───────────────────────────────────────────────────────────────────


def test_lexico_valido_y_sin_tildes():
    tab = leer_lexico()
    assert tab["id"].is_unique
    for col in ("formas", "excluir"):
        assert not tab[col].str.contains("[áéíóúñü]").any()
    assert {"juicio", "atribucion_cargada", "atribucion_neutra"} <= set(tab["tipo"])
    assert set(tab["origen"]) <= {"a_priori", "tras_datos"}


def test_deteccion_basica_con_variantes():
    assert "polemica" in _det("Polémica por el decreto del Gobierno")
    assert "polemica" in _det("El polémico nombramiento en Ecopetrol")
    assert "arremete" in _det("Petro arremetió contra la Fiscalía")
    assert "fracaso" in _det("Fracasó la consulta anticorrupción")
    assert "historico" in _det("Histórico acuerdo en la OTAN")


def test_limites_de_palabra():
    # «ira» (verbo «irá») no cuenta; «crisis» no se confunde con otra palabra
    assert "furia" not in _det("La iniciativa irá al Congreso")
    assert not _det("Choco y Cauca bajo lluvias")      # Chocó no es «choque»


def test_exclusiones_de_contexto():
    assert "golpe" not in _det("Alerta por golpe de calor en Barranquilla")
    assert "golpe" not in _det("Maduro denuncia intento de golpe de Estado")
    assert "golpe" in _det("Duro golpe a la reforma tributaria")
    assert "historico" not in _det("Asamblea del Pacto Histórico define listas")
    assert "historico" not in _det("Cierran vías en el centro histórico de Cartagena")
    assert "historico" not in _det("El dólar llega a máximo histórico")
    assert "alivio" not in _det("Coalición Centro Esperanza elige candidato")
    assert "grave" not in _det("Grave accidente en la vía al Llano")
    assert "grave" in _det("Grave denuncia de la ONU sobre masacres")
    assert "denuncia" not in _det("Corte archiva denuncia contra el senador")
    assert "denuncia" in _det("Alcalde denuncia amenazas del ELN")
    assert "logro" not in _det("No se logró acuerdo con el paro")
    assert "acusa" not in _det("Fiscalía acusa a tres policías por homicidio")
    assert "duro" not in _det("El cese al fuego no duró un día")


def test_concesion_solo_con_que():
    assert "admite" not in _det("Consejo de Estado admite demanda contra elección")
    assert "admite" in _det("Ministro admite que hubo errores")
    assert "reconoce" not in _det("La UE reconoce a Guaidó")
    assert "reconoce" in _det("Gobierno reconoce que fue un error")


def test_entradas_desactivadas_no_se_detectan():
    tab = leer_lexico()
    for i in tab.loc[tab["activa"] == "no", "id"]:
        assert i not in POR_ID
    assert "positivo" not in _det("Juicio por falsos positivos")


def test_coincidencia_anulada_solo_si_queda_dentro_del_contexto():
    e = POR_ID["golpe"]
    t = normalize("golpe de calor y duro golpe a la economia")
    ms = coincidencias(t, e)
    assert len(ms) == 1 and ms[0].start() > 10   # sólo el segundo «golpe»


# ── indicadores ──────────────────────────────────────────────────────────────


def test_indicadores_polaridad_y_atribucion():
    titulos = ["Petro arremete contra el fiscal", "Gobierno celebra logro histórico", "Duque dijo que habrá diálogo",
               "Contundente mensaje del ministro", "Reunión del gabinete"]
    E = matriz_entradas([normalize(t) for t in titulos], LEX)
    I = indicadores(E, LEX)
    assert I["negativa"].tolist() == [True, False, False, False, False]
    assert I["positiva"].tolist() == [False, True, False, False, False]
    assert I["carga"].tolist() == [True, True, False, True, False]   # el intensificador cuenta como carga
    assert I["neto"].tolist() == [1, -1, 0, 0, 0]
    assert I["atrib_cargada"].tolist() == [True, True, False, False, False]
    assert I["atrib_neutra"].tolist() == [False, False, True, False, False]
    # la atribución neutra no es carga
    assert not I.loc[2, "carga"]


def test_quitar_entradas():
    E = matriz_entradas([normalize("Polémica y escándalo en el Congreso")], LEX)
    assert indicadores(E, LEX)["negativa"].iat[0]
    assert indicadores(E, LEX, quitar=["polemica"])["negativa"].iat[0]
    assert not indicadores(E, LEX, quitar=["polemica", "escandalo"])["negativa"].iat[0]


def test_mencion_gobierno_simetrica():
    t = [normalize("Polémica por decreto del Gobierno Petro"), normalize("Polémica por decreto del Gobierno Duque")]
    assert menciona_gobierno(t, ["petro", "duque"]).tolist() == [True, True]
    # el apellido del OTRO presidente no cuenta como mención del gobierno de turno
    assert menciona_gobierno([normalize("Duque critica la reforma")], ["petro"]).tolist() == [False]
    assert menciona_gobierno([normalize("Petro critica la reforma")], ["petro"]).tolist() == [True]


# ── diseño emparejado ────────────────────────────────────────────────────────


def _meta(filas):
    return pd.DataFrame(filas, columns=["event_id", "source_id"])


def test_emparejado_compara_dentro_del_evento():
    # Evento 1: a sin carga; b y c con carga (½ cada uno → otros = 1). Evento 2: a con carga; b sin.
    # Evento 3 no tiene al medio a y no debe contar.
    meta = _meta([(1, "a"), (1, "b"), (1, "c"), (2, "a"), (2, "b"), (3, "b"), (3, "c")])
    M = pd.DataFrame({"negativa": [0, 1, 1, 1, 0, 1, 1]}, dtype=float)
    t, d = emparejado(meta, M, "a", reps=200)
    r = t.set_index("indicador").loc["negativa"]
    assert r.eventos == 2
    assert np.isclose(r.prop_medio, 0.5) and np.isclose(r.prop_otros, 0.5) and np.isclose(r.diferencia, 0)


def test_emparejado_agenda_comun_da_cero():
    # Un hecho negativo produce carga en TODOS los medios: la diferencia emparejada es 0
    # aunque el nivel sea alto.
    filas, vals = [], []
    for e in range(50):
        for m in "abc":
            filas.append((e, m))
            vals.append(1.0 if e < 30 else 0.0)
    t, _ = emparejado(_meta(filas), pd.DataFrame({"negativa": vals}), "a", reps=200)
    r = t.iloc[0]
    assert np.isclose(r.prop_medio, 0.6) and np.isclose(r.diferencia, 0)
    assert r.ic_bajo == 0 and r.ic_alto == 0


def test_emparejado_excluir_y_simetria():
    meta = _meta([(1, "a"), (1, "rcn"), (2, "a"), (2, "b")])
    M = pd.DataFrame({"x": [1.0, 0.0, 0.0, 1.0]})
    t, _ = emparejado(meta, M, "a", excluir=("rcn",), reps=100)
    assert t.iloc[0].eventos == 1 and np.isclose(t.iloc[0].diferencia, -1)
    # intercambiar los papeles invierte el signo
    meta2 = _meta([(1, "a"), (1, "b"), (2, "a"), (2, "b")])
    M2 = pd.DataFrame({"x": [1.0, 0.0, 1.0, 1.0]})
    da = emparejado(meta2, M2, "a", reps=100)[0].iloc[0].diferencia
    db = emparejado(meta2, M2, "b", reps=100)[0].iloc[0].diferencia
    assert np.isclose(da, -db) and np.isclose(da, 0.5)


def test_razon_atribucion_cargada():
    meta = _meta([(1, "a"), (1, "b"), (2, "a"), (2, "b")])
    M = pd.DataFrame({"atrib_cargada": [1.0, 0, 0, 0], "atrib_alguna": [1.0, 1, 1, 1]})
    t, _ = emparejado(meta, M, "a", reps=100, razones={"r": ("atrib_cargada", "atrib_alguna")})
    r = t.set_index("indicador").loc["r"]
    assert np.isclose(r.prop_medio, 0.5) and np.isclose(r.prop_otros, 0.0)


def test_cambio_gobiernos_resta_diferencias():
    tab = pd.DataFrame([
        {"medio": "a", "gobierno": "duque", "indicador": "x", "diferencia": 0.01, "dif_relativa": 0.1,
         "prop_medio": 0.11, "prop_otros": 0.10},
        {"medio": "a", "gobierno": "petro", "indicador": "x", "diferencia": 0.04, "dif_relativa": 0.4,
         "prop_medio": 0.14, "prop_otros": 0.10}])
    draws = {("a", "duque", "x"): np.full(100, 0.01), ("a", "petro", "x"): np.full(100, 0.04)}
    c = cambio_gobiernos(tab, draws, [("a", "x")]).iloc[0]
    assert np.isclose(c.cambio, 0.03) and np.isclose(c.ic_bajo, 0.03) and np.isclose(c.cambio_relativo, 0.3)


def test_longitud_similar():
    base = pd.DataFrame({"event_id": [1, 1, 1, 2, 2], "source_id": ["a", "b", "c", "a", "b"],
                         "n_palabras": [10, 11, 13, 6, 12]})
    assert eventos_longitud_similar(base, "a").tolist() == [1]   # evento 2: 6 frente a 12
