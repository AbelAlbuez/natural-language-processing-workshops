"""Genera los bloques mensuales a recolectar.

Ver §9: el corpus no se construye con una ejecución gigante, sino con muchas
unidades pequeñas de (medio, proveedor, año-mes). El planificador es lo que
convierte "quiero 2013–2024 de El Tiempo" en 144 bloques reanudables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from news_corpus.config.catalog import Catalog, SourceConfig
from news_corpus.providers.base import Period


def month_range(start: date, end: date) -> list[Period]:
    """Bloques mensuales de `start` a `end`, ambos inclusive por mes."""
    periods: list[Period] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        periods.append(Period.month(year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return periods


@dataclass
class PlannedChunk:
    source: SourceConfig
    period: Period
    # Motivo por el que un bloque se marca como fuera de cobertura conocida.
    # No se descarta: se informa. Que el archivo declare no llegar tan atrás
    # no es prueba de que no haya nada.
    warning: str | None = None


def plan(
    catalog: Catalog,
    *,
    source_ids: list[str],
    start: date,
    end: date,
    skip_before_archive: bool = True,
) -> list[PlannedChunk]:
    planned: list[PlannedChunk] = []

    for source_id in source_ids:
        source = catalog.source(source_id)
        if not source.active:
            continue

        for period in month_range(start, end):
            archive_from = source.discovery.archive_from
            reliable_from = source.discovery.reliable_from
            warning: str | None = None

            if archive_from and period.start < archive_from:
                if skip_before_archive:
                    continue
                warning = f"anterior al archivo declarado ({archive_from:%Y-%m})"
            elif reliable_from and period.start < reliable_from:
                # El caso de El Tiempo: hay archivo desde 1990 pero sólo es
                # denso desde 2016. Se recolecta igual, marcado.
                warning = f"archivo adelgazado (denso desde {reliable_from:%Y-%m})"

            planned.append(PlannedChunk(source=source, period=period, warning=warning))

    return planned


def resolve_sources(catalog: Catalog, requested: list[str] | None) -> list[str]:
    """`None` o vacío significa todos los medios activos con sitemap propio."""
    if requested:
        for sid in requested:
            catalog.source(sid)  # lanza KeyError si no existe
        return requested
    return [
        s.id
        for s in catalog.active_sources()
        if s.discovery.strategy in {"monthly_sitemap", "monthly_sitemap_gz"}
    ]
