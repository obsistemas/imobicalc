"""sugestao de preco de anuncio

Revision ID: 9c4aa0df08d5
Revises: 1ee518ccc841
Create Date: 2026-07-16 15:49:06.020365

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "9c4aa0df08d5"
down_revision: Union[str, Sequence[str], None] = "1ee518ccc841"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sugestoes_preco",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("imovel_id", sa.Uuid(), nullable=False),
        sa.Column("avaliacao_id", sa.Uuid(), nullable=False),
        sa.Column("corretor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "urgencia",
            sa.Enum("rapido", "normal", "maximo", native_enum=False, name="urgencia"),
            nullable=False,
        ),
        sa.Column("preco_anuncio_sugerido", sa.Numeric(12, 4), nullable=False),
        sa.Column("valor_minimo_aceitavel", sa.Numeric(12, 4), nullable=False),
        sa.Column("fatores", sa.Text(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sugestoes_preco_uuid", "sugestoes_preco", ["uuid"], unique=True)
    op.create_index("ix_sugestoes_preco_tenant_id", "sugestoes_preco", ["tenant_id"])
    op.create_index("ix_sugestoes_preco_imovel_id", "sugestoes_preco", ["imovel_id"])
    op.create_index("ix_sugestoes_preco_avaliacao_id", "sugestoes_preco", ["avaliacao_id"])
    op.create_index("ix_sugestoes_preco_corretor_id", "sugestoes_preco", ["corretor_id"])


def downgrade() -> None:
    op.drop_index("ix_sugestoes_preco_corretor_id", table_name="sugestoes_preco")
    op.drop_index("ix_sugestoes_preco_avaliacao_id", table_name="sugestoes_preco")
    op.drop_index("ix_sugestoes_preco_imovel_id", table_name="sugestoes_preco")
    op.drop_index("ix_sugestoes_preco_tenant_id", table_name="sugestoes_preco")
    op.drop_index("ix_sugestoes_preco_uuid", table_name="sugestoes_preco")
    op.drop_table("sugestoes_preco")
