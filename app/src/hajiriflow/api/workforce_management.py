import csv
import io
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.workforce import CompanyProfile, Employee, OrganizationNode
from hajiriflow.db.models.workforce_profile import CompanyReportProfile, EmployeeProfile
from hajiriflow.identity.audit import redact_audit_payload

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/workforce-management",
    tags=["workforce-management"],
)

EmployeeStatus = Literal["active", "inactive", "terminated"]
EmploymentType = Literal[
    "permanent",
    "contract",
    "temporary",
    "intern",
    "consultant",
]
EmployeeSort = Literal["attendance_id", "employee_code", "name", "joined_on"]
SortOrder = Literal["asc", "desc"]
StatusFilter = Annotated[EmployeeStatus | None, Query(alias="status")]


class CompanyReportProfileUpdate(BaseModel):
    address: str | None = Field(default=None, max_length=300)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=80)
    report_header: str | None = Field(default=None, max_length=240)


class CompanyReportProfileView(CompanyReportProfileUpdate):
    organization_id: UUID


class OrganizationNodeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    status: Literal["active", "archived"] | None = None


class OrganizationNodeView(BaseModel):
    id: UUID
    organization_id: UUID
    parent_id: UUID | None
    node_type: str
    code: str
    name: str
    status: str


class EmployeeProfileUpdate(BaseModel):
    attendance_id: int | None = Field(default=None, ge=1, le=2_147_483_647)
    hr_employee_number: str | None = Field(default=None, max_length=80)
    employment_type: EmploymentType = "permanent"
    designation: str | None = Field(default=None, max_length=160)
    grade_level: str | None = Field(default=None, max_length=80)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=80)
    payroll_reference: str | None = Field(default=None, max_length=120)


class EmployeeDetailView(BaseModel):
    id: UUID
    organization_id: UUID
    employee_code: str
    display_name: str
    joined_on: date
    left_on: date | None
    status: str
    attendance_id: int | None
    hr_employee_number: str | None
    employment_type: str
    designation: str | None
    grade_level: str | None
    contact_email: str | None
    contact_phone: str | None
    payroll_reference: str | None


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _company(session: Session, organization_id: UUID) -> CompanyProfile:
    item = session.get(CompanyProfile, organization_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization not found",
        )
    return item


def _employee(
    session: Session,
    organization_id: UUID,
    employee_id: UUID,
) -> Employee:
    item = session.get(Employee, employee_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="employee not found",
        )
    return item


def _profile(
    session: Session,
    organization_id: UUID,
    employee_id: UUID,
) -> EmployeeProfile | None:
    item = session.get(EmployeeProfile, employee_id)
    if item and item.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="employee profile not found",
        )
    return item


def _detail(
    employee: Employee,
    profile: EmployeeProfile | None,
) -> EmployeeDetailView:
    return EmployeeDetailView(
        id=employee.id,
        organization_id=employee.organization_id,
        employee_code=employee.employee_code,
        display_name=employee.display_name,
        joined_on=employee.joined_on,
        left_on=employee.left_on,
        status=employee.status,
        attendance_id=profile.attendance_id if profile else None,
        hr_employee_number=profile.hr_employee_number if profile else None,
        employment_type=profile.employment_type if profile else "permanent",
        designation=profile.designation if profile else None,
        grade_level=profile.grade_level if profile else None,
        contact_email=profile.contact_email if profile else None,
        contact_phone=profile.contact_phone if profile else None,
        payroll_reference=profile.payroll_reference if profile else None,
    )


def _node_view(item: OrganizationNode) -> OrganizationNodeView:
    return OrganizationNodeView(
        id=item.id,
        organization_id=item.organization_id,
        parent_id=item.parent_id,
        node_type=item.node_type,
        code=item.code,
        name=item.name,
        status=item.status,
    )


def _audit(
    session: Session,
    *,
    identity: RequestIdentity,
    organization_id: UUID,
    action: str,
    object_type: str,
    object_id: UUID,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_user_id=identity.principal.user.id,
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            before_data=redact_audit_payload(before) if before else None,
            after_data=redact_audit_payload(after) if after else None,
            context_data={"organization_id": str(organization_id)},
        )
    )


