"""Normalización de URLs y hashing — base de la deduplicación (§17)."""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Parámetros de campaña y de sesión: no identifican el artículo.
_TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "_ga", "gclid", "fbclid")
_TRACKING_EXACT = {
    "cid", "ref", "source", "origin", "share", "amp", "outputtype",
    "s_cid", "ncid", "smid", "partner",
}


def strip_tracking(query: str) -> str:
    kept = [
        (k, v)
        for k, v in parse_qsl(query, keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_EXACT
    ]
    kept.sort()  # orden estable: ?a=1&b=2 y ?b=2&a=1 son la misma URL
    return urlencode(kept)


def normalize_url(url: str) -> str:
    """Forma canónica para comparar dos URLs.

    Deliberadamente NO se toca el path más allá de quitar la barra final: en
    estos medios el path identifica el artículo y alterarlo perdería registros.
    """
    parts = urlsplit(url.strip())

    scheme = parts.scheme.lower() or "https"
    if scheme == "http":
        scheme = "https"  # el mismo artículo servido por http y https es uno solo

    netloc = parts.netloc.lower().removeprefix("www.")
    if netloc.endswith(":80") or netloc.endswith(":443"):
        netloc = netloc.rsplit(":", 1)[0]

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")

    # El fragmento nunca distingue artículos.
    return urlunsplit((scheme, netloc, path, strip_tracking(parts.query), ""))


def hash_url(url: str) -> str:
    """SHA-256 de la URL normalizada. Clave de deduplicación."""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def domain_of(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")
