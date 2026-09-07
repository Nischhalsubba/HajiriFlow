"""Add device platform and immutable raw attendance evidence.

Revision ID: 20260907_0005
Revises: 20260907_0004
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0005"
down_revision: str | None = "20260907_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("vendor", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("serial_number", sa.String(length=160), nullable=True),
        sa.Column("adapter_key", sa.String(length=120), nullable=False),
        sa.Column("endpoint_uri", sa.String(length=500), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("pull_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'error')",
            name="device_valid_status",
        ),
        sa.CheckConstraint(
            "pull_interval_seconds >= 60", name="device_minimum_pull_interval"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_device_org_code"),
        sa.UniqueConstraint(
            "organization_id", "serial_number", name="uq_device_org_serial"
        ),
    )
    op.create_index(
        "ix_devices_org_status", "devices", ["organization_id", "status"], unique=False
    )
    op.create_index(
        "ix_devices_adapter_status", "devices", ["adapter_key", "status"], unique=False
    )

    op.create_table(
        "device_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.String(length=120), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version >= 1", name="device_credential_positive_version"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id", "version", name="uq_device_credential_version"
        ),
    )
    op.create_index(
        "ix_device_credentials_device_active",
        "device_credentials",
        ["device_id", "retired_at"],
        unique=False,
    )

    op.create_table(
        "device_pull_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("cursor_before", sa.String(length=500), nullable=True),
        sa.Column("cursor_after", sa.String(length=500), nullable=True),
        sa.Column("ingested_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode IN ('scheduled', 'immediate')", name="device_pull_session_valid_mode"
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'skipped')",
            name="device_pull_session_valid_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 1", name="device_pull_session_positive_attempts"
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="device_pull_session_valid_times",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_pull_sessions_device_started",
        "device_pull_sessions",
        ["device_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_device_pull_sessions_org_status",
        "device_pull_sessions",
        ["organization_id", "status"],
        unique=False,
    )

    op.create_table(
        "raw_punches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("pull_session_id", sa.Uuid(), nullable=True),
        sa.Column("external_event_id", sa.String(length=200), nullable=True),
        sa.Column("device_user_identifier", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("punch_kind", sa.String(length=20), nullable=False),
        sa.Column("verification_method", sa.String(length=80), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "punch_kind IN ('in', 'out', 'break', 'unknown')",
            name="raw_punch_valid_kind",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pull_session_id"], ["device_pull_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id", "source_fingerprint", name="uq_raw_punch_device_fingerprint"
        ),
    )
    op.create_index(
        "ix_raw_punches_org_time",
        "raw_punches",
        ["organization_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_raw_punches_device_time",
        "raw_punches",
        ["device_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_raw_punches_device_user",
        "raw_punches",
        ["device_id", "device_user_identifier"],
        unique=False,
    )

    op.create_table(
        "device_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("external_user_id", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("privilege", sa.String(length=80), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("template_count", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id", "external_user_id", name="uq_device_user_external_id"
        ),
    )
    op.create_index(
        "ix_device_users_org_device",
        "device_users",
        ["organization_id", "device_id"],
        unique=False,
    )

    op.create_table(
        "device_employee_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_user_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="device_employee_mapping_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["device_user_id"], ["device_users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_user_id", name="uq_device_employee_mapping_user"),
    )
    op.create_index(
        "ix_device_employee_mappings_employee",
        "device_employee_mappings",
        ["organization_id", "employee_id"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_raw_punch_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'raw_punches are immutable';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER raw_punches_immutable
            BEFORE UPDATE OR DELETE ON raw_punches
            FOR EACH ROW EXECUTE FUNCTION prevent_raw_punch_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS raw_punches_immutable ON raw_punches")
        op.execute("DROP FUNCTION IF EXISTS prevent_raw_punch_mutation()")

    op.drop_index(
        "ix_device_employee_mappings_employee", table_name="device_employee_mappings"
    )
    op.drop_table("device_employee_mappings")
    op.drop_index("ix_device_users_org_device", table_name="device_users")
    op.drop_table("device_users")
    op.drop_index("ix_raw_punches_device_user", table_name="raw_punches")
    op.drop_index("ix_raw_punches_device_time", table_name="raw_punches")
    op.drop_index("ix_raw_punches_org_time", table_name="raw_punches")
    op.drop_table("raw_punches")
    op.drop_index(
        "ix_device_pull_sessions_org_status", table_name="device_pull_sessions"
    )
    op.drop_index(
        "ix_device_pull_sessions_device_started", table_name="device_pull_sessions"
    )
    op.drop_table("device_pull_sessions")
    op.drop_index(
        "ix_device_credentials_device_active", table_name="device_credentials"
    )
    op.drop_table("device_credentials")
    op.drop_index("ix_devices_adapter_status", table_name="devices")
    op.drop_index("ix_devices_org_status", table_name="devices")
    op.drop_table("devices")
