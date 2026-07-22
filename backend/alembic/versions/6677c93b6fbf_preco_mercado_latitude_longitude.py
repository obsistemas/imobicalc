"""preco mercado latitude longitude

Revision ID: 6677c93b6fbf
Revises: e6aa8e67038d
Create Date: 2026-07-21 16:40:53.235869

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "6677c93b6fbf"
down_revision: Union[str, Sequence[str], None] = "e6aa8e67038d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("preco_mercado", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("preco_mercado", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("preco_mercado", "longitude")
    op.drop_column("preco_mercado", "latitude")
