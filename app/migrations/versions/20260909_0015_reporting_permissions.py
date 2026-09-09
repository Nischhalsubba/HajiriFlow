"""Add attendance report export and employee self-service permissions.

Revision ID: 20260909_0015
Revises: 20260909_0014
Create Date: 2026-09-09
"""
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0015"
down_revision: str | None = "20260909_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "attendance.export": "Export attendance reports within authorized organization scope.",
    "attendance.self.read": "View the signed-in employee's own attendance and evidence.",
}

ROLE_PERMISSIONS = {
    "workforce_administrator": ("attendance.export",),
    "payroll_administrator": ("attendance.export",),
    "employee": ("attendance.self.read",),
}


def upgrade() -> None:
    bind = op.get_bind()
    for code, description in PERMISSIONS.items():
        bind.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, created_at) "
                "VALUES (:id, :code, :description, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {
                "id": str(uuid4()),
                "code": code,
                "description": description,
            },
        )
    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        for permission_code in permission_codes:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT roles.id, permissions.id FROM roles, permissions "
                    "WHERE roles.code = :role_code AND permissions.code = :permission_code "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "role_code": role_code,
                    "permission_code": permission_code,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        for permission_code in permission_codes:
            bind.execute(
                sa.text(
                    "DELETE FROM role_permissions WHERE role_id IN "
                    "(SELECT id FROM roles WHERE code = :role_code) AND permission_id IN "
                    "(SELECT id FROM permissions WHERE code = :permission_code)"
                ),
                {
                    "role_code": role_code,
                    "permission_code": permission_code,
                },
            )
    for permission_code in PERMISSIONS:
        bind.execute(
            sa.text("DELETE FROM permissions WHERE code = :permission_code"),
            {"permission_code": permission_code},
        )
