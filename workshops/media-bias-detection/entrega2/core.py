import math
import re
import unicodedata
from collections import Counter


def fold(text):
    return "".join(
        character for character in unicodedata.normalize("NFD", str(text).lower())
        if unicodedata.category(character) != "Mn"
    )


def normalize(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    return " ".join(re.findall(r"[a-z]+", fold(text)))


def tokenize(text, stop_words=()):
    return [word for word in normalize(text).split() if len(word) > 2 and word not in stop_words]


def keyword_pattern(keywords):
    normalized = [normalize(keyword) for keyword in keywords]
    terms = [re.escape(keyword) for keyword in normalized if keyword]
    if not terms:
        raise ValueError("Se necesita al menos una palabra clave no vacia")
    return r"\b(?:" + "|".join(terms) + r")\b"


def ttr(tokens):
    return len(set(tokens)) / len(tokens) if tokens else 0.0


def msttr(tokens, window=50):
    if window < 1:
        raise ValueError("La ventana debe ser positiva")
    if len(tokens) < window:
        return ttr(tokens)
    segments = len(tokens) // window
    return sum(ttr(tokens[start:start + window]) for start in range(0, segments * window, window)) / segments


def yules_k(tokens):
    if not tokens:
        return 0.0
    frequencies = Counter(tokens)
    return 10000.0 * sum(count * (count - 1) for count in frequencies.values()) / len(tokens) ** 2


def counter_metrics(frequencies):
    total = sum(frequencies.values())
    return {
        "tokens": total,
        "vocabulario": len(frequencies),
        "ttr_agregado": len(frequencies) / total if total else math.nan,
        "yule_k_agregado": 10000.0 * sum(count * (count - 1) for count in frequencies.values()) / total ** 2 if total else math.nan,
    }


def ngrams(tokens, size):
    return [" ".join(tokens[start:start + size]) for start in range(len(tokens) - size + 1)]