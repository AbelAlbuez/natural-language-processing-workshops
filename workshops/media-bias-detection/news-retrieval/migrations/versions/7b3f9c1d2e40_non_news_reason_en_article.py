"""non_news_reason en article

Revision ID: 7b3f9c1d2e40
Revises: 29e030435542
Create Date: 2026-11-04 23:30:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '7b3f9c1d2e40'
down_revision: str | None = '29e030435542'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('article', sa.Column('non_news_reason', sa.Enum('emision', 'multimedia', 'caricatura', 'servicio', 'indicador', 'comercial', 'obituario', name='non_news_reason', native_enum=False, length=16), nullable=True))
    op.create_index(op.f('ix_article_non_news_reason'), 'article', ['non_news_reason'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_article_non_news_reason'), table_name='article')
    op.drop_column('article', 'non_news_reason')
