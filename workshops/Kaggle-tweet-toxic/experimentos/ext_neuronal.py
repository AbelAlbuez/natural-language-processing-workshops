"""E10a — Redes neuronales entrenadas desde cero (PyTorch, CPU) como modelos base para el stacking.

Al importar este módulo se registran en `toxic_base`:
- el bloque `seq`: secuencias de índices de palabras y de caracteres (vocabulario ajustado SOLO con idx_a);
- los modelos `NN-BiGRU` (palabras), `NN-CharCNN` (caracteres) y `NN-Mix` (las dos ramas juntas).

Nada es preentrenado: los embeddings se inicializan al azar y se aprenden con el train de cada fold.
El early stopping usa una partición interna (15 %) del train del fold; nunca la partición de validación ni el test.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS', '3')
import re
from collections import Counter
import numpy as np
from scipy import sparse
from sklearn.model_selection import StratifiedShuffleSplit
import torch
import torch.nn as nn
import toxic_base as tb

torch.set_num_threads(3)

LW, LC = 60, 280            # longitud máxima en palabras y en caracteres
MIN_FREQ = 2                # mínimo de apariciones (en idx_a) para entrar al vocabulario
RE_PAL = re.compile(r'\b\w+\b')
PAD, UNK = 0, 1

# Hiperparámetros del entrenamiento (constantes del módulo: no entran en el cfg, así no tocan la caché de los demás)
NN = dict(epocas=40, paciencia=5, lote=32, lr=2e-3, wd=1e-4, dropout=0.5, n_init=3, val_frac=0.15, balanceado=True)


def _vocab(seqs):
    c = Counter(t for s in seqs for t in s)
    return {t: i + 2 for i, t in enumerate(sorted(t for t, n in c.items() if n >= MIN_FREQ))}

def _indices(seqs, voc, L):
    M = np.zeros((len(seqs), L), dtype=np.int64)
    for i, s in enumerate(seqs):
        ids = [voc.get(t, UNK) for t in s][:L]
        M[i, :len(ids)] = ids
    return M

def bloque_seq(d, idx_a, idx_b, cfg):
    """Matriz (n, LW + LC + 2) de enteros: índices de palabras, índices de caracteres (0 = relleno) y, en las
    2 últimas columnas, los tamaños de los vocabularios (constantes) para que el modelo dimensione sus embeddings."""
    ta, tb_ = tb._textos(d, idx_a, idx_b)
    wa = [RE_PAL.findall(t) for t in ta]; wb = [RE_PAL.findall(t) for t in tb_]
    ca = [list(t) for t in ta];         cb = [list(t) for t in tb_]
    vw, vc = _vocab(wa), _vocab(ca)
    A = np.hstack([_indices(wa, vw, LW), _indices(ca, vc, LC)])
    B = np.hstack([_indices(wb, vw, LW), _indices(cb, vc, LC)])
    A = np.hstack([A, np.full((len(A), 2), 0)]); B = np.hstack([B, np.full((len(B), 2), 0)])
    A[:, -2], A[:, -1] = len(vw) + 2, len(vc) + 2
    B[:, -2], B[:, -1] = len(vw) + 2, len(vc) + 2
    return sparse.csr_matrix(A), sparse.csr_matrix(B)
tb.BLOQUES['seq'] = bloque_seq


class Red(nn.Module):
    """Rama de palabras: embedding 64 -> BiGRU 2x48 -> max y media. Rama de caracteres: embedding 24 ->
    convoluciones de ancho 3/5/7 (64 filtros c/u) -> max. Concatenación -> dropout -> 3 salidas sigmoides."""
    def __init__(self, nw, nc, ramas, dropout, n_lex=0):
        super().__init__()
        self.ramas = ramas
        dim = n_lex                            # variables de léxico (opcionales) entran directo a la capa densa
        if 'w' in ramas:
            self.ew = nn.Embedding(nw, 64, padding_idx=PAD)
            self.gru = nn.GRU(64, 48, batch_first=True, bidirectional=True)
            dim += 4 * 48
        if 'e' in ramas:                       # bolsa de embeddings (estilo fastText): sin orden
            self.ee = nn.Embedding(nw, 96, padding_idx=PAD)
            dim += 2 * 96
        if 'c' in ramas:
            self.ec = nn.Embedding(nc, 24, padding_idx=PAD)
            self.convs = nn.ModuleList([nn.Conv1d(24, 64, k, padding=k // 2) for k in (3, 5, 7)])
            dim += 3 * 64
        self.drop_e = nn.Dropout(0.25)
        self.drop = nn.Dropout(dropout)
        self.out = nn.Sequential(nn.Linear(dim, 64), nn.ReLU(), nn.Dropout(dropout), nn.Linear(64, 3))

    def forward(self, xw, xc, xl=None):
        h = [] if xl is None else [xl]
        if 'w' in self.ramas:
            m = (xw != PAD).unsqueeze(-1).float()
            o, _ = self.gru(self.drop_e(self.ew(xw)))
            h += [(o - 1e4 * (1 - m)).max(1).values, (o * m).sum(1) / m.sum(1).clamp(min=1)]
        if 'e' in self.ramas:
            m = (xw != PAD).unsqueeze(-1).float()
            e = self.drop_e(self.ee(xw))
            h += [(e - 1e4 * (1 - m)).max(1).values, (e * m).sum(1) / m.sum(1).clamp(min=1)]
        if 'c' in self.ramas:
            m = (xc != PAD).unsqueeze(1).float()
            e = self.drop_e(self.ec(xc)).transpose(1, 2)
            h += [(torch.relu(cv(e)) - 1e4 * (1 - m)).max(2).values for cv in self.convs]
        return self.out(self.drop(torch.cat(h, 1)))


def _entrenar(Xw, Xc, Xl, Y, nw, nc, ramas, semilla, combo):
    torch.manual_seed(semilla); np.random.seed(semilla)
    sss = StratifiedShuffleSplit(1, test_size=NN['val_frac'], random_state=semilla)
    itr, iva = next(sss.split(Xw, combo))
    red = Red(nw, nc, ramas, NN['dropout'], Xl.shape[1])
    opt = torch.optim.AdamW(red.parameters(), lr=NN['lr'], weight_decay=NN['wd'])
    pos = Y[itr].mean(0).clip(0.05, 0.95)
    perdida = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((1 - pos) / pos, dtype=torch.float32)) \
        if NN['balanceado'] else nn.BCEWithLogitsLoss()
    Xw_t, Xc_t, Y_t = torch.from_numpy(Xw), torch.from_numpy(Xc), torch.from_numpy(Y).float()
    Xl_t = torch.from_numpy(Xl).float()
    g = torch.Generator().manual_seed(semilla)
    mejor, estado, sin_mejora = np.inf, None, 0
    for ep in range(NN['epocas']):
        red.train()
        orden = torch.from_numpy(itr)[torch.randperm(len(itr), generator=g)]
        for i in range(0, len(orden), NN['lote']):
            b = orden[i:i + NN['lote']]
            opt.zero_grad()
            l = perdida(red(Xw_t[b], Xc_t[b], Xl_t[b]), Y_t[b])
            l.backward()
            nn.utils.clip_grad_norm_(red.parameters(), 5.0)
            opt.step()
        red.eval()
        with torch.no_grad():
            lv = perdida(red(Xw_t[iva], Xc_t[iva], Xl_t[iva]), Y_t[iva]).item()
        if lv < mejor - 1e-4:
            mejor, sin_mejora = lv, 0
            estado = {k: v.clone() for k, v in red.state_dict().items()}
        else:
            sin_mejora += 1
            if sin_mejora >= NN['paciencia']:
                break
    red.load_state_dict(estado)
    red.eval()
    return red


def nn_fp(ramas):
    def fp(Xa, Ya, combo_a, Xb, cfg):
        Xa, Xb = Xa.toarray(), Xb.toarray()
        S = LW + LC + 2                        # columnas del bloque seq; lo que sigue es léxico (si se pidió)
        A, B = Xa[:, :S].astype(np.int64), Xb[:, :S].astype(np.int64)
        La, Lb = Xa[:, S:] / max(cfg['PESO_LEX'], 1e-9), Xb[:, S:] / max(cfg['PESO_LEX'], 1e-9)
        nw, nc = int(A[0, -2]), int(A[0, -1])
        Aw, Ac, Bw, Bc = A[:, :LW], A[:, LW:LW + LC], B[:, :LW], B[:, LW:LW + LC]
        Ps = []
        for k in range(NN['n_init']):
            red = _entrenar(Aw, Ac, La, Ya, nw, nc, ramas, 1000 + k, combo_a)
            with torch.no_grad():
                Ps.append(torch.sigmoid(red(torch.from_numpy(Bw), torch.from_numpy(Bc), torch.from_numpy(Lb).float())).numpy())
        return np.mean(Ps, 0)
    return fp

tb.MODELOS['NN-BiGRU'] = dict(bloques=['seq'], fit_predict=nn_fp('w'))
tb.MODELOS['NN-CharCNN'] = dict(bloques=['seq'], fit_predict=nn_fp('c'))
tb.MODELOS['NN-BolsaEmb'] = dict(bloques=['seq'], fit_predict=nn_fp('e'))
tb.MODELOS['NN-Mix'] = dict(bloques=['seq'], fit_predict=nn_fp('wc'))
tb.MODELOS['NN-BiGRU-lex'] = dict(bloques=['seq', 'lex'], fit_predict=nn_fp('w'))
tb.MODELOS['NN-BolsaEmb-lex'] = dict(bloques=['seq', 'lex'], fit_predict=nn_fp('e'))
