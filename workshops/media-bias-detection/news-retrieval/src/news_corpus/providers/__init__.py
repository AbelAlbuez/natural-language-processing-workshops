"""Proveedores de discovery y su selección por estrategia del catálogo."""

from __future__ import annotations

from datetime import date

from news_corpus.providers.base import BaseProvider
from news_corpus.providers.indexed import ArcFeedProvider, SitemapIndexProvider
from news_corpus.providers.sitemap import SUPPORTED_STRATEGIES as _MONTHLY
from news_corpus.providers.sitemap import SitemapProvider

#: Estrategias de `sources.yaml` que el pipeline sabe recolectar.
COLLECTABLE_STRATEGIES = set(_MONTHLY) | {"arc_paginated", "sitemap_index"}


class ProviderPool:
    """Un proveedor por estrategia, reutilizado en toda la corrida.

    Reutilizar importa para Arc e índices: guardan el feed en memoria y cada
    bloque mensual filtra sobre esa copia en vez de volver a descargarlo.
    """

    def __init__(self, *, stop_before: date | None = None) -> None:
        self._stop_before = stop_before
        self._providers: dict[str, BaseProvider] = {}

    def for_strategy(self, strategy: str) -> BaseProvider:
        if strategy not in self._providers:
            if strategy in _MONTHLY:
                self._providers[strategy] = SitemapProvider()
            elif strategy == "arc_paginated":
                self._providers[strategy] = ArcFeedProvider(stop_before=self._stop_before)
            elif strategy == "sitemap_index":
                self._providers[strategy] = SitemapIndexProvider(stop_before=self._stop_before)
            else:
                raise ValueError(f"estrategia {strategy!r} sin proveedor implementado")
        return self._providers[strategy]

    def close(self) -> None:
        for p in self._providers.values():
            p.close()


__all__ = [
    "COLLECTABLE_STRATEGIES",
    "ArcFeedProvider",
    "ProviderPool",
    "SitemapIndexProvider",
    "SitemapProvider",
]
