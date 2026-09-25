"""add webhook oauth client credentials

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23 14:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add OAuth client_credentials columns to sc_webhook and token cache table."""
    op.add_column(
        "sc_webhook",
        sa.Column("auth_type", sa.String(length=32), server_default="none", nullable=False),
    )
    op.add_column(
        "sc_webhook",
        sa.Column("oauth_token_url", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "sc_webhook",
        sa.Column("oauth_client_id", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "sc_webhook",
        sa.Column("oauth_client_secret", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "sc_webhook",
        sa.Column("oauth_scope", sa.String(length=512), nullable=True),
    )

    op.create_table(
        "sys_oauth_token_cache",
        sa.Column("sys_id", sa.String(length=32), nullable=False),
        sa.Column("webhook_id", sa.String(length=32), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(length=32), nullable=False, server_default="Bearer"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sys_id"),
        sa.ForeignKeyConstraint(["webhook_id"], ["sc_webhook.sys_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("webhook_id"),
    )
    op.create_index(
        op.f("ix_sys_oauth_token_cache_webhook_id"),
        "sys_oauth_token_cache",
        ["webhook_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove OAuth client_credentials support."""
    op.drop_index(
        op.f("ix_sys_oauth_token_cache_webhook_id"),
        table_name="sys_oauth_token_cache",
    )
    op.drop_table("sys_oauth_token_cache")
    op.drop_column("sc_webhook", "oauth_scope")
    op.drop_column("sc_webhook", "oauth_client_secret")
    op.drop_column("sc_webhook", "oauth_client_id")
    op.drop_column("sc_webhook", "oauth_token_url")
    op.drop_column("sc_webhook", "auth_type")