def _employee_rows(
    session: Session,
    organization_id: UUID,
    *,
    q: str | None,
    status_filter: str | None,
    employment_type: str | None,
    sort_by: str,
    sort_order: str,
    limit: int,
    offset: int,
) -> list[tuple[Employee, EmployeeProfile | None]]:
    query = (
        select(Employee, EmployeeProfile)
        .outerjoin(EmployeeProfile, EmployeeProfile.employee_id == Employee.id)
        .where(Employee.organization_id == organization_id)
    )
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Employee.display_name.ilike(pattern),
                Employee.employee_code.ilike(pattern),
                EmployeeProfile.hr_employee_number.ilike(pattern),
            )
        )
    if status_filter:
        query = query.where(Employee.status == status_filter)
    if employment_type:
        query = query.where(EmployeeProfile.employment_type == employment_type)

    sort_map = {
        "attendance_id": EmployeeProfile.attendance_id,
        "employee_code": Employee.employee_code,
        "name": Employee.display_name,
        "joined_on": Employee.joined_on,
    }
    column = sort_map[sort_by]
    order = desc if sort_order == "desc" else asc
    if sort_by == "attendance_id":
        query = query.order_by(
            column.is_(None),
            order(column),
            Employee.employee_code,
        )
    else:
        query = query.order_by(order(column), Employee.employee_code)
    return list(session.execute(query.offset(offset).limit(limit)).all())


