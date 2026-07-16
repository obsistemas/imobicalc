"""motor de avaliacao e base de precos de mercado

Revision ID: 1ee518ccc841
Revises: 8dde28f6ba47
Create Date: 2026-07-16 00:04:16.198222

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "1ee518ccc841"
down_revision: Union[str, Sequence[str], None] = "8dde28f6ba47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIPO_ENUM = sa.Enum(
    "apartamento", "casa", "terreno", "comercial", "galpao", native_enum=False, name="imoveltipo"
)


def upgrade() -> None:
    op.create_table(
        "preco_mercado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("bairro", sa.String(length=120), nullable=True),
        sa.Column("cidade", sa.String(length=120), nullable=True),
        sa.Column("estado", sa.String(length=2), nullable=True),
        sa.Column("tipo", _TIPO_ENUM, nullable=False),
        sa.Column("preco_m2", sa.Numeric(12, 4), nullable=False),
        sa.Column("fonte", sa.String(length=200), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("bairro", "cidade", "tipo", name="uq_preco_mercado_bairro_cidade_tipo"),
    )
    op.create_index("ix_preco_mercado_uuid", "preco_mercado", ["uuid"], unique=True)

    op.create_table(
        "custo_construcao_padrao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column(
            "padrao",
            sa.Enum("baixo", "normal", "alto", native_enum=False, name="padraoconstrutivo"),
            nullable=False,
            unique=True,
        ),
        sa.Column("custo_m2", sa.Numeric(12, 4), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_custo_construcao_padrao_uuid", "custo_construcao_padrao", ["uuid"], unique=True)

    op.create_table(
        "avaliacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("imovel_id", sa.Uuid(), nullable=False),
        sa.Column("corretor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "metodo",
            sa.Enum("comparativo", "reproducao", "renda", native_enum=False, name="metodoavaliacao"),
            nullable=False,
        ),
        sa.Column("valor_estimado", sa.Numeric(12, 4), nullable=False),
        sa.Column("valor_min", sa.Numeric(12, 4), nullable=False),
        sa.Column("valor_max", sa.Numeric(12, 4), nullable=False),
        sa.Column("fatores", sa.Text(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_avaliacoes_uuid", "avaliacoes", ["uuid"], unique=True)
    op.create_index("ix_avaliacoes_tenant_id", "avaliacoes", ["tenant_id"])
    op.create_index("ix_avaliacoes_imovel_id", "avaliacoes", ["imovel_id"])
    op.create_index("ix_avaliacoes_corretor_id", "avaliacoes", ["corretor_id"])


def downgrade() -> None:
    op.drop_index("ix_avaliacoes_corretor_id", table_name="avaliacoes")
    op.drop_index("ix_avaliacoes_imovel_id", table_name="avaliacoes")
    op.drop_index("ix_avaliacoes_tenant_id", table_name="avaliacoes")
    op.drop_index("ix_avaliacoes_uuid", table_name="avaliacoes")
    op.drop_table("avaliacoes")

    op.drop_index("ix_custo_construcao_padrao_uuid", table_name="custo_construcao_padrao")
    op.drop_table("custo_construcao_padrao")

    op.drop_index("ix_preco_mercado_uuid", table_name="preco_mercado")
    op.drop_table("preco_mercado")
