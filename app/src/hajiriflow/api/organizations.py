from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    current_identity,
    get_db,
    require_organization_permission,
)
from hajiriflow.db.models.identity import Role, UserAccount, UserRole
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.identity.permissions import has_permission

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


class AccessibleOrganizationView(BaseModel):
    id: UUID
    display_name: str
    legal_name: str
    timezone: str
    status: str


class OrganizationOperatorView(BaseModel):
    id: UUID
    display_name: str
    role_codes: list[str]


@router.get("", response_model=list[AccessibleOrganizationView])
def list_accessible_organizations(
    identity: Annotated[RequestIdentity, Depends(current_identity)],
    session: Annotated[Session, Depends(get_db)],
) -> list[AccessibleOrganizationView]:
    organizations = session.scalars(
        select(CompanyProfile)
        .where(CompanyProfile.status == "active")
        .order_by(CompanyProfile.display_name, CompanyProfile.id)
    ).all()
    return [
        AccessibleOrganizationView(
            id=item.id,
            display_name=item.display_name,
            legal_name=item.legal_name,
            timezone=item.timezone,
            status=item.status,
        )
        for item in organizations
        if has_permission(
            identity.principal.grants,
            "organization.read",
            organization_id=item.id,
        )
    ]


@router.get(
    "/{organization_id}/operators",
    response_model=list[OrganizationOperatorView],
)
def list_organization_operators(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("organization.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[OrganizationOperatorView]:
    now = datetime.now(UTC)
    rows = session.execute(
        select(UserAccount, Role.code)
        .join(UserRole, UserRole.user_id == UserAccount.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserAccount.status == "active",
            UserRole.starts_at <= now,
            or_(UserRole.ends_at.is_(None), UserRole.ends_at > now),
            or_(
                UserRole.scope_type == "global",
                and_(
                    UserRole.scope_type == "organization",
                    UserRole.scope_id == organization_id,
                ),
            ),
        )
        .order_by(UserAccount.display_name, UserAccount.id, Role.code)
    ).all()

    operators: dict[UUID, OrganizationOperatorView] = {}
    for user, role_code in rows:
        existing = operators.get(user.id)
        if existing is None:
            operators[user.id] = OrganizationOperatorView(
                id=user.id,
                display_name=user.display_name,
                role_codes=[role_code],
            )
        elif role_code not in existing.role_codes:
            existing.role_codes.append(role_code)
    return list(operators.values())
