"""Sincroniza config/*.yaml → Postgres.

El YAML manda. Esta operación es idempotente: correrla dos veces deja la base
igual. Los medios que desaparecen del YAML se marcan `active=False` en vez de
borrarse — un artículo ya almacenado sigue necesitando su medio para
interpretarse, y borrar historia contradice la trazabilidad del corpus (§18).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from news_corpus.config.catalog import Catalog
from news_corpus.db.models import Government, Source, SourceDomain, Topic


@dataclass
class SyncReport:
    sources_created: int = 0
    sources_updated: int = 0
    sources_deactivated: list[str] = field(default_factory=list)
    governments_upserted: int = 0
    topics_upserted: int = 0
    domains_linked: int = 0

    def render(self) -> str:
        lines = [
            f"medios      creados {self.sources_created}, actualizados {self.sources_updated}",
            f"dominios    vinculados {self.domains_linked}",
            f"gobiernos   {self.governments_upserted}",
            f"temas       {self.topics_upserted}",
        ]
        if self.sources_deactivated:
            lines.append(
                "desactivados (ya no están en el YAML): "
                + ", ".join(self.sources_deactivated)
            )
        return "\n".join(lines)


def sync_catalog(session: Session, catalog: Catalog) -> SyncReport:
    report = SyncReport()

    # ── Medios y dominios ────────────────────────────────────────────────────
    yaml_ids = {s.id for s in catalog.sources}
    for cfg in catalog.sources:
        row = session.get(Source, cfg.id)
        if row is None:
            row = Source(id=cfg.id)
            session.add(row)
            report.sources_created += 1
        else:
            report.sources_updated += 1

        row.name = cfg.name
        row.source_type = cfg.source_type
        row.country = cfg.country
        row.language = cfg.language
        row.active = cfg.active
        row.archive_from = cfg.discovery.archive_from
        row.reliable_from = cfg.discovery.reliable_from
        row.discovery_config = cfg.discovery.model_dump(mode="json")

        session.flush()

        existing = {d.domain for d in row.domains}
        for i, domain in enumerate(cfg.domains):
            key = domain.lower()
            if key not in existing:
                session.add(
                    SourceDomain(domain=key, source_id=cfg.id, is_canonical=(i == 0))
                )
                report.domains_linked += 1

    for row in session.scalars(select(Source)).all():
        if row.id not in yaml_ids and row.active:
            row.active = False
            report.sources_deactivated.append(row.id)

    # ── Gobiernos ────────────────────────────────────────────────────────────
    for cfg in catalog.governments:
        row = session.get(Government, cfg.id) or Government(id=cfg.id)
        row.president = cfg.president
        row.term = cfg.term
        row.start_date = cfg.start_date
        row.end_date = cfg.end_date
        row.source_note = cfg.source_note
        session.merge(row)
        report.governments_upserted += 1

    # ── Temas ────────────────────────────────────────────────────────────────
    # Los padres primero: `parent_id` es una FK a esta misma tabla.
    for cfg in sorted(catalog.topics, key=lambda t: (t.parent_id is not None, t.id)):
        row = session.get(Topic, cfg.id) or Topic(id=cfg.id)
        row.name = cfg.name
        row.parent_id = cfg.parent_id
        row.keywords = cfg.keywords
        row.active = cfg.active
        session.merge(row)
        report.topics_upserted += 1

    return report
