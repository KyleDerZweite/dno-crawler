"""add download registry

Revision ID: a3b9c7d1e5f2
Revises: 7f3c1b2d4a10
Create Date: 2026-03-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b9c7d1e5f2"
down_revision: str | Sequence[str] | None = "7f3c1b2d4a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create download_registry table for cross-run download deduplication."""
    op.create_table(
        "download_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "dno_id",
            sa.Integer(),
            sa.ForeignKey("dnos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "crawl_job_id",
            sa.Integer(),
            sa.ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(32), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("file_format", sa.String(10), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(20), nullable=False, server_default="unclassified"),
        sa.Column("classification_detail", postgresql.JSON(), nullable=True),
        sa.Column("detected_year", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_dlreg_dno_year", "download_registry", ["dno_id", "year"])
    op.create_index("idx_dlreg_url_hash", "download_registry", ["dno_id", "url_hash"], unique=True)


def downgrade() -> None:
    """Drop download_registry table."""
    op.drop_index("idx_dlreg_url_hash", table_name="download_registry")
    op.drop_index("idx_dlreg_dno_year", table_name="download_registry")
    op.drop_table("download_registry")
