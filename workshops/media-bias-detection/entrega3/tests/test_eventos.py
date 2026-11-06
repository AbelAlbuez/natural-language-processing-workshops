import numpy as np

from eventos import attach_followups, build_events, candidate_edges, reciprocal_pairs, template_mask


def _unit(*rows):
    m = np.array(rows, dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def test_candidatos_solo_de_otros_medios_y_dentro_de_la_ventana():
    # 0 y 1 son del mismo medio e idénticos; 2 es de otro medio pero 5 días después.
    emb = _unit([1, 0], [1, 0], [1, 0], [1, 0.05])
    media = np.array([0, 0, 1, 2])
    day = np.array([0, 0, 5, 1])
    i, j, s, best_sim, best_idx = candidate_edges(emb, day, media, ventana=2, sim_min=0.5)
    pares = set(zip(i.tolist(), j.tolist()))
    assert (0, 1) not in pares          # mismo medio
    assert (0, 2) not in pares          # fuera de la ventana
    assert {(0, 3), (1, 3)} <= pares    # otro medio, 1 día
    assert np.isnan(best_sim[0, 0]) and best_idx[0, 0] == -1  # nunca su propio medio
    assert best_idx[0, 2] == 3 and best_idx[0, 1] == -1


def test_reciprocidad():
    # Para 0 (medio 0) el más parecido del medio 1 es 1; para 1 el más parecido del medio 0 es 2, no 0.
    best_idx = np.array([[-1, 1], [2, -1], [-1, 1]])
    best_sim = np.array([[np.nan, 0.8], [0.9, np.nan], [np.nan, 0.9]], dtype=np.float32)
    media = np.array([0, 1, 0])
    i, j, s = reciprocal_pairs(best_idx, best_sim, media)
    assert list(zip(i.tolist(), j.tolist())) == [(1, 2)]
    assert s[0] == np.float32(0.9)


def test_el_encadenamiento_no_une_dos_hechos_distintos():
    # Hecho A: 0 (medio 0) y 1 (medio 1). Hecho B: 2 (medio 2) y 3 (medio 0). Un puente 1~2
    # (parecido intermedio) los encadena en una componente con dos titulares del medio 0.
    emb = _unit([1, 0, 0], [0.9, 0.44, 0], [0.44, 0.9, 0], [0, 1, 0])
    media = np.array([0, 1, 2, 0])
    day = np.zeros(4, dtype=int)
    pi, pj = np.array([0, 1, 2]), np.array([1, 2, 3])
    psim = (emb[pi] * emb[pj]).sum(axis=1)
    events, stats = build_events(emb, day, media, pi, pj, psim, umbral=0.75, margen=0.10)
    assert stats["componentes"] == 1 and stats["componentes_partidas"] == 1
    cores = [set(e["core"].tolist()) for e in events]
    assert not any({0, 3} <= c for c in cores)   # los dos titulares del medio 0 no quedan juntos
    assert all(len(np.unique(media[list(c)])) == len(c) for c in cores)  # un titular por medio


def test_seguimiento_solo_del_mismo_medio_y_cerca_del_evento():
    emb = _unit([1, 0], [1, 0.02], [1, 0.03], [1, 0.03], [1, 0.03])
    media = np.array([0, 1, 0, 2, 0])
    day = np.array([10, 10, 11, 11, 30])
    events, _ = build_events(emb, day, media, np.array([0]), np.array([1]), np.array([0.99]), umbral=0.75)
    taken = np.zeros(5, dtype=bool)
    taken[events[0]["core"]] = True
    idx, ev, sim = attach_followups(emb, day, media, events, umbral=0.75, ventana=2, taken=taken)
    assert idx.tolist() == [2]   # 3 es de un medio que no está en el evento; 4 está lejos en el tiempo
    assert ev.tolist() == [0] and sim[0] > 0.75


def test_plantillas_masivas_del_mismo_medio_y_dia():
    rng = np.random.default_rng(0)
    base = rng.normal(size=8)
    plantilla = base + rng.normal(scale=0.01, size=(12, 8))     # 12 casi idénticos, medio 0, día 3
    otros = rng.normal(size=(5, 8))                              # distintos entre sí
    emb = np.vstack([plantilla, otros, plantilla[:3]])
    emb = (emb / np.linalg.norm(emb, axis=1, keepdims=True)).astype(np.float32)
    media = np.array([0] * 12 + [0] * 5 + [1] * 3)               # 3 copias en otro medio: no cuentan
    day = np.array([3] * 12 + [3] * 5 + [3] * 3)
    mask = template_mask(emb, day, media, sim=0.9, min_group=10)
    assert mask[:12].all() and not mask[12:].any()
