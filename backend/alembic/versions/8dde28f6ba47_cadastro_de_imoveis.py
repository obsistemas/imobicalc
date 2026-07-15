"""cadastro de imoveis

Revision ID: 8dde28f6ba47
Revises: 166887b79f27
Create Date: 2026-07-15 12:37:55.847568

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8dde28f6ba47"
down_revision: Union[str, Sequence[str], None] = "166887b79f27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "imoveis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("corretor_id", sa.Uuid(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("cep", sa.String(length=9), nullable=False),
        sa.Column("logradouro", sa.String(length=200), nullable=True),
        sa.Column("bairro", sa.String(length=120), nullable=False),
        sa.Column("cidade", sa.String(length=120), nullable=False),
        sa.Column("estado", sa.String(length=2), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column(
            "tipo",
            sa.Enum("apartamento", "casa", "terreno", "comercial", "galpao", native_enum=False, name="imoveltipo"),
            nullable=False,
        ),
        sa.Column("area_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("area_util", sa.Numeric(12, 2), nullable=True),
        sa.Column("quartos", sa.Integer(), nullable=True),
        sa.Column("banheiros", sa.Integer(), nullable=True),
        sa.Column("suites", sa.Integer(), nullable=True),
        sa.Column("vagas", sa.Integer(), nullable=True),
        sa.Column("andar", sa.Integer(), nullable=True),
        sa.Column("idade_anos", sa.Integer(), nullable=True),
        sa.Column(
            "conservacao",
            sa.Enum("otima", "boa", "regular", "ruim", native_enum=False, name="conservacao"),
            nullable=True,
        ),
        sa.Column("valor_anunciado", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "disponivel", "vendido", "alugado", "reservado", native_enum=False, name="imovelstatus"
            ),
            nullable=False,
            server_default="disponivel",
        ),
        sa.Column("matricula", sa.String(length=50), nullable=True),
        sa.Column("iptu_quitado", sa.Boolean(), nullable=True),
        sa.Column("escritura_ok", sa.Boolean(), nullable=True),
        sa.Column("fotos", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("data_venda", sa.Date(), nullable=True),
    )
    op.create_index("ix_imoveis_uuid", "imoveis", ["uuid"], unique=True)
    op.create_index("ix_imoveis_tenant_id", "imoveis", ["tenant_id"])
    op.create_index("ix_imoveis_corretor_id", "imoveis", ["corretor_id"])


def downgrade() -> None:
    op.drop_index("ix_imoveis_corretor_id", table_name="imoveis")
    op.drop_index("ix_imoveis_tenant_id", table_name="imoveis")
    op.drop_index("ix_imoveis_uuid", table_name="imoveis")
    op.drop_table("imoveis")
