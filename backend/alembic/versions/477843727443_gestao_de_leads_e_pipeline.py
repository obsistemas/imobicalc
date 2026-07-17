"""gestao de leads e pipeline

Revision ID: 477843727443
Revises: 9c4aa0df08d5
Create Date: 2026-07-16 19:16:02.818287

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "477843727443"
down_revision: Union[str, Sequence[str], None] = "9c4aa0df08d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("corretor_id", sa.Uuid(), nullable=False),
        sa.Column("imovel_id", sa.Uuid(), nullable=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("telefone", sa.String(length=30), nullable=True),
        sa.Column(
            "origem",
            sa.Enum("site", "indicacao", "portal", "redes_sociais", "outro", native_enum=False, name="origemlead"),
            nullable=False,
        ),
        sa.Column(
            "estagio",
            sa.Enum(
                "novo", "contatado", "visita", "proposta", "fechado", "perdido",
                native_enum=False, name="estagiolead",
            ),
            nullable=False,
            server_default="novo",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_leads_uuid", "leads", ["uuid"], unique=True)
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"])
    op.create_index("ix_leads_corretor_id", "leads", ["corretor_id"])
    op.create_index("ix_leads_imovel_id", "leads", ["imovel_id"])

    op.create_table(
        "leads_notas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("autor_id", sa.Uuid(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("automatica", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leads_notas_uuid", "leads_notas", ["uuid"], unique=True)
    op.create_index("ix_leads_notas_tenant_id", "leads_notas", ["tenant_id"])
    op.create_index("ix_leads_notas_lead_id", "leads_notas", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_leads_notas_lead_id", table_name="leads_notas")
    op.drop_index("ix_leads_notas_tenant_id", table_name="leads_notas")
    op.drop_index("ix_leads_notas_uuid", table_name="leads_notas")
    op.drop_table("leads_notas")

    op.drop_index("ix_leads_imovel_id", table_name="leads")
    op.drop_index("ix_leads_corretor_id", table_name="leads")
    op.drop_index("ix_leads_tenant_id", table_name="leads")
    op.drop_index("ix_leads_uuid", table_name="leads")
    op.drop_table("leads")
