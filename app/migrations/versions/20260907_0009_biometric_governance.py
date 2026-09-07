"""Add biometric consent and deletion governance.

Revision ID: 20260907_0009
Revises: 20260907_0008
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0009"
down_revision: str | None = "20260907_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "biometric_consent_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("purpose", sa.String(length=240), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('granted', 'declined', 'revoked')",
            name="biometric_consent_valid_decision",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_biometric_consent_employee_time",
        "biometric_consent_events",
        ["organization_id", "employee_id", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "biometric_deletion_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("device_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_by", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_receipt_hash", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="biometric_deletion_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["device_user_id"], ["device_users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_biometric_deletion_org_status",
        "biometric_deletion_requests",
        ["organization_id", "status", "requested_at"],
        unique=False,
    )
    op.create_index(
        "ix_biometric_deletion_employee",
        "biometric_deletion_requests",
        ["organization_id", "employee_id", "requested_at"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_biometric_consent_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'biometric consent events are append-only';
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE TRIGGER biometric_consent_no_update
            BEFORE UPDATE ON biometric_consent_events
            FOR EACH ROW EXECUTE FUNCTION prevent_biometric_consent_mutation();
            """
        )
        op.execute(
            """
            CREATE TRIGGER biometric_consent_no_delete
            BEFORE DELETE ON biometric_consent_events
            FOR EACH ROW EXECUTE FUNCTION prevent_biometric_consent_mutation();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS biometric_consent_no_delete ON biometric_consent_events"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS biometric_consent_no_update ON biometric_consent_events"
        )
        op.execute("DROP FUNCTION IF EXISTS prevent_biometric_consent_mutation()")

    op.drop_index(
        "ix_biometric_deletion_employee", table_name="biometric_deletion_requests"
    )
    op.drop_index(
        "ix_biometric_deletion_org_status", table_name="biometric_deletion_requests"
    )
    op.drop_table("biometric_deletion_requests")
    op.drop_index(
        "ix_biometric_consent_employee_time", table_name="biometric_consent_events"
    )
    op.drop_table("biometric_consent_events")
