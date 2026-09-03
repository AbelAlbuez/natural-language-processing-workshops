"""Ejecuta un bloque de adquisición de principio a fin.

    discovery → normalización → validación → deduplicación → persistencia

El bloque es la unidad transaccional y reanudable. Sólo se marca COMPLETED si
el proveedor respondió; si falló, queda FAILED y se reintenta. Devolver cero
artículos por un fallo de red y darlo por bueno es cómo se producen huecos
silenciosos en un corpus (Fase 1, §B).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from news_corpus.config.catalog import Catalog, SourceConfig
from news_corpus.db.models import (
    ArchiveDensity,
    Article,
    ChunkStatus,
    CollectionChunk,
    DatePrecision,
    DiscoveryRecord,
    RejectionReason,
)
from news_corpus.providers.base import BaseProvider, DiscoveredItem, Period
from news_corpus.utils.logging import get_logger
from news_corpus.utils.urls import domain_of, hash_url, normalize_url

logger = get_logger(__name__)


@dataclass
class ChunkOutcome:
    source_id: str
    period: str
    status: ChunkStatus
    n_found: int = 0
    n_new: int = 0
    n_duplicates: int = 0
    n_rejected: int = 0
    n_out_of_period: int = 0
    error: str | None = None


def resolve_publication_date(
    item: DiscoveredItem, period: Period
) -> tuple[datetime | None, date | None, DatePrecision]:
    """Decide la fecha de publicación y cuánto vale.

    `lastmod` sólo se cree si cae dentro del mes del propio sitemap. Cuando no,
    es un artefacto de migración del CMS (verificado en Blu Radio: el 100% de
    los sitemaps de 2013 traen lastmod de 2016-2024, con slugs que dicen
    "1-de-enero-de-2013"). En ese caso manda el mes del archivo.
    """
    if item.published_at is not None and period.contains(item.published_at):
        return item.published_at, item.published_at.date(), DatePrecision.DAY

    if item.published_at is not None:
        # Había fecha, pero es de otra época: se conserva en el registro de
        # discovery y se degrada a precisión de mes.
        return None, period.start, DatePrecision.MONTH

    return None, period.start, DatePrecision.MONTH


def resolve_government(
    catalog: Catalog, published_date: date | None, precision: DatePrecision, period: Period
):
    """Asigna gobierno sólo cuando la fecha lo determina sin ambigüedad.

    Con precisión de mes, un mes de transición (agosto de 2010, 2014, 2018,
    2022) contiene dos gobiernos: asignar uno sería inventarse el dato.
    """
    if published_date is None:
        return None

    if precision == DatePrecision.DAY:
        return catalog.government_at(published_date)

    inicio = catalog.government_at(period.start)
    ultimo_dia = date.fromordinal(period.end.toordinal() - 1)
    fin = catalog.government_at(ultimo_dia)
    return inicio if inicio is not None and inicio is fin else None


def _get_or_create_chunk(
    session: Session, *, source_id: str, provider: str, period: Period
) -> CollectionChunk:
    chunk = session.scalar(
        select(CollectionChunk).where(
            CollectionChunk.source_id == source_id,
            CollectionChunk.provider == provider,
            CollectionChunk.period_start == period.start,
        )
    )
    if chunk is None:
        chunk = CollectionChunk(
            source_id=source_id,
            provider=provider,
            period_start=period.start,
            period_end=period.end,
        )
        session.add(chunk)
        session.flush()
    return chunk


def collect_chunk(
    session: Session,
    *,
    provider: BaseProvider,
    catalog: Catalog,
    source: SourceConfig,
    period: Period,
    force: bool = False,
) -> ChunkOutcome:
    """Procesa un bloque. Idempotente: reprocesar no duplica artículos."""

    chunk = _get_or_create_chunk(
        session, source_id=source.id, provider=provider.name, period=period
    )

    if chunk.status == ChunkStatus.COMPLETED and not force:
        logger.debug("bloque ya completado", medio=source.id, periodo=period.label)
        return ChunkOutcome(
            source_id=source.id,
            period=period.label,
            status=ChunkStatus.COMPLETED,
            n_found=chunk.n_found,
        )

    chunk.status = ChunkStatus.RUNNING
    chunk.attempts += 1
    chunk.started_at = datetime.now(UTC)
    session.flush()

    try:
        result = provider.discover(source, period)
    except Exception as exc:  # el proveedor no respondió: NO es un mes vacío
        chunk.status = ChunkStatus.FAILED
        chunk.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        session.flush()
        logger.warning(
            "bloque fallido", medio=source.id, periodo=period.label, error=str(exc)
        )
        return ChunkOutcome(
            source_id=source.id,
            period=period.label,
            status=ChunkStatus.FAILED,
            error=str(exc),
        )

    outcome = _persist(
        session,
        chunk=chunk,
        catalog=catalog,
        source=source,
        period=period,
        provider_name=provider.name,
        items=result.items,
    )

    chunk.request_url = result.request_url
    chunk.n_found = outcome.n_found
    chunk.n_new = outcome.n_new
    chunk.n_duplicates = outcome.n_duplicates
    chunk.n_rejected = outcome.n_rejected
    chunk.status = ChunkStatus.COMPLETED
    chunk.completed_at = datetime.now(UTC)
    chunk.last_error = None

    _record_density(
        session,
        source_id=source.id,
        provider=provider.name,
        period=period,
        n_offered=outcome.n_found,
        n_stored=outcome.n_new + outcome.n_duplicates,
    )

    session.flush()
    return outcome


def _persist(
    session: Session,
    *,
    chunk: CollectionChunk,
    catalog: Catalog,
    source: SourceConfig,
    period: Period,
    provider_name: str,
    items: list[DiscoveredItem],
) -> ChunkOutcome:
    out = ChunkOutcome(
        source_id=source.id, period=period.label, status=ChunkStatus.COMPLETED
    )
    out.n_found = len(items)

    # Deduplicación dentro del propio bloque: un sitemap puede repetir una URL.
    seen_in_chunk: set[str] = set()

    for item in items:
        url_norm = normalize_url(item.url)
        url_h = hash_url(item.url)

        if url_h in seen_in_chunk:
            out.n_duplicates += 1
            continue
        seen_in_chunk.add(url_h)

        # El dominio debe pertenecer al medio esperado. Protege contra
        # sitemaps que enlazan a terceros y contra errores de configuración.
        resolved = catalog.source_for_domain(domain_of(url_norm))
        rejected: RejectionReason | None = None
        if resolved is None or resolved.id != source.id:
            rejected = RejectionReason.UNKNOWN_DOMAIN
            out.n_rejected += 1

        if item.raw.get("date_in_period") is False:
            out.n_out_of_period += 1

        record = DiscoveryRecord(
            chunk_id=chunk.id,
            provider=provider_name,
            url=item.url,
            url_normalized=url_norm,
            url_hash=url_h,
            title_raw=item.title,
            published_at_raw=item.published_at_raw,
            published_at=item.published_at,
            raw_payload=item.raw,
            rejected_reason=rejected,
        )
        session.add(record)

        if rejected is not None:
            continue

        article = session.scalar(select(Article).where(Article.url_hash == url_h))
        if article is None:
            published_at, published_date, precision = resolve_publication_date(item, period)
            government = resolve_government(catalog, published_date, precision, period)
            article = Article(
                url_hash=url_h,
                url=item.url,
                url_normalized=url_norm,
                source_id=source.id,
                government_id=government.id if government else None,
                title=item.title,
                published_at=published_at,
                published_date=published_date,
                date_precision=precision,
                language=source.language,
                first_seen_provider=provider_name,
            )
            session.add(article)
            session.flush()
            out.n_new += 1
        else:
            # Ya existía: otro proveedor o bloque lo vio antes. Se enriquece
            # sin sobrescribir — el primer dato observado se conserva.
            out.n_duplicates += 1
            if article.title is None and item.title:
                article.title = item.title

        record.article_id = article.id

    return out


def _record_density(
    session: Session,
    *,
    source_id: str,
    provider: str,
    period: Period,
    n_offered: int,
    n_stored: int,
) -> None:
    """Registra cuántas URLs ofreció el medio ese mes.

    Es la defensa contra el sesgo de archivo: sin este dato, comparar volumen
    de cobertura entre gobiernos mide el archivado (Fase 1, riesgo #2).
    """
    row = session.get(ArchiveDensity, (source_id, provider, period.start))
    if row is None:
        row = ArchiveDensity(
            source_id=source_id, provider=provider, period_start=period.start
        )
        session.add(row)
    row.n_urls_offered = n_offered
    row.n_articles_stored = n_stored
    row.measured_at = datetime.now(UTC)


def corpus_summary(session: Session) -> dict:
    """Cifras agregadas para `news-corpus status`."""
    by_status = dict(
        session.execute(
            select(CollectionChunk.status, func.count()).group_by(CollectionChunk.status)
        ).all()
    )
    return {
        "chunks": {getattr(k, "value", str(k)): v for k, v in by_status.items()},
        "articles": session.scalar(select(func.count()).select_from(Article)) or 0,
        "discovery_records": session.scalar(
            select(func.count()).select_from(DiscoveryRecord)
        )
        or 0,
    }
