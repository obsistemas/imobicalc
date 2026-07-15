"""2fa e convites

Revision ID: 8626e556133f
Revises: 4ad4b94bd77c
Create Date: 2026-07-14 22:03:00.305956

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8626e556133f"
down_revision: Union[str, Sequence[str], None] = "4ad4b94bd77c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("totp_recovery_codes", sa.Text(), nullable=True))

    op.create_table(
        "convites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "papel",
            sa.Enum("admin", "corretor", native_enum=False, name="papel"),
            nullable=False,
            server_default="corretor",
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aceito_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_convites_uuid", "convites", ["uuid"], unique=True)
    op.create_index("ix_convites_tenant_id", "convites", ["tenant_id"])
    op.create_index("ix_convites_email", "convites", ["email"])
    op.create_index("ix_convites_token", "convites", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_convites_token", table_name="convites")
    op.drop_index("ix_convites_email", table_name="convites")
    op.drop_index("ix_convites_tenant_id", table_name="convites")
    op.drop_index("ix_convites_uuid", table_name="convites")
    op.drop_table("convites")

    op.drop_column("users", "totp_recovery_codes")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
