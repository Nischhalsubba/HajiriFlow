from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

FULL_ACCESS = "system.full_access"


class ScopeType(StrEnum):
    GLOBAL = "global"
    ORGANIZATION = "organization"


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    permission: str
    scope_type: ScopeType = ScopeType.GLOBAL
    scope_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.scope_type is ScopeType.GLOBAL and self.scope_id is not None:
            raise ValueError("global grants cannot contain a scope_id")
        if self.scope_type is ScopeType.ORGANIZATION and self.scope_id is None:
            raise ValueError("organization grants require a scope_id")


def has_permission(
    grants: set[PermissionGrant] | frozenset[PermissionGrant],
    required_permission: str,
    *,
    organization_id: UUID | None = None,
) -> bool:
    """Return True only when an explicit applicable grant exists."""

    for grant in grants:
        if grant.permission not in {required_permission, FULL_ACCESS}:
            continue
        if grant.scope_type is ScopeType.GLOBAL:
            return True
        if organization_id is not None and grant.scope_id == organization_id:
            return True
    return False


def collect_role_grants(
    role_codes: set[str] | frozenset[str],
    grants_by_role: dict[str, set[PermissionGrant] | frozenset[PermissionGrant]],
) -> frozenset[PermissionGrant]:
    """Unknown roles intentionally contribute no permissions."""

    resolved: set[PermissionGrant] = set()
    for role_code in role_codes:
        resolved.update(grants_by_role.get(role_code, ()))
    return frozenset(resolved)
