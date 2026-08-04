"""rbac 4 papeis

Revision ID: 53f31a2b4f63
Revises: b47afd257a74
Create Date: 2026-08-02 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "53f31a2b4f63"
down_revision: Union[str, Sequence[str], None] = "b47afd257a74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("assistente_de_id", sa.Uuid(), nullable=True))
    op.add_column("convites", sa.Column("assistente_de_id", sa.Uuid(), nullable=True))

    # papel é armazenado como string (native_enum=False) — a coluna original (migração
    # 4ad4b94bd77c) foi dimensionada em VARCHAR(8) a partir do enum antigo ("admin"/"corretor",
    # no máx. 8 chars). "assistente" tem 10 chars — sem alargar a coluna, o Postgres rejeita
    # qualquer INSERT/UPDATE com esse valor (`value too long for type character varying(8)`);
    # SQLite (usado nos testes) não aplica esse limite, então isso só aparece em produção.
    op.alter_column("users", "papel", type_=sa.String(10), existing_type=sa.String(8))
    op.alter_column("convites", "papel", type_=sa.String(10), existing_type=sa.String(8))

    # Todo `admin` vira `dono` (RN1: mesma pessoa, mesmas permissões, nome novo).
    op.execute("UPDATE users SET papel = 'dono' WHERE papel = 'admin'")


def downgrade() -> None:
    op.execute("UPDATE users SET papel = 'admin' WHERE papel = 'dono'")
    op.alter_column("convites", "papel", type_=sa.String(8), existing_type=sa.String(10))
    op.alter_column("users", "papel", type_=sa.String(8), existing_type=sa.String(10))
    op.drop_column("convites", "assistente_de_id")
    op.drop_column("users", "assistente_de_id")
