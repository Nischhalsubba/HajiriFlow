from uuid import uuid4

import pytest

from hajiriflow.identity.permissions import (
    FULL_ACCESS,
    PermissionGrant,
    ScopeType,
    collect_role_grants,
    has_permission,
)


def test_unknown_role_is_denied() -> None:
    grants = collect_role_grants({"made-up-role"}, {})
    assert not has_permission(grants, "attendance.read")


def test_global_grant_applies_to_any_organization() -> None:
    grants = frozenset({PermissionGrant("attendance.read")})
    assert has_permission(grants, "attendance.read", organization_id=uuid4())


def test_organization_grant_is_scoped() -> None:
    allowed_org = uuid4()
    other_org = uuid4()
    grants = frozenset(
        {
            PermissionGrant(
                "attendance.read",
                scope_type=ScopeType.ORGANIZATION,
                scope_id=allowed_org,
            )
        }
    )
    assert has_permission(grants, "attendance.read", organization_id=allowed_org)
    assert not has_permission(grants, "attendance.read", organization_id=other_org)
    assert not has_permission(grants, "attendance.read")


def test_full_access_requires_explicit_grant() -> None:
    assert not has_permission(frozenset(), "payroll.run.generate")
    assert has_permission(
        frozenset({PermissionGrant(FULL_ACCESS)}),
        "payroll.run.generate",
    )


def test_invalid_scope_shape_is_rejected() -> None:
    with pytest.raises(ValueError):
        PermissionGrant("attendance.read", scope_type=ScopeType.ORGANIZATION)
