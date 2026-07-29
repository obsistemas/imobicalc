"""captacao automatica de leads

Revision ID: 3461e5b1fb3c
Revises: 1370d8f54143
Create Date: 2026-07-28 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "3461e5b1fb3c"
down_revision: Union[str, Sequence[str], None] = "1370d8f54143"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("leads", "corretor_id", existing_type=sa.Uuid(), nullable=True)

    op.add_column("imoveis", sa.Column("views", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("imoveis", sa.Column("contatos", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "tenant_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenant_api_keys_uuid", "tenant_api_keys", ["uuid"], unique=True)
    op.create_index("ix_tenant_api_keys_tenant_id", "tenant_api_keys", ["tenant_id"], unique=True)
    op.create_index("ix_tenant_api_keys_key_hash", "tenant_api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_api_keys_key_hash", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_tenant_id", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_uuid", table_name="tenant_api_keys")
    op.drop_table("tenant_api_keys")

    op.drop_column("imoveis", "contatos")
    op.drop_column("imoveis", "views")

    op.alter_column("leads", "corretor_id", existing_type=sa.Uuid(), nullable=False)
