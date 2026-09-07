from datetime import date, time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
    require_permission,
)
from hajiriflow.workforce.service import WorkforceService

router = APIRouter(prefix="/api/v1/organizations", tags=["workforce"])


class CompanyCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=240)
    display_name: str = Field(min_length=1, max_length=200)
    timezone: str = Field(default="Asia/Kathmandu", min_length=1, max_length=64)


class CompanyView(BaseModel):
    id: UUID
    legal_name: str
    display_name: str
    timezone: str
    status: str


class NodeCreate(BaseModel):
    node_type: Literal["directorate", "department", "section", "unit"]
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None


class NodeView(BaseModel):
    id: UUID
    organization_id: UUID
    parent_id: UUID | None
    node_type: str
    code: str
    name: str
    status: str


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=200)
    joined_on: date
    user_account_id: UUID | None = None


class EmployeeStatusUpdate(BaseModel):
    status: Literal["active", "inactive", "terminated"]
    left_on: date | None = None


class EmployeeView(BaseModel):
    id: UUID
    organization_id: UUID
    employee_code: str
    display_name: str
    joined_on: date
    left_on: date | None
    status: str


class OrganizationAssignmentCreate(BaseModel):
    organization_node_id: UUID
    starts_on: date
    ends_on: date | None = None
    is_primary: bool = True


class OrganizationAssignmentView(BaseModel):
    id: UUID
    employee_id: UUID
    organization_node_id: UUID
    starts_on: date
    ends_on: date | None
    is_primary: bool


class ShiftCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    starts_at: time
    ends_at: time
    break_minutes: int = Field(default=0, ge=0, le=720)
    grace_minutes: int = Field(default=0, ge=0, le=240)


