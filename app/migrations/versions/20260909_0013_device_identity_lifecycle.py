"""Add previewed device identity actions and encrypted archives.

Revision ID: 20260909_0013
Revises: 20260909_0012
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0013"
down_revision: str | None = "20260909_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_identity_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_device_id", sa.Uuid(), nullable=True),
        sa.Column("target_device_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("request_data", sa.JSON(), nullable=False),
        sa.Column("preview_data", sa.JSON(), nullable=False),
        sa.Column("preview_hash", sa.String(length=64), nullable=False),
        sa.Column("result_data", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action_type IN ('push_users', 'migrate_users', 'archive_export', 'archive_restore')",
            name="device_identity_action_valid_type",
        ),
        sa.CheckConstraint(
            "status IN ('preview', 'approved', 'running', 'succeeded', 'partial', 'failed', 'cancelled')",
            name="device_identity_action_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_identity_actions_org_created",
        "device_identity_actions",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_device_identity_actions_status_created",
        "device_identity_actions",
        ["status", "created_at"],
    )

    op.create_table(
        "device_archives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_device_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("key_id", sa.String(length=100), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("manifest_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('ready', 'restored', 'failed')",
            name="device_archive_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_device_id"], ["devices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_archives_org_created",
        "device_archives",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_archives_org_created", table_name="device_archives")
    op.drop_table("device_archives")
    op.drop_index(
        "ix_device_identity_actions_status_created",
        table_name="device_identity_actions",
    )
    op.drop_index(
        "ix_device_identity_actions_org_created",
        table_name="device_identity_actions",
    )
    op.drop_table("device_identity_actions")
