"""Contrato común de los proveedores de discovery (§11, §15).

Discovery y extracción de contenido son etapas distintas: un proveedor entrega
URLs con la metadata que tenga, no el texto del artículo. Esa separación es lo
que permite añadir GDELT o Common Crawl sin tocar el resto del pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime

from news_corpus.config.catalog import SourceConfig


@dataclass(frozen=True)
class Period:
    """Ventana de un bloque. Mensual por defecto: es la granularidad nativa
    de los sitemaps de El Tiempo, Caracol, Blu, La República y RCN."""

    start: date
    end: date

    @classmethod
    def month(cls, year: int, month: int) -> Period:
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return cls(start=start, end=end)

    def contains(self, when: datetime | date) -> bool:
        d = when.date() if isinstance(when, datetime) else when
        return self.start <= d < self.end

    @property
    def label(self) -> str:
        return f"{self.start:%Y-%m}"

    def __str__(self) -> str:
        return self.label


@dataclass
class DiscoveredItem:
    """Una URL vista por un proveedor, antes de normalizar o deduplicar."""

    url: str
    title: str | None = None
    published_at: datetime | None = None
    published_at_raw: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class DiscoveryResult:
    items: list[DiscoveredItem]
    request_url: str
    # `empty_is_legitimate` distingue "este mes no tuvo publicaciones" de
    # "el proveedor no respondió". Confundirlos marca bloques como completados
    # sin datos — el fallo silencioso que documentamos en GDELT (Fase 1, §B).
    empty_is_legitimate: bool = True


class BaseProvider(ABC):
    """Adapter de discovery. Un proveedor por fuente de URLs."""

    name: str = "base"

    @abstractmethod
    def discover(self, source: SourceConfig, period: Period) -> DiscoveryResult:
        """Devuelve las URLs que el proveedor conoce para (medio, período).

        Debe lanzar excepción si la petición falló. Devolver una lista vacía
        significa afirmar que no había nada.
        """

    def supports(self, source: SourceConfig) -> bool:
        return True

    def close(self) -> None:  # noqa: B027 — hook opcional, no todo proveedor abre conexiones
        """Libera recursos (conexiones HTTP). Sin efecto por defecto."""
        return None