@router.get("/company-profile", response_model=CompanyReportProfileView)
def get_company_report_profile(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("organization.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> CompanyReportProfileView:
    _company(session, organization_id)
    item = session.get(CompanyReportProfile, organization_id)
    return CompanyReportProfileView(
        organization_id=organization_id,
        address=item.address if item else None,
        contact_email=item.contact_email if item else None,
        contact_phone=item.contact_phone if item else None,
        report_header=item.report_header if item else None,
    )


@router.put("/company-profile", response_model=CompanyReportProfileView)
def update_company_report_profile(
    organization_id: UUID,
    payload: CompanyReportProfileUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("organization.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> CompanyReportProfileView:
    _company(session, organization_id)
    item = session.get(CompanyReportProfile, organization_id)
    before = None
    if item:
        before = {
            "address": item.address,
            "contact_email": item.contact_email,
            "contact_phone": item.contact_phone,
            "report_header": item.report_header,
        }
    else:
        item = CompanyReportProfile(organization_id=organization_id)
        session.add(item)
    item.address = _strip_optional(payload.address)
    item.contact_email = _strip_optional(payload.contact_email)
    item.contact_phone = _strip_optional(payload.contact_phone)
    item.report_header = _strip_optional(payload.report_header)
    after = {
        "address": item.address,
        "contact_email": item.contact_email,
        "contact_phone": item.contact_phone,
        "report_header": item.report_header,
    }
    _audit(
        session,
        identity=identity,
        organization_id=organization_id,
        action="workforce.company_report_profile.updated",
        object_type="company_report_profile",
        object_id=organization_id,
        before=before,
        after=after,
    )
    session.commit()
    return CompanyReportProfileView(organization_id=organization_id, **after)


@router.patch("/nodes/{node_id}", response_model=OrganizationNodeView)
def update_organization_node(
    organization_id: UUID,
    node_id: UUID,
    payload: OrganizationNodeUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("organization.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> OrganizationNodeView:
    item = session.get(OrganizationNode, node_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization node not found",
        )
    if payload.parent_id is not None:
        if payload.parent_id == item.id:
            raise HTTPException(
                status_code=400,
                detail="organization node cannot be its own parent",
            )
        parent = session.get(OrganizationNode, payload.parent_id)
        if not parent or parent.organization_id != organization_id:
            raise HTTPException(
                status_code=400,
                detail="parent node must belong to the organization",
            )
        cursor = parent
        visited: set[UUID] = set()
        while cursor is not None and cursor.id not in visited:
            if cursor.id == item.id:
                raise HTTPException(
                    status_code=400,
                    detail="organization hierarchy cannot contain cycles",
                )
            visited.add(cursor.id)
            cursor = (
                session.get(OrganizationNode, cursor.parent_id)
                if cursor.parent_id
                else None
            )
    before = {
        "code": item.code,
        "name": item.name,
        "parent_id": str(item.parent_id) if item.parent_id else None,
        "status": item.status,
    }
    if payload.code is not None:
        item.code = payload.code.strip()
    if payload.name is not None:
        item.name = payload.name.strip()
    if "parent_id" in payload.model_fields_set:
        item.parent_id = payload.parent_id
    if payload.status is not None:
        item.status = payload.status
    after = {
        "code": item.code,
        "name": item.name,
        "parent_id": str(item.parent_id) if item.parent_id else None,
        "status": item.status,
    }
    _audit(
        session,
        identity=identity,
        organization_id=organization_id,
        action="workforce.organization_node.updated",
        object_type="organization_node",
        object_id=item.id,
        before=before,
        after=after,
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="organization node code already exists",
        ) from exc
    return _node_view(item)


@router.get("/employees", response_model=list[EmployeeDetailView])
def list_employee_details(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
    q: str | None = Query(default=None, max_length=120),
    status_filter: StatusFilter = None,
    employment_type: EmploymentType | None = None,
    sort_by: EmployeeSort = "employee_code",
    sort_order: SortOrder = "asc",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[EmployeeDetailView]:
    _company(session, organization_id)
    rows = _employee_rows(
        session,
        organization_id,
        q=q,
        status_filter=status_filter,
        employment_type=employment_type,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    return [_detail(employee, profile) for employee, profile in rows]


@router.get("/employees/{employee_id}", response_model=EmployeeDetailView)
def get_employee_detail(
    organization_id: UUID,
    employee_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailView:
    employee = _employee(session, organization_id, employee_id)
    return _detail(employee, _profile(session, organization_id, employee_id))


@router.put("/employees/{employee_id}/profile", response_model=EmployeeDetailView)
def update_employee_profile(
    organization_id: UUID,
    employee_id: UUID,
    payload: EmployeeProfileUpdate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> EmployeeDetailView:
    employee = _employee(session, organization_id, employee_id)
    item = _profile(session, organization_id, employee_id)
    before = None
    if item is None:
        item = EmployeeProfile(
            employee_id=employee.id,
            organization_id=organization_id,
        )
        session.add(item)
    else:
        before = {
            "attendance_id": item.attendance_id,
            "hr_employee_number": item.hr_employee_number,
            "employment_type": item.employment_type,
            "designation": item.designation,
            "grade_level": item.grade_level,
        }
    item.attendance_id = payload.attendance_id
    item.hr_employee_number = _strip_optional(payload.hr_employee_number)
    item.employment_type = payload.employment_type
    item.designation = _strip_optional(payload.designation)
    item.grade_level = _strip_optional(payload.grade_level)
    item.contact_email = _strip_optional(payload.contact_email)
    item.contact_phone = _strip_optional(payload.contact_phone)
    item.payroll_reference = _strip_optional(payload.payroll_reference)
    item.updated_at = datetime.now(UTC)
    after = {
        "attendance_id": item.attendance_id,
        "hr_employee_number": item.hr_employee_number,
        "employment_type": item.employment_type,
        "designation": item.designation,
        "grade_level": item.grade_level,
    }
    _audit(
        session,
        identity=identity,
        organization_id=organization_id,
        action="workforce.employee_profile.updated",
        object_type="employee_profile",
        object_id=employee.id,
        before=before,
        after=after,
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="attendance ID or HR employee number is already assigned",
        ) from exc
    return _detail(employee, item)


def _export_headers() -> list[str]:
    return [
        "attendance_id",
        "employee_code",
        "hr_employee_number",
        "display_name",
        "employment_type",
        "designation",
        "grade_level",
        "status",
        "joined_on",
        "left_on",
        "contact_email",
        "contact_phone",
        "payroll_reference",
    ]


def _export_values(item: EmployeeDetailView) -> list[object]:
    return [
        item.attendance_id,
        item.employee_code,
        item.hr_employee_number,
        item.display_name,
        item.employment_type,
        item.designation,
        item.grade_level,
        item.status,
        item.joined_on.isoformat(),
        item.left_on.isoformat() if item.left_on else None,
        item.contact_email,
        item.contact_phone,
        item.payroll_reference,
    ]


@router.get("/employees/export/file")
def export_employees(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("employee.export")),
    ],
    session: Annotated[Session, Depends(get_db)],
    export_format: Literal["csv", "xlsx"] = Query(
        default="csv",
        alias="format",
    ),
    q: str | None = Query(default=None, max_length=120),
    status_filter: StatusFilter = None,
    employment_type: EmploymentType | None = None,
) -> StreamingResponse:
    _company(session, organization_id)
    rows = _employee_rows(
        session,
        organization_id,
        q=q,
        status_filter=status_filter,
        employment_type=employment_type,
        sort_by="attendance_id",
        sort_order="asc",
        limit=10_000,
        offset=0,
    )
    details = [_detail(employee, profile) for employee, profile in rows]
    headers = _export_headers()
    if export_format == "csv":
        text = io.StringIO(newline="")
        writer = csv.writer(text)
        writer.writerow(headers)
        writer.writerows(_export_values(item) for item in details)
        data = io.BytesIO(text.getvalue().encode("utf-8-sig"))
        media_type = "text/csv; charset=utf-8"
        filename = "employees.csv"
    else:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Employees")
        sheet.append(headers)
        for item in details:
            sheet.append(_export_values(item))
        data = io.BytesIO()
        workbook.save(data)
        data.seek(0)
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = "employees.xlsx"
    return StreamingResponse(
        data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
