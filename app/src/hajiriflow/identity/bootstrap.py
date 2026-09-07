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
    "organization.create": "Create an organization/company profile.",
    "organization.read": "View organization structure and company settings.",
    "organization.manage": "Manage organization structure and company settings.",
    "employee.read": "View employees and effective workforce assignments.",
    "employee.manage": "Manage employee lifecycle and organization assignments.",
    "shift.read": "View shift definitions and effective assignments.",
    "shift.manage": "Manage shift definitions and effective assignments.",
    "calendar.read": "View shared workday, holiday, and BS calendar decisions.",
    "calendar.manage": "Manage weekends and organization holidays.",
    "leave.read": "View organization leave policies, balances, and requests.",
    "leave.manage": "Manage leave policies and employee allocations.",
    "leave.approve": "Approve or reject employee leave requests.",
    "leave.request": "Request and view the signed-in employee's own leave.",
    "field_duty.read": "View organization field-duty requests.",
    "field_duty.approve": "Approve or reject field-duty requests.",
    "field_duty.request": "Request and view the signed-in employee's own field duty.",
    "device.read": "View organization devices, diagnostics, inventory, and pull history.",
    "device.manage": "Manage organization devices and encrypted device credentials.",
    "device.pull": "Request device pulls and view their results.",
    "device.mapping.manage": "Map device identities to employees.",
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
    "workforce_administrator": {
        "name": "Workforce administrator",
        "permissions": {
            "organization.create",
            "organization.read",
            "organization.manage",
            "employee.read",
            "employee.manage",
            "shift.read",
            "shift.manage",
            "calendar.read",
            "calendar.manage",
            "leave.read",
            "leave.manage",
            "leave.approve",
            "field_duty.read",
            "field_duty.approve",
            "device.read",
            "device.manage",
            "device.pull",
            "device.mapping.manage",
        },
    },
    "employee": {
        "name": "Employee",
        "permissions": {
            "calendar.read",
            "leave.request",
            "field_duty.request",
        },
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
