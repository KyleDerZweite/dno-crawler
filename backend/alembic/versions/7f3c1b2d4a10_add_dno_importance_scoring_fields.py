"""add dno importance scoring fields

Revision ID: 7f3c1b2d4a10
Revises: 2682f122e71f
Create Date: 2026-03-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f3c1b2d4a10"
down_revision: str | Sequence[str] | None = "2682f122e71f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("dnos", sa.Column("service_area_km2", sa.Float(), nullable=True))
    op.add_column("dnos", sa.Column("customer_count", sa.Integer(), nullable=True))
    op.add_column("dnos", sa.Column("importance_score", sa.Float(), nullable=True))
    op.add_column("dnos", sa.Column("importance_confidence", sa.Float(), nullable=True))
    op.add_column("dnos", sa.Column("importance_version", sa.String(length=32), nullable=True))
    op.add_column("dnos", sa.Column("importance_factors", sa.JSON(), nullable=True))
    op.add_column("dnos", sa.Column("importance_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_dnos_importance_score"), "dnos", ["importance_score"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_dnos_importance_score"), table_name="dnos")
    op.drop_column("dnos", "importance_updated_at")
    op.drop_column("dnos", "importance_factors")
    op.drop_column("dnos", "importance_version")
    op.drop_column("dnos", "importance_confidence")
    op.drop_column("dnos", "importance_score")
    op.drop_column("dnos", "customer_count")
    op.drop_column("dnos", "service_area_km2")