class ShiftView(BaseModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    starts_at: time
    ends_at: time
    break_minutes: int
    grace_minutes: int
    active: bool


class ShiftAssignmentCreate(BaseModel):
    shift_id: UUID
    employee_id: UUID | None = None
    organization_node_id: UUID | None = None
    starts_on: date
    ends_on: date | None = None


class ShiftAssignmentView(BaseModel):
    id: UUID
    shift_id: UUID
    employee_id: UUID | None
    organization_node_id: UUID | None
    starts_on: date
    ends_on: date | None


class EmployeeContextView(BaseModel):
    employee_id: UUID
    on_date: date
    organization_assignment: OrganizationAssignmentView | None
    shift_assignment: ShiftAssignmentView | None
    shift: ShiftView | None


def company_view(company) -> CompanyView:
    return CompanyView(
        id=company.id,
        legal_name=company.legal_name,
        display_name=company.display_name,
        timezone=company.timezone,
        status=company.status,
    )


def node_view(node) -> NodeView:
    return NodeView(
        id=node.id,
        organization_id=node.organization_id,
        parent_id=node.parent_id,
        node_type=node.node_type,
        code=node.code,
        name=node.name,
        status=node.status,
    )


def employee_view(employee) -> EmployeeView:
    return EmployeeView(
        id=employee.id,
        organization_id=employee.organization_id,
        employee_code=employee.employee_code,
        display_name=employee.display_name,
        joined_on=employee.joined_on,
        left_on=employee.left_on,
        status=employee.status,
    )


def organization_assignment_view(item) -> OrganizationAssignmentView:
    return OrganizationAssignmentView(
        id=item.id,
        employee_id=item.employee_id,
        organization_node_id=item.organization_node_id,
        starts_on=item.starts_on,
        ends_on=item.ends_on,
        is_primary=item.is_primary,
    )


def shift_view(item) -> ShiftView:
    return ShiftView(
        id=item.id,
        organization_id=item.organization_id,
        code=item.code,
        name=item.name,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        break_minutes=item.break_minutes,
        grace_minutes=item.grace_minutes,
        active=item.active,
    )


def shift_assignment_view(item) -> ShiftAssignmentView:
    return ShiftAssignmentView(
        id=item.id,
        shift_id=item.shift_id,
        employee_id=item.employee_id,
        organization_node_id=item.organization_node_id,
        starts_on=item.starts_on,
        ends_on=item.ends_on,
    )


def service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="record already exists")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=CompanyView, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity, Depends(require_permission("organization.create"))
    ],
    session: Annotated[Session, Depends(get_db)],
) -> CompanyView:
    try:
        company = WorkforceService(session).create_company(
            legal_name=payload.legal_name,
            display_name=payload.display_name,
            timezone=payload.timezone,
            actor_user_id=identity.principal.user.id,
        )
        return company_view(company)
    except (ValueError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.get("/{organization_id}", response_model=CompanyView)
def get_company(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("organization.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> CompanyView:
    try:
        return company_view(WorkforceService(session).company(organization_id))
    except LookupError as exc:
        raise service_error(exc) from exc


@router.get("/{organization_id}/nodes", response_model=list[NodeView])
def list_nodes(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("organization.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[NodeView]:
    try:
        return [node_view(item) for item in WorkforceService(session).list_nodes(organization_id)]
    except LookupError as exc:
        raise service_error(exc) from exc


@router.post(
    "/{organization_id}/nodes",
    response_model=NodeView,
    status_code=status.HTTP_201_CREATED,
)
def create_node(
    organization_id: UUID,
    payload: NodeCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("organization.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> NodeView:
    try:
        item = WorkforceService(session).create_node(
            organization_id=organization_id,
            node_type=payload.node_type,
            code=payload.code,
            name=payload.name,
            parent_id=payload.parent_id,
            actor_user_id=identity.principal.user.id,
        )
        return node_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.get("/{organization_id}/employees", response_model=list[EmployeeView])
def list_employees(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[EmployeeView]:
    try:
        items = WorkforceService(session).list_employees(
            organization_id,
            query_text=q,
            limit=limit,
            offset=offset,
        )
        return [employee_view(item) for item in items]
    except LookupError as exc:
        raise service_error(exc) from exc


@router.post(
    "/{organization_id}/employees",
    response_model=EmployeeView,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    organization_id: UUID,
    payload: EmployeeCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeView:
    try:
        item = WorkforceService(session).create_employee(
            organization_id=organization_id,
            employee_code=payload.employee_code,
            display_name=payload.display_name,
            joined_on=payload.joined_on,
            user_account_id=payload.user_account_id,
            actor_user_id=identity.principal.user.id,
        )
        return employee_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.patch(
    "/{organization_id}/employees/{employee_id}/status",
    response_model=EmployeeView,
)
def set_employee_status(
    organization_id: UUID,
    employee_id: UUID,
    payload: EmployeeStatusUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeView:
    try:
        item = WorkforceService(session).set_employee_status(
            organization_id=organization_id,
            employee_id=employee_id,
            status=payload.status,
            left_on=payload.left_on,
            actor_user_id=identity.principal.user.id,
        )
        return employee_view(item)
    except (LookupError, ValueError) as exc:
        raise service_error(exc) from exc


@router.post(
    "/{organization_id}/employees/{employee_id}/organization-assignments",
    response_model=OrganizationAssignmentView,
    status_code=status.HTTP_201_CREATED,
)
def assign_employee_organization(
    organization_id: UUID,
    employee_id: UUID,
    payload: OrganizationAssignmentCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> OrganizationAssignmentView:
    try:
        item = WorkforceService(session).assign_employee_node(
            organization_id=organization_id,
            employee_id=employee_id,
            organization_node_id=payload.organization_node_id,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            is_primary=payload.is_primary,
            actor_user_id=identity.principal.user.id,
        )
        return organization_assignment_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.get("/{organization_id}/shifts", response_model=list[ShiftView])
def list_shifts(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("shift.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[ShiftView]:
    try:
        return [shift_view(item) for item in WorkforceService(session).list_shifts(organization_id)]
    except LookupError as exc:
        raise service_error(exc) from exc


@router.post(
    "/{organization_id}/shifts",
    response_model=ShiftView,
    status_code=status.HTTP_201_CREATED,
)
def create_shift(
    organization_id: UUID,
    payload: ShiftCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("shift.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ShiftView:
    try:
        item = WorkforceService(session).create_shift(
            organization_id=organization_id,
            code=payload.code,
            name=payload.name,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            break_minutes=payload.break_minutes,
            grace_minutes=payload.grace_minutes,
            actor_user_id=identity.principal.user.id,
        )
        return shift_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.post(
    "/{organization_id}/shift-assignments",
    response_model=ShiftAssignmentView,
    status_code=status.HTTP_201_CREATED,
)
def assign_shift(
    organization_id: UUID,
    payload: ShiftAssignmentCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("shift.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ShiftAssignmentView:
    try:
        item = WorkforceService(session).assign_shift(
            organization_id=organization_id,
            shift_id=payload.shift_id,
            employee_id=payload.employee_id,
            organization_node_id=payload.organization_node_id,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            actor_user_id=identity.principal.user.id,
        )
        return shift_assignment_view(item)
    except (LookupError, ValueError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.get(
    "/{organization_id}/employees/{employee_id}/context",
    response_model=EmployeeContextView,
)
def employee_context(
    organization_id: UUID,
    employee_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    on_date: date = Query(),
) -> EmployeeContextView:
    try:
        org_assignment, shift_assignment, shift = WorkforceService(
            session
        ).resolve_employee_context(
            organization_id=organization_id,
            employee_id=employee_id,
            on_date=on_date,
        )
        return EmployeeContextView(
            employee_id=employee_id,
            on_date=on_date,
            organization_assignment=(
                organization_assignment_view(org_assignment) if org_assignment else None
            ),
            shift_assignment=(
                shift_assignment_view(shift_assignment) if shift_assignment else None
            ),
            shift=shift_view(shift) if shift else None,
        )
    except LookupError as exc:
        raise service_error(exc) from exc
