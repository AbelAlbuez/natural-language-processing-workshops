"""Carga y valida config/*.yaml en objetos tipados.

El catálogo YAML es la fuente de verdad; las tablas del mismo nombre en
Postgres son un espejo sincronizable (`news-corpus catalog sync`). Editar el
YAML y re-sincronizar debe bastar para cambiar medios, gobiernos o temas sin
tocar código (§20, §30).
"""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


def _parse_month(value: Any) -> date | None:
    """Acepta `2008-11`, `2008-11-01` o una `date` ya parseada por PyYAML."""
    if value is None:
        return None
    if isinstance(value, date):
        return value.replace(day=1)
    text = str(value).strip()
    parts = text.split("-")
    if len(parts) == 2:
        return date(int(parts[0]), int(parts[1]), 1)
    return date.fromisoformat(text).replace(day=1)


# ─────────────────────────────────────────────────────────────────────────────


class DiscoveryConfig(BaseModel):
    strategy: str
    url_template: str | None = None
    archive_from: date | None = None
    reliable_from: date | None = None
    max_offset: int | None = None
    fallback: list[str] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _months(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("archive_from", "reliable_from"):
                if key in data:
                    data[key] = _parse_month(data[key])
        return data


class SourceConfig(BaseModel):
    id: str
    name: str
    domains: list[str]
    source_type: str
    active: bool = True
    country: str = "CO"
    language: str = "es"
    discovery: DiscoveryConfig

    @property
    def canonical_domain(self) -> str:
        return self.domains[0]

    def sitemap_url(self, year: int, month: int) -> str:
        """Resuelve la plantilla mensual del medio.

        `month_name_en` existe porque La República y RCN nombran sus sitemaps
        con el mes en inglés (`articles_August_2026.xml.gz`).
        """
        if not self.discovery.url_template:
            raise ValueError(f"{self.id} no define url_template")
        return self.discovery.url_template.format(
            year=year,
            month=month,
            month_name_en=calendar.month_name[month],
        )


class GovernmentConfig(BaseModel):
    id: str
    president: str
    term: int = 1
    start_date: date
    end_date: date
    source_note: str | None = None

    def contains(self, when: date) -> bool:
        """Intervalo semiabierto: el día de posesión pertenece al gobierno que entra."""
        return self.start_date <= when < self.end_date


class TopicConfig(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    keywords: list[str] = Field(default_factory=list)
    active: bool = True


class CrossSourceProviderConfig(BaseModel):
    id: str
    enabled: bool = True
    coverage_from: date | None = None
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _months(cls, data: Any) -> Any:
        if isinstance(data, dict) and "coverage_from" in data:
            data["coverage_from"] = _parse_month(data["coverage_from"])
        return data


class Catalog(BaseModel):
    sources: list[SourceConfig]
    governments: list[GovernmentConfig]
    topics: list[TopicConfig]
    cross_source_providers: list[CrossSourceProviderConfig] = Field(default_factory=list)

    # ── Búsquedas ────────────────────────────────────────────────────────────

    def source(self, source_id: str) -> SourceConfig:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(f"Medio desconocido: {source_id!r}")

    def active_sources(self) -> list[SourceConfig]:
        return [s for s in self.sources if s.active]

    def source_for_domain(self, domain: str) -> SourceConfig | None:
        """Resuelve dominio → medio. Many-to-one: RTVC cambió de dominio."""
        needle = domain.lower().removeprefix("www.")
        for s in self.sources:
            if any(d.lower().removeprefix("www.") == needle for d in s.domains):
                return s
        return None

    def government_at(self, when: date) -> GovernmentConfig | None:
        for g in self.governments:
            if g.contains(when):
                return g
        return None

    def government(self, government_id: str) -> GovernmentConfig:
        for g in self.governments:
            if g.id == government_id:
                return g
        raise KeyError(f"Gobierno desconocido: {government_id!r}")


# ─────────────────────────────────────────────────────────────────────────────


def _read(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Falta el archivo de configuración: {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _flatten_topics(raw: list[dict], parent_id: str | None = None) -> list[TopicConfig]:
    out: list[TopicConfig] = []
    for node in raw:
        out.append(
            TopicConfig(
                id=node["id"],
                name=node["name"],
                parent_id=parent_id,
                keywords=node.get("keywords", []),
                active=node.get("active", True),
            )
        )
        out.extend(_flatten_topics(node.get("children", []), parent_id=node["id"]))
    return out


def load_catalog(config_dir: Path) -> Catalog:
    sources_doc = _read(config_dir / "sources.yaml")
    governments_doc = _read(config_dir / "governments.yaml")
    topics_doc = _read(config_dir / "topics.yaml")

    defaults = sources_doc.get("defaults", {})
    sources = [
        SourceConfig(**{**defaults, **entry}) for entry in sources_doc.get("sources", [])
    ]

    catalog = Catalog(
        sources=sources,
        governments=[GovernmentConfig(**g) for g in governments_doc.get("governments", [])],
        topics=_flatten_topics(topics_doc.get("topics", [])),
        cross_source_providers=[
            CrossSourceProviderConfig(**p)
            for p in sources_doc.get("cross_source_providers", [])
        ],
    )
    _validate(catalog)
    return catalog


def _validate(catalog: Catalog) -> None:
    """Falla temprano ante configuración incoherente."""
    errors: list[str] = []

    for name, items in (
        ("medios", catalog.sources),
        ("gobiernos", catalog.governments),
        ("temas", catalog.topics),
    ):
        ids = [i.id for i in items]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            errors.append(f"IDs duplicados en {name}: {sorted(dupes)}")

    # Un dominio no puede apuntar a dos medios: rompería el mapeo del corpus.
    seen: dict[str, str] = {}
    for s in catalog.sources:
        for d in s.domains:
            key = d.lower().removeprefix("www.")
            if key in seen and seen[key] != s.id:
                errors.append(f"El dominio {d!r} está en {seen[key]!r} y en {s.id!r}")
            seen[key] = s.id

    # Los gobiernos deben ser contiguos y no solaparse: si no, un artículo
    # podría caer en dos gobiernos o en ninguno.
    ordered = sorted(catalog.governments, key=lambda g: g.start_date)
    for prev, nxt in zip(ordered, ordered[1:], strict=False):
        if prev.end_date > nxt.start_date:
            errors.append(f"Gobiernos solapados: {prev.id} y {nxt.id}")
        elif prev.end_date < nxt.start_date:
            errors.append(
                f"Hueco entre gobiernos {prev.id} ({prev.end_date}) "
                f"y {nxt.id} ({nxt.start_date})"
            )

    known = {t.id for t in catalog.topics}
    for t in catalog.topics:
        if t.parent_id and t.parent_id not in known:
            errors.append(f"El tema {t.id!r} referencia un padre inexistente {t.parent_id!r}")

    if errors:
        raise ValueError("Configuración inválida:\n  - " + "\n  - ".join(errors))
