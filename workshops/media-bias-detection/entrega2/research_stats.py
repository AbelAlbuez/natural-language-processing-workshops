import numpy as np
from scipy.stats import chi2_contingency, norm


def holm_adjust(p_values):
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError("P-values deben ser un vector finito en [0,1]")
    order = np.argsort(values)
    adjusted = np.minimum(1, np.maximum.accumulate(values[order] * (len(values) - np.arange(len(values)))))
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result


def chi_square_counts(table):
    observed = np.asarray(table)
    if observed.ndim != 2 or not np.isfinite(observed).all() or (observed < 0).any() or not np.equal(observed, np.floor(observed)).all():
        raise ValueError("La tabla requiere conteos enteros no negativos")
    if min(observed.shape) < 2 or (observed.sum(axis=0) == 0).any() or (observed.sum(axis=1) == 0).any():
        raise ValueError("La tabla requiere al menos dos filas/columnas sin margenes vacios")
    statistic, probability, degrees, expected = chi2_contingency(observed, correction=False)
    effect = np.sqrt(statistic / (observed.sum() * min(observed.shape[0] - 1, observed.shape[1] - 1)))
    return {
        "chi2": float(statistic), "p": float(probability), "dof": int(degrees),
        "cramers_v": float(effect), "n": int(observed.sum()),
        "expected_min": float(expected.min()), "expected_below5": int((expected < 5).sum()),
        "asymptotic_cells_ok": bool((expected >= 5).all()),
    }


def wilson_interval(successes, total, confidence=0.95):
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("Conteos binomiales invalidos")
    score = norm.ppf((1 + confidence) / 2)
    proportion = successes / total
    denominator = 1 + score ** 2 / total
    center = (proportion + score ** 2 / (2 * total)) / denominator
    radius = score * np.sqrt(proportion * (1 - proportion) / total + score ** 2 / (4 * total ** 2)) / denominator
    return float(max(0, center - radius)), float(min(1, center + radius))


def block_bootstrap_mean(values, repetitions=1000, block_length=3, seed=42):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("Serie no vacia y finita requerida")
    random = np.random.default_rng(seed)
    blocks = int(np.ceil(len(values) / block_length))
    starts = random.integers(0, len(values), size=(repetitions, blocks))
    indices = ((starts[:, :, None] + np.arange(block_length)) % len(values)).reshape(repetitions, -1)[:, :len(values)]
    means = values[indices].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return {"mean": float(values.mean()), "low": float(low), "high": float(high), "months": len(values)}