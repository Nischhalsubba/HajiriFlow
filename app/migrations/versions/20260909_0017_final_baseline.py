"""Complete identity linking and operations permissions.

Revision ID: 20260909_0017
Revises: 20260909_0016
Create Date: 2026-09-09
"""
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0017"
down_revision: str | None = "20260909_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            "SELECT employee_id FROM user_accounts "
            "WHERE employee_id IS NOT NULL GROUP BY employee_id "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot enforce one-account-per-employee: duplicate employee links exist."
        )
    op.create_index(
        "uq_user_accounts_employee_id",
        "user_accounts",
        ["employee_id"],
        unique=True,
    )

    permission_code = "operations.read"
    bind.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description, created_at) "
            "VALUES (:id, :code, :description, CURRENT_TIMESTAMP) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {
            "id": str(uuid4()),
            "code": permission_code,
            "description": "View sanitized operational health, metrics, and alert indicators.",
        },
    )
    for role_code in ("workforce_administrator", "payroll_administrator"):
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT roles.id, permissions.id FROM roles, permissions "
                "WHERE roles.code = :role_code AND permissions.code = :permission_code "
                "ON CONFLICT DO NOTHING"
            ),
            {"role_code": role_code, "permission_code": permission_code},
        )


def downgrade() -> None:
    bind = op.get_bind()
    permission_code = "operations.read"
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = :permission_code)"
        ),
        {"permission_code": permission_code},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code = :permission_code"),
        {"permission_code": permission_code},
    )
    op.drop_index("uq_user_accounts_employee_id", table_name="user_accounts")
