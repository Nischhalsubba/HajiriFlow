from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.db.models.identity import Permission, Role, RolePermission
from hajiriflow.identity.permissions import FULL_ACCESS

PERMISSIONS = {
    FULL_ACCESS: "Access every protected HajiriFlow action.",
    "identity.user.read": "View user accounts and their status.",
    "identity.user.create": "Create user accounts.",
    "identity.user.manage": "Activate, disable, and update user accounts.",
    "identity.role.assign": "Assign roles to user accounts.",
    "identity.audit.read": "View redacted identity and access audit events.",
}

ROLES = {
    "system_administrator": {
        "name": "System administrator",
        "permissions": {FULL_ACCESS},
    },
    "identity_administrator": {
        "name": "Identity administrator",
        "permissions": {
            "identity.user.read",
            "identity.user.create",
            "identity.user.manage",
            "identity.role.assign",
            "identity.audit.read",
        },
    },
    "employee": {
        "name": "Employee",
        "permissions": set(),
    },
}


def seed_identity_catalog(session: Session) -> None:
    permission_by_code = {
        item.code: item for item in session.scalars(select(Permission)).all()
    }
    for code, description in PERMISSIONS.items():
        if code not in permission_by_code:
            item = Permission(code=code, description=description)
            session.add(item)
            permission_by_code[code] = item

    role_by_code = {item.code: item for item in session.scalars(select(Role)).all()}
    for code, definition in ROLES.items():
        if code not in role_by_code:
            role = Role(
                code=code,
                name=str(definition["name"]),
                description=None,
                is_system=True,
            )
            session.add(role)
            role_by_code[code] = role

    session.flush()
    existing = {
        (item.role_id, item.permission_id)
        for item in session.scalars(select(RolePermission)).all()
    }
    for role_code, definition in ROLES.items():
        role = role_by_code[role_code]
        for permission_code in definition["permissions"]:
            permission = permission_by_code[str(permission_code)]
            key = (role.id, permission.id)
            if key not in existing:
                session.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )
                existing.add(key)
