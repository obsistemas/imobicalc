"""integracao portais - finalidade

Revision ID: b47afd257a74
Revises: 3461e5b1fb3c
Create Date: 2026-07-29 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b47afd257a74"
down_revision: Union[str, Sequence[str], None] = "3461e5b1fb3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    finalidade_enum = sa.Enum("venda", "aluguel", name="finalidade", native_enum=False)
    op.add_column("imoveis", sa.Column("finalidade", finalidade_enum, nullable=True))


def downgrade() -> None:
    op.drop_column("imoveis", "finalidade")
