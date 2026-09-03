"""Esquema del corpus.

Tres decisiones de diseño que vienen directamente de la Fase 1 y que conviene
no deshacer sin releer docs/01-research-and-architecture.md:

1. `discovery_record` y `article` están separados. Un registro de discovery es
   "vi esta URL en esta fuente en este momento"; un artículo es la entidad
   deduplicada. La separación es lo que permite responder "¿qué encontró cada
   proveedor?" y "¿qué se descartó y por qué?" sin perder trazabilidad (§18).

2. Nada se borra nunca. Los descartes se marcan con `rejected_reason`. Un
   corpus académico tiene que poder explicar sus ausencias.

3. `archive_density` existe porque el sitemap de El Tiempo tiene 129 URLs en
   junio de 2014 y 4.670 en junio de 2016. Sin esta tabla, cualquier
   comparación de volumen entre gobiernos mide el archivado, no la cobertura.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _enum_col(enum_cls, name: str, length: int) -> Enum:
    """Columna de enum que persiste el VALOR, no el nombre de Python.

    Sin `values_callable`, SQLAlchemy guarda 'COMPLETED' en vez de 'completed'.
    El corpus se exporta a Parquet/CSV para el análisis, así que lo que hay en
    la columna debe ser legible y estable sin pasar por el ORM.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class ChunkStatus(enum.StrEnum):
    """Estados de un bloque de adquisición (§10)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DatePrecision(enum.StrEnum):
    """Cuánta confianza merece `published_date`.

    Nace de un hallazgo real: los sitemaps de Blu Radio de 2013 traen
    `lastmod` de 2016-2024 — la marca de una migración masiva del CMS, no la
    fecha de publicación. En Blu Radio el 100% de las fechas caía fuera del
    mes de su propio sitemap, y en Caracol el 73%; en El Tiempo, el 0%.
    Los slugs lo confirman: `.../en-blu-jeans-1-de-enero-de-2013` con
    lastmod 2016-04-28. El archivo mensual manda sobre `lastmod`.

    DAY   — lastmod cayó dentro del mes del sitemap; se usa tal cual.
    MONTH — lastmod era un artefacto; sólo se conoce el mes del archivo.
    UNKNOWN — no había fecha utilizable.
    """

    DAY = "day"
    MONTH = "month"
    UNKNOWN = "unknown"


class TitleSource(enum.StrEnum):
    """De dónde salió el título. Un titular derivado del slug NO es el titular.

    Los sitemaps históricos no traen `news:title`: de los primeros 17.202
    artículos recolectados, 0 tenían título. El slug es un proxy muy bueno
    (`.../senado-de-estados-unidos-logra-acuerdo-para-evitar-abismo-fiscal`)
    pero es una reconstrucción: pierde tildes, mayúsculas y puntuación, y el
    medio pudo cambiar el titular sin cambiar la URL. Cualquier análisis léxico
    fino debe saber cuál está leyendo.
    """

    SITEMAP = "sitemap"      # declarado por el medio en news:title
    SLUG = "slug"            # derivado de la URL
    EXTRACTED = "extracted"  # leído de la página (fase de extracción)


class ExtractionStatus(enum.StrEnum):
    """Resultado de intentar leer la página del artículo.

    Se distingue el fallo recuperable (`http_error`, `failed`) del definitivo
    (`no_title`, `robots_denied`), para no reintentar en bucle lo que no va a
    cambiar ni dar por perdido lo que sí puede recuperarse.
    """

    OK = "ok"
    NO_TITLE = "no_title"          # la página respondió pero no tiene titular
    HTTP_ERROR = "http_error"      # 404/410: el artículo ya no existe
    FAILED = "failed"              # red o timeout: reintentable
    ROBOTS_DENIED = "robots_denied"


class RejectionReason(enum.StrEnum):
    """Por qué un registro de discovery no se promovió a artículo.

    `OUT_OF_WINDOW` es el guardia contra el fallo de GDELT verificado en Fase 1:
    HTTP 200 + JSON válido con artículos de otra época.
    """

    OUT_OF_WINDOW = "out_of_window"
    NOT_AN_ARTICLE = "not_an_article"
    UNKNOWN_DOMAIN = "unknown_domain"
    MALFORMED_URL = "malformed_url"
    DUPLICATE = "duplicate"


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo (espejo persistido de config/*.yaml — la configuración manda)
# ─────────────────────────────────────────────────────────────────────────────


class Source(Base):
    __tablename__ = "source"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="CO")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="es")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Fechas VERIFICADAS en Fase 1, no aspiracionales.
    archive_from: Mapped[date | None] = mapped_column(Date)
    reliable_from: Mapped[date | None] = mapped_column(Date)

    discovery_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    domains: Mapped[list[SourceDomain]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SourceDomain(Base):
    """Mapeo dominio → medio, many-to-one.

    Existe porque RTVC redirige de rtvc.gov.co a inravision.gov.co: en 20 años
    un medio cambia de dominio y el corpus debe seguir reconociéndolo.
    """

    __tablename__ = "source_domain"

    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    source: Mapped[Source] = relationship(back_populates="domains")


class Government(Base):
    __tablename__ = "government"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    president: Mapped[str] = mapped_column(String(160), nullable=False)
    term: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("end_date > start_date", name="ck_government_dates"),
    )


class Topic(Base):
    __tablename__ = "topic"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"), index=True
    )
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ─────────────────────────────────────────────────────────────────────────────
# Adquisición
# ─────────────────────────────────────────────────────────────────────────────


class CollectionChunk(Base):
    """Unidad atómica y reanudable: (medio, proveedor, año-mes).

    La granularidad mensual no es arbitraria: coincide con la de los sitemaps
    de El Tiempo, Caracol, Blu, La República y RCN.
    """

    __tablename__ = "collection_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[ChunkStatus] = mapped_column(
        _enum_col(ChunkStatus, "chunk_status", 16),
        nullable=False,
        default=ChunkStatus.PENDING,
        index=True,
    )

    # Reproducibilidad (§26): sin esto no se puede explicar cómo se construyó
    # cualquier subconjunto del corpus.
    request_url: Mapped[str | None] = mapped_column(Text)
    n_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # La clave de reanudación. Un bloque completado no se repite (§10).
        UniqueConstraint(
            "source_id", "provider", "period_start", name="uq_chunk_identity"
        ),
        CheckConstraint("period_end > period_start", name="ck_chunk_period"),
        Index("ix_chunk_resume", "status", "provider", "source_id"),
    )


class DiscoveryRecord(Base):
    """Una observación cruda: "este proveedor vio esta URL".

    Se conserva aunque el registro sea rechazado o duplicado — es la única
    forma de responder después "¿qué quedó fuera del corpus y por qué?".
    """

    __tablename__ = "discovery_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("collection_chunk.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    title_raw: Mapped[str | None] = mapped_column(Text)
    published_at_raw: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Se resuelve a artículo sólo si supera validación y deduplicación.
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("article.id", ondelete="SET NULL"), index=True
    )
    rejected_reason: Mapped[RejectionReason | None] = mapped_column(
        _enum_col(RejectionReason, "rejection_reason", 24)
    )

    # Provenance completa (§18). `raw_payload` se guarda como dict, no como str:
    # serializar en la capa de dominio mezcla capas (lección de FinSage).
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("chunk_id", "url_hash", name="uq_discovery_per_chunk"),
        Index("ix_discovery_unresolved", "chunk_id", "article_id"),
    )


class Article(Base):
    """La entidad deduplicada. Unidad fundamental de análisis (§2)."""

    __tablename__ = "article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)

    source_id: Mapped[str] = mapped_column(
        ForeignKey("source.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    government_id: Mapped[str | None] = mapped_column(
        ForeignKey("government.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str | None] = mapped_column(Text)
    title_source: Mapped[TitleSource | None] = mapped_column(
        _enum_col(TitleSource, "title_source", 12), index=True
    )
    subtitle: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(String(160))
    image_url: Mapped[str | None] = mapped_column(Text)

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    published_date: Mapped[date | None] = mapped_column(Date, index=True)
    # Sin esto, una fecha de migración del CMS pasa por fecha de publicación y
    # el eje temporal del corpus queda corrompido en silencio.
    date_precision: Mapped[DatePrecision] = mapped_column(
        _enum_col(DatePrecision, "date_precision", 12),
        nullable=False,
        default=DatePrecision.UNKNOWN,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="es")

    # Fase de extracción (posterior). Se dejan preparados, no se llenan aún.
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    extraction_status: Mapped[ExtractionStatus | None] = mapped_column(
        _enum_col(ExtractionStatus, "extraction_status", 16), index=True
    )
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)

    # Qué proveedor lo vio PRIMERO. El linaje completo vive en discovery_record:
    # un artículo puede haber sido descubierto por sitemap y por GDELT a la vez.
    first_seen_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_article_corpus_slice", "source_id", "government_id", "published_date"),
        Index("ix_article_source_date", "source_id", "published_date"),
    )


class ArticleTopic(Base):
    """Etiquetado temático multi-etiqueta, aplicado DESPUÉS del discovery.

    `rule_version` permite re-etiquetar el corpus cuando cambien las keywords
    de topics.yaml sin volver a descargar nada, y saber qué versión de reglas
    produjo cada etiqueta.
    """

    __tablename__ = "article_topic"

    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"), primary_key=True
    )
    matched_on: Mapped[str] = mapped_column(String(32), nullable=False)
    matched_keyword: Mapped[str | None] = mapped_column(String(160))
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)


class ArchiveDensity(Base):
    """Cuántas URLs ofreció realmente cada medio en cada mes.

    Esta tabla es una defensa metodológica, no una métrica operativa. El
    sitemap de El Tiempo da 129 URLs en junio de 2014 y 4.670 en junio de 2016;
    sin registrar eso, comparar el volumen de cobertura entre el gobierno de
    Uribe y el de Petro mide el archivado y lo presenta como hallazgo.
    """

    __tablename__ = "archive_density"

    source_id: Mapped[str] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)

    n_urls_offered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_articles_stored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
