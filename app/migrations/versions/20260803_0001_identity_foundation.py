"""Create identity, authorization, session, and audit foundation.

Revision ID: 20260803_0001
Revises:
Create Date: 2026-08-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_user_accounts_valid_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_accounts"),
        sa.UniqueConstraint("username", name="uq_user_accounts_username"),
    )
    op.create_index("ix_user_accounts_status", "user_accounts", ["status"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            ondelete="CASCADE",
            name="fk_role_permissions_permission_id_permissions",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            ondelete="CASCADE",
            name="fk_role_permissions_role_id_roles",
        ),
        sa.PrimaryKeyConstraint(
            "role_id",
            "permission_id",
            name="pk_role_permissions",
        ),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "scope_type IN ('global', 'organization')",
            name="ck_user_roles_valid_scope_type",
        ),
        sa.CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'organization' AND scope_id IS NOT NULL)",
            name="ck_user_roles_scope_matches_type",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_user_roles_valid_effective_range",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["user_accounts.id"],
            ondelete="SET NULL",
            name="fk_user_roles_assigned_by_user_accounts",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            ondelete="CASCADE",
            name="fk_user_roles_role_id_roles",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            ondelete="CASCADE",
            name="fk_user_roles_user_id_user_accounts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_roles"),
        sa.UniqueConstraint(
            "user_id",
            "role_id",
            "scope_type",
            "scope_id",
            "starts_at",
            name="uq_user_roles_assignment",
        ),
    )
    op.create_index(
        "ix_user_roles_user_active",
        "user_roles",
        ["user_id", "starts_at", "ends_at"],
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            ondelete="CASCADE",
            name="fk_auth_sessions_user_id_user_accounts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_active",
        "auth_sessions",
        ["expires_at", "revoked_at"],
    )
    op.create_index(
        "ix_auth_sessions_user_expires",
        "auth_sessions",
        ["user_id", "expires_at"],
    )

    op.create_table(
        "authentication_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_hash", sa.String(length=128), nullable=False),
        sa.Column("client_ip_hash", sa.String(length=128), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "result IN ('success', 'failure')",
            name="ck_authentication_attempts_valid_result",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_authentication_attempts"),
    )
    op.create_index(
        "ix_auth_attempts_ip_time",
        "authentication_attempts",
        ["client_ip_hash", "attempted_at"],
    )
    op.create_index(
        "ix_auth_attempts_subject_time",
        "authentication_attempts",
        ["subject_hash", "attempted_at"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=150), nullable=False),
        sa.Column("object_type", sa.String(length=150), nullable=False),
        sa.Column("object_id", sa.String(length=150), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("context_data", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_accounts.id"],
            ondelete="SET NULL",
            name="fk_audit_events_actor_user_id_user_accounts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_actor",
        "audit_events",
        ["actor_user_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_object",
        "audit_events",
        ["object_type", "object_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_time",
        "audit_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_time", table_name="audit_events")
    op.drop_index("ix_audit_events_object", table_name="audit_events")
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(
        "ix_auth_attempts_subject_time",
        table_name="authentication_attempts",
    )
    op.drop_index(
        "ix_auth_attempts_ip_time",
        table_name="authentication_attempts",
    )
    op.drop_table("authentication_attempts")
    op.drop_index("ix_auth_sessions_user_expires", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_active", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_user_roles_user_active", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_index("ix_user_accounts_status", table_name="user_accounts")
    op.drop_table("user_accounts")
