from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings
from hajiriflow.db.models.identity import Role, UserAccount, UserRole
from hajiriflow.identity.service import IdentityService


@dataclass(frozen=True, slots=True)
class ActiveRoleAssignment:
    id: UUID
    user_id: UUID
    role_code: str
    role_name: str
    scope_type: str
    scope_id: UUID | None
    starts_at: datetime
    assigned_by: UUID | None


class RoleLifecycleService:
    """Read and end effective-dated role assignments without deleting history."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def list_roles(self) -> list[Role]:
        return list(self.session.scalars(select(Role).order_by(Role.name, Role.code)))

    def list_active_assignments(
        self,
        *,
        now: datetime | None = None,
    ) -> list[ActiveRoleAssignment]:
        effective_at = now or datetime.now(UTC)
        rows = self.session.execute(
            select(UserRole, Role)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.starts_at <= effective_at,
                or_(UserRole.ends_at.is_(None), UserRole.ends_at > effective_at),
            )
            .order_by(UserRole.user_id, Role.name, UserRole.starts_at)
        ).all()
        return [
            ActiveRoleAssignment(
                id=assignment.id,
                user_id=assignment.user_id,
                role_code=role.code,
                role_name=role.name,
                scope_type=assignment.scope_type,
                scope_id=assignment.scope_id,
                starts_at=assignment.starts_at,
                assigned_by=assignment.assigned_by,
            )
            for assignment, role in rows
        ]

    def get_active_assignment(
        self,
        assignment_id: UUID,
        *,
        now: datetime | None = None,
    ) -> ActiveRoleAssignment:
        effective_at = now or datetime.now(UTC)
        row = self.session.execute(
            select(UserRole, Role)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.id == assignment_id,
                UserRole.starts_at <= effective_at,
                or_(UserRole.ends_at.is_(None), UserRole.ends_at > effective_at),
            )
        ).one_or_none()
        if row is None:
            raise LookupError("active role assignment not found")
        assignment, role = row
        return ActiveRoleAssignment(
            id=assignment.id,
            user_id=assignment.user_id,
            role_code=role.code,
            role_name=role.name,
            scope_type=assignment.scope_type,
            scope_id=assignment.scope_id,
            starts_at=assignment.starts_at,
            assigned_by=assignment.assigned_by,
        )

    def revoke_assignment(
        self,
        assignment_id: UUID,
        *,
        actor_user_id: UUID,
        now: datetime | None = None,
    ) -> ActiveRoleAssignment:
        effective_at = now or datetime.now(UTC)
        record = self.get_active_assignment(assignment_id, now=effective_at)
        assignment = self.session.get(UserRole, assignment_id)
        if assignment is None:
            raise LookupError("active role assignment not found")
        if self.session.get(UserAccount, record.user_id) is None:
            raise LookupError("user not found")

        assignment.ends_at = effective_at
        IdentityService(self.session, self.settings).add_audit(
            actor_user_id=actor_user_id,
            action="identity.role.revoked",
            object_type="user_role",
            object_id=str(assignment.id),
            before_data={
                "role": record.role_code,
                "scope_type": record.scope_type,
                "scope_id": str(record.scope_id) if record.scope_id else None,
                "active": True,
            },
            after_data={
                "role": record.role_code,
                "scope_type": record.scope_type,
                "scope_id": str(record.scope_id) if record.scope_id else None,
                "active": False,
                "ended_at": effective_at.isoformat(),
            },
        )
        return record
