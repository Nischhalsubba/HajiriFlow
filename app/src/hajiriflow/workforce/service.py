from datetime import date, time
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from hajiriflow.db.models.identity import AuditEvent, UserAccount
from hajiriflow.db.models.workforce import (
    CompanyProfile,
    Employee,
    EmployeeOrganizationAssignment,
    OrganizationNode,
    Shift,
    ShiftAssignment,
)
from hajiriflow.identity.audit import redact_audit_payload


class WorkforceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _audit(
        self,
        *,
        actor_user_id: UUID,
        action: str,
        object_type: str,
        object_id: UUID,
        after: dict,
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                object_type=object_type,
                object_id=str(object_id),
                after_data=redact_audit_payload(after),
            )
        )

    def create_company(
        self,
        *,
        legal_name: str,
        display_name: str,
        timezone: str,
        actor_user_id: UUID,
    ) -> CompanyProfile:
        company = CompanyProfile(
            legal_name=legal_name.strip(),
            display_name=display_name.strip(),
            timezone=timezone.strip(),
        )
        if not company.legal_name or not company.display_name or not company.timezone:
            raise ValueError("company fields cannot be blank")
        self.session.add(company)
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="workforce.company.created",
            object_type="company_profile",
            object_id=company.id,
            after={"display_name": company.display_name, "timezone": company.timezone},
        )
        return company

    def company(self, organization_id: UUID) -> CompanyProfile:
        company = self.session.get(CompanyProfile, organization_id)
        if not company:
            raise LookupError("organization not found")
        return company

    def create_node(
        self,
        *,
        organization_id: UUID,
        node_type: str,
        code: str,
        name: str,
        parent_id: UUID | None,
        actor_user_id: UUID,
    ) -> OrganizationNode:
        self.company(organization_id)
        if parent_id:
            parent = self.session.get(OrganizationNode, parent_id)
            if not parent or parent.organization_id != organization_id:
                raise ValueError("parent node must belong to the same organization")
        node = OrganizationNode(
            organization_id=organization_id,
            node_type=node_type,
            code=code.strip(),
            name=name.strip(),
            parent_id=parent_id,
        )
        if not node.code or not node.name:
            raise ValueError("node code and name cannot be blank")
        self.session.add(node)
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="workforce.organization_node.created",
            object_type="organization_node",
            object_id=node.id,
            after={"code": node.code, "node_type": node.node_type},
        )
        return node

    def list_nodes(self, organization_id: UUID) -> list[OrganizationNode]:
        self.company(organization_id)
        query = (
            select(OrganizationNode)
            .where(OrganizationNode.organization_id == organization_id)
            .order_by(OrganizationNode.node_type, OrganizationNode.name)
        )
        return list(self.session.scalars(query).all())

    def create_employee(
        self,
        *,
        organization_id: UUID,
        employee_code: str,
        display_name: str,
        joined_on: date,
        user_account_id: UUID | None,
        actor_user_id: UUID,
    ) -> Employee:
        self.company(organization_id)
        employee = Employee(
            organization_id=organization_id,
            employee_code=employee_code.strip(),
            display_name=display_name.strip(),
            joined_on=joined_on,
        )
        if not employee.employee_code or not employee.display_name:
            raise ValueError("employee code and display name cannot be blank")
        self.session.add(employee)
        self.session.flush()
        if user_account_id:
            user = self.session.get(UserAccount, user_account_id)
            if not user:
                raise LookupError("user account not found")
            if user.employee_id and user.employee_id != employee.id:
                raise ValueError("user account is already linked to an employee")
            user.employee_id = employee.id
        self._audit(
            actor_user_id=actor_user_id,
            action="workforce.employee.created",
            object_type="employee",
            object_id=employee.id,
            after={"employee_code": employee.employee_code, "status": employee.status},
        )
        return employee

    def list_employees(
        self,
        organization_id: UUID,
        *,
        query_text: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Employee]:
        self.company(organization_id)
        query = select(Employee).where(Employee.organization_id == organization_id)
        if query_text:
            pattern = f"%{query_text.strip()}%"
            query = query.where(
                or_(
                    Employee.display_name.ilike(pattern),
                    Employee.employee_code.ilike(pattern),
                )
            )
        query = query.order_by(Employee.display_name).offset(offset).limit(limit)
        return list(self.session.scalars(query).all())

    def set_employee_status(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        status: str,
        left_on: date | None,
        actor_user_id: UUID,
    ) -> Employee:
        employee = self.session.get(Employee, employee_id)
        if not employee or employee.organization_id != organization_id:
            raise LookupError("employee not found")
        if left_on and left_on < employee.joined_on:
            raise ValueError("left_on cannot be before joined_on")
        employee.status = status
        employee.left_on = left_on
        self._audit(
            actor_user_id=actor_user_id,
            action="workforce.employee.status_changed",
            object_type="employee",
            object_id=employee.id,
            after={"status": status, "left_on": left_on.isoformat() if left_on else None},
        )
        return employee

    @staticmethod
    def _overlaps(starts_on, ends_on, new_start: date, new_end: date | None):
        end_value = new_end or date.max
        return and_(
            starts_on <= end_value,
            or_(ends_on.is_(None), ends_on >= new_start),
        )

    def assign_employee_node(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        organization_node_id: UUID,
        starts_on: date,
        ends_on: date | None,
        is_primary: bool,
        actor_user_id: UUID,
    ) -> EmployeeOrganizationAssignment:
        employee = self.session.get(Employee, employee_id)
        node = self.session.get(OrganizationNode, organization_node_id)
        if not employee or employee.organization_id != organization_id:
            raise LookupError("employee not found")
        if not node or node.organization_id != organization_id:
            raise LookupError("organization node not found")
        if ends_on and ends_on < starts_on:
            raise ValueError("ends_on cannot be before starts_on")
        if is_primary:
            overlap = self.session.scalar(
                select(EmployeeOrganizationAssignment.id).where(
                    EmployeeOrganizationAssignment.employee_id == employee_id,
                    EmployeeOrganizationAssignment.is_primary.is_(True),
                    self._overlaps(
                        EmployeeOrganizationAssignment.starts_on,
                        EmployeeOrganizationAssignment.ends_on,
                        starts_on,
                        ends_on,
                    ),
                )
            )
            if overlap:
                raise ValueError(
                    "primary organization assignment overlaps an existing period"
                )
        assignment = EmployeeOrganizationAssignment(
            organization_id=organization_id,
            employee_id=employee_id,
            organization_node_id=organization_node_id,
            starts_on=starts_on,
            ends_on=ends_on,
            is_primary=is_primary,
        )
        self.session.add(assignment)
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="workforce.employee.organization_assigned",
            object_type="employee_organization_assignment",
            object_id=assignment.id,
            after={
                "employee_id": str(employee_id),
                "organization_node_id": str(organization_node_id),
                "starts_on": starts_on.isoformat(),
                "ends_on": ends_on.isoformat() if ends_on else None,
                "is_primary": is_primary,
            },
        )
        return assignment

    def create_shift(
        self,
        *,
        organization_id: UUID,
        code: str,
        name: str,
        starts_at: time,
        ends_at: time,
        break_minutes: int,
        grace_minutes: int,
        actor_user_id: UUID,
    ) -> Shift:
        self.company(organization_id)
        shift = Shift(
            organization_id=organization_id,
            code=code.strip(),
            name=name.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            break_minutes=break_minutes,
            grace_minutes=grace_minutes,
        )
        if not shift.code or not shift.name:
            raise ValueError("shift code and name cannot be blank")
        self.session.add(shift)
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="workforce.shift.created",
            object_type="shift",
            object_id=shift.id,
            after={"code": shift.code, "starts_at": starts_at.isoformat()},
        )
        return shift

    def list_shifts(self, organization_id: UUID) -> list[Shift]:
        self.company(organization_id)
        query = (
            select(Shift)
            .where(Shift.organization_id == organization_id)
            .order_by(Shift.name)
        )
        return list(self.session.scalars(query).all())

    def assign_shift(
        self,
        *,
        organization_id: UUID,
        shift_id: UUID,
        employee_id: UUID | None,
        organization_node_id: UUID | None,
        starts_on: date,
        ends_on: date | None,
        actor_user_id: UUID,
    ) -> ShiftAssignment:
        if (employee_id is None) == (organization_node_id is None):
            raise ValueError("exactly one shift assignment target is required")
        shift = self.session.get(Shift, shift_id)
        if not shift or shift.organization_id != organization_id:
            raise LookupError("shift not found")
        if ends_on and ends_on < starts_on:
            raise ValueError("ends_on cannot be before starts_on")
        target_column = ShiftAssignment.employee_id
        target_id = employee_id
        if employee_id:
            employee = self.session.get(Employee, employee_id)
            if not employee or employee.organization_id != organization_id:
                raise LookupError("employee not found")
        else:
            node = self.session.get(OrganizationNode, organization_node_id)
            if not node or node.organization_id != organization_id:
                raise LookupError("organization node not found")
            target_column = ShiftAssignment.organization_node_id
            target_id = organization_node_id
        overlap = self.session.scalar(
            select(ShiftAssignment.id).where(
                target_column == target_id,
                self._overlaps(
                    ShiftAssignment.starts_on,
                    ShiftAssignment.ends_on,
                    starts_on,
                    ends_on,
                ),
            )
        )
        if overlap:
            raise ValueError("shift assignment overlaps an existing period")
        assignment = ShiftAssignment(
            organization_id=organization_id,
            shift_id=shift_id,
            employee_id=employee_id,
            organization_node_id=organization_node_id,
            starts_on=starts_on,
            ends_on=ends_on,
        )
        self.session.add(assignment)
        self.session.flush()
        self._audit(
            actor_user_id=actor_user_id,
            action="workforce.shift.assigned",
            object_type="shift_assignment",
            object_id=assignment.id,
            after={
                "shift_id": str(shift_id),
                "employee_id": str(employee_id) if employee_id else None,
                "organization_node_id": (
                    str(organization_node_id) if organization_node_id else None
                ),
                "starts_on": starts_on.isoformat(),
                "ends_on": ends_on.isoformat() if ends_on else None,
            },
        )
        return assignment

    def resolve_employee_context(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID,
        on_date: date,
    ) -> tuple[
        EmployeeOrganizationAssignment | None,
        ShiftAssignment | None,
        Shift | None,
    ]:
        employee = self.session.get(Employee, employee_id)
        if not employee or employee.organization_id != organization_id:
            raise LookupError("employee not found")

        def active_range(model):
            return and_(
                model.starts_on <= on_date,
                or_(model.ends_on.is_(None), model.ends_on >= on_date),
            )

        org_assignment = self.session.scalar(
            select(EmployeeOrganizationAssignment)
            .where(
                EmployeeOrganizationAssignment.employee_id == employee_id,
                EmployeeOrganizationAssignment.is_primary.is_(True),
                active_range(EmployeeOrganizationAssignment),
            )
            .order_by(EmployeeOrganizationAssignment.starts_on.desc())
            .limit(1)
        )
        shift_assignment = self.session.scalar(
            select(ShiftAssignment)
            .where(
                ShiftAssignment.employee_id == employee_id,
                active_range(ShiftAssignment),
            )
            .order_by(ShiftAssignment.starts_on.desc())
            .limit(1)
        )
        if not shift_assignment and org_assignment:
            shift_assignment = self.session.scalar(
                select(ShiftAssignment)
                .where(
                    ShiftAssignment.organization_node_id
                    == org_assignment.organization_node_id,
                    active_range(ShiftAssignment),
                )
                .order_by(ShiftAssignment.starts_on.desc())
                .limit(1)
            )
        shift = (
            self.session.get(Shift, shift_assignment.shift_id)
            if shift_assignment
            else None
        )
        return org_assignment, shift_assignment, shift
