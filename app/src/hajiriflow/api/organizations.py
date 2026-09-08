from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import RequestIdentity, current_identity, get_db
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.identity.permissions import has_permission

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


class AccessibleOrganizationView(BaseModel):
    id: UUID
    display_name: str
    legal_name: str
    timezone: str
    status: str


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
