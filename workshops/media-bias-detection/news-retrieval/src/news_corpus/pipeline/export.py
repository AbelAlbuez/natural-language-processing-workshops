"""Export del corpus para análisis NLP (§24).

El dataset exportado lleva los campos de procedencia — `date_precision`,
`title_source`, `archive_density` — no como adorno, sino porque sin ellos el
análisis no puede distinguir un titular publicado de uno reconstruido, ni una
diferencia de cobertura de una diferencia de archivado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from news_corpus.db.models import (
    ArchiveDensity,
    Article,
    ArticleTopic,
    Source,
)

# El cuerpo va al final a propósito: deja legible el CSV en un editor y no
# estorba a quien sólo quiere la metadata.
METADATA_COLUMNS = [
    "article_id", "url", "source_id", "source_name", "government_id",
    "title", "title_source", "section", "published_date", "date_precision",
    "topics", "provider", "first_seen_at", "archive_density_month",
    "author", "description", "extraction_status", "content_chars",
]
CONTENT_COLUMNS = ["content", "content_hash"]
COLUMNS = METADATA_COLUMNS + CONTENT_COLUMNS


@dataclass
class ExportStats:
    rows: int
    path: Path
    fmt: str


def _rows(session: Session, *, source_id: str | None, desde: date | None, hasta: date | None):
    topics_sq = (
        select(
            ArticleTopic.article_id,
            func.string_agg(ArticleTopic.topic_id, ",").label("topics"),
        )
        .group_by(ArticleTopic.article_id)
        .subquery()
    )
    density_sq = select(
        ArchiveDensity.source_id,
        ArchiveDensity.period_start,
        ArchiveDensity.n_urls_offered,
    ).subquery()

    stmt = (
        select(
            Article.id, Article.url, Article.source_id, Source.name,
            Article.government_id, Article.title, Article.title_source,
            Article.section, Article.published_date, Article.date_precision,
            topics_sq.c.topics, Article.first_seen_provider, Article.first_seen_at,
            density_sq.c.n_urls_offered,
            Article.author, Article.description, Article.extraction_status,
            Article.content, Article.content_hash,
        )
        .join(Source, Source.id == Article.source_id)
        .outerjoin(topics_sq, topics_sq.c.article_id == Article.id)
        .outerjoin(
            density_sq,
            (density_sq.c.source_id == Article.source_id)
            & (
                density_sq.c.period_start
                == func.date_trunc("month", Article.published_date).cast(
                    Article.published_date.type
                )
            ),
        )
        .order_by(Article.source_id, Article.published_date, Article.id)
    )
    if source_id:
        stmt = stmt.where(Article.source_id == source_id)
    if desde:
        stmt = stmt.where(Article.published_date >= desde)
    if hasta:
        stmt = stmt.where(Article.published_date <= hasta)
    return session.execute(stmt).all()


def export_corpus(
    session: Session,
    *,
    out: Path,
    fmt: str = "parquet",
    source_id: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    with_content: bool = True,
) -> ExportStats:
    raw = _rows(session, source_id=source_id, desde=desde, hasta=hasta)
    columnas = COLUMNS if with_content else METADATA_COLUMNS

    records = [
        {
            "article_id": r[0],
            "url": r[1],
            "source_id": r[2],
            "source_name": r[3],
            "government_id": r[4],
            "title": r[5],
            "title_source": str(r[6]) if r[6] else None,
            "section": r[7],
            "published_date": r[8].isoformat() if r[8] else None,
            "date_precision": str(r[9]) if r[9] else None,
            "topics": r[10] or "",
            "provider": r[11],
            "first_seen_at": r[12].isoformat() if r[12] else None,
            "archive_density_month": r[13],
            "author": r[14],
            "description": r[15],
            "extraction_status": str(r[16]) if r[16] else None,
            # Longitud del cuerpo aunque no se exporte el cuerpo: permite
            # filtrar los artículos analizables sin cargar el texto entero.
            "content_chars": len(r[17]) if r[17] else 0,
            "content": r[17],
            "content_hash": r[18],
        }
        for r in raw
    ]
    if not with_content:
        for rec in records:
            for campo in CONTENT_COLUMNS:
                rec.pop(campo)

    out.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "jsonl":
        with out.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    elif fmt == "csv":
        import csv

        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=columnas)
            writer.writeheader()
            writer.writerows(records)
    elif fmt == "parquet":
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Parquet necesita el extra 'export': uv pip install -e '.[export]'"
            ) from exc
        pd.DataFrame(records, columns=columnas).to_parquet(out, index=False)
    else:
        raise ValueError(f"Formato no soportado: {fmt!r}")

    return ExportStats(rows=len(records), path=out, fmt=fmt)
