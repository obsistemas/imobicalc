"""licenciamento e auditoria

Revision ID: 166887b79f27
Revises: 8626e556133f
Create Date: 2026-07-14 23:42:18.868281

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "166887b79f27"
down_revision: Union[str, Sequence[str], None] = "8626e556133f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=20), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column("max_imoveis", sa.Integer(), nullable=True),
        sa.Column("preco_mensal", sa.Numeric(12, 4), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_plans_uuid", "plans", ["uuid"], unique=True)
    op.create_index("ix_plans_nome", "plans", ["nome"], unique=True)

    op.create_table(
        "licenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("preco_congelado", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "status",
            sa.Enum("trial", "active", "past_due", "suspended", "cancelled", native_enum=False, name="licensestatus"),
            nullable=False,
            server_default="trial",
        ),
        sa.Column("trial_termina_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("past_due_desde", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspensa_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_licenses_tenant_id"),
    )
    op.create_index("ix_licenses_uuid", "licenses", ["uuid"], unique=True)
    op.create_index("ix_licenses_tenant_id", "licenses", ["tenant_id"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("license_id", sa.Integer(), sa.ForeignKey("licenses.id"), nullable=False),
        sa.Column("valor", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "paid", "failed", "refunded", native_enum=False, name="invoicestatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("ciclo_mes", sa.Integer(), nullable=False),
        sa.Column("ciclo_ano", sa.Integer(), nullable=False),
        sa.Column("vencimento", sa.Date(), nullable=False),
        sa.Column("externa_id", sa.String(length=100), nullable=True),
        sa.Column("pago_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invoices_uuid", "invoices", ["uuid"], unique=True)
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("ix_invoices_externa_id", "invoices", ["externa_id"])

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column("event_id_externo", sa.String(length=150), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("processado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_events_uuid", "payment_events", ["uuid"], unique=True)
    op.create_index("ix_payment_events_tenant_id", "payment_events", ["tenant_id"])
    op.create_index("ix_payment_events_event_id_externo", "payment_events", ["event_id_externo"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("ator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acao", sa.String(length=100), nullable=False),
        sa.Column("entidade", sa.String(length=50), nullable=False),
        sa.Column("entidade_id", sa.String(length=64), nullable=False),
        sa.Column("antes", sa.Text(), nullable=True),
        sa.Column("depois", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_uuid", "audit_logs", ["uuid"], unique=True)
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_uuid", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_payment_events_event_id_externo", table_name="payment_events")
    op.drop_index("ix_payment_events_tenant_id", table_name="payment_events")
    op.drop_index("ix_payment_events_uuid", table_name="payment_events")
    op.drop_table("payment_events")

    op.drop_index("ix_invoices_externa_id", table_name="invoices")
    op.drop_index("ix_invoices_tenant_id", table_name="invoices")
    op.drop_index("ix_invoices_uuid", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_licenses_tenant_id", table_name="licenses")
    op.drop_index("ix_licenses_uuid", table_name="licenses")
    op.drop_table("licenses")

    op.drop_index("ix_plans_nome", table_name="plans")
    op.drop_index("ix_plans_uuid", table_name="plans")
    op.drop_table("plans")
