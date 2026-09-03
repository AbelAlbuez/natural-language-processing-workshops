"""date_precision en article + enums en minúscula

Dos cambios que van juntos:

1. `article.date_precision` distingue una fecha de publicación real de una
   marca de migración del CMS. Nació de un hallazgo: en los sitemaps de
   Blu Radio de 2013 el 100% de los `lastmod` es de 2016-2024, y en Caracol
   el 73%, mientras los slugs dicen "1-de-enero-de-2013".

2. Los enums pasan a guardar su VALOR ('completed') y no el nombre de Python
   ('COMPLETED'), para que el corpus exportado sea legible sin el ORM.

Revision ID: 5c7a077ee1b3
Revises: be442265c01f
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c7a077ee1b3"
down_revision: str | None = "be442265c01f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "article",
        sa.Column(
            "date_precision",
            sa.String(length=12),
            nullable=False,
            # Las filas existentes se recolectaron antes de distinguir la fecha
            # real del artefacto de migración: quedan 'unknown' hasta que se
            # vuelvan a recoger con --force.
            server_default="unknown",
        ),
    )
    op.create_index(
        op.f("ix_article_date_precision"), "article", ["date_precision"], unique=False
    )

    # Normalizar los valores ya escritos con el nombre del enum.
    op.execute("UPDATE collection_chunk SET status = lower(status)")
    op.execute(
        "UPDATE discovery_record SET rejected_reason = lower(rejected_reason) "
        "WHERE rejected_reason IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("UPDATE collection_chunk SET status = upper(status)")
    op.execute(
        "UPDATE discovery_record SET rejected_reason = upper(rejected_reason) "
        "WHERE rejected_reason IS NOT NULL"
    )
    op.drop_index(op.f("ix_article_date_precision"), table_name="article")
    op.drop_column("article", "date_precision")
