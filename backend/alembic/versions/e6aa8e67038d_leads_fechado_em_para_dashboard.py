"""leads fechado_em para dashboard

Revision ID: e6aa8e67038d
Revises: 477843727443
Create Date: 2026-07-16 21:56:35.741492

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e6aa8e67038d"
down_revision: Union[str, Sequence[str], None] = "477843727443"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("fechado_em", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "fechado_em")
