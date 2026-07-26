"""superadmin users

Revision ID: 1370d8f54143
Revises: 6677c93b6fbf
Create Date: 2026-07-25 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "1370d8f54143"
down_revision: Union[str, Sequence[str], None] = "6677c93b6fbf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "superadmin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_superadmin_users_uuid", "superadmin_users", ["uuid"], unique=True)
    op.create_index("ix_superadmin_users_email", "superadmin_users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_superadmin_users_email", table_name="superadmin_users")
    op.drop_index("ix_superadmin_users_uuid", table_name="superadmin_users")
    op.drop_table("superadmin_users")
