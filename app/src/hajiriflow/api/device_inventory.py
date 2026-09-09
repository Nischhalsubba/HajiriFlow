from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import RequestIdentity, get_db, require_organization_permission
from hajiriflow.db.models.device import Device, DeviceEmployeeMapping, DeviceUser

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/devices",
    tags=["device-inventory"],
)


class DeviceUserInventoryView(BaseModel):
    id: UUID
    device_id: UUID
    external_user_id: str
    display_name: str | None
    privilege: str | None
    active: bool
    template_count: int
    mapped_employee_id: UUID | None
    first_seen_at: datetime
    last_seen_at: datetime


@router.get("/{device_id}/user-inventory", response_model=list[DeviceUserInventoryView])
def device_user_inventory(
    organization_id: UUID,
    device_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("device.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DeviceUserInventoryView]:
    device = session.get(Device, device_id)
    if not device or device.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    query = select(DeviceUser).where(
        DeviceUser.organization_id == organization_id,
        DeviceUser.device_id == device_id,
    )
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            DeviceUser.external_user_id.ilike(pattern) | DeviceUser.display_name.ilike(pattern)
        )
    users = session.scalars(
        query.order_by(DeviceUser.external_user_id).offset(offset).limit(limit)
    ).all()
    result: list[DeviceUserInventoryView] = []
    for user in users:
        employee_id = session.scalar(
            select(DeviceEmployeeMapping.employee_id).where(
                DeviceEmployeeMapping.device_user_id == user.id,
                DeviceEmployeeMapping.status == "active",
            )
        )
        result.append(
            DeviceUserInventoryView(
                id=user.id,
                device_id=user.device_id,
                external_user_id=user.external_user_id,
                display_name=user.display_name,
                privilege=user.privilege,
                active=user.active,
                template_count=user.template_count,
                mapped_employee_id=employee_id,
                first_seen_at=user.first_seen_at,
                last_seen_at=user.last_seen_at,
            )
        )
    return result
