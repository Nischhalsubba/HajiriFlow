from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings
from hajiriflow.db.models.identity import AuthSession, UserAccount
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.identity.exceptions import DuplicateUsername
from hajiriflow.identity.service import IdentityService


class IdentityAdminService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.identity = IdentityService(session, settings)

    def search_users(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        linked: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserAccount]:
        if status not in {None, "active", "disabled"}:
            raise ValueError("unsupported user status filter")
        bounded_limit = max(1, min(limit, 200))
        bounded_offset = max(0, min(offset, 10000))
        statement = select(UserAccount)
        if query and query.strip():
            needle = f"%{query.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(UserAccount.username).like(needle),
                    func.lower(UserAccount.display_name).like(needle),
                )
            )
        if status is not None:
            statement = statement.where(UserAccount.status == status)
        if linked is True:
            statement = statement.where(UserAccount.employee_id.is_not(None))
        elif linked is False:
            statement = statement.where(UserAccount.employee_id.is_(None))
        return list(
            self.session.scalars(
                statement.order_by(UserAccount.display_name, UserAccount.username)
                .offset(bounded_offset)
                .limit(bounded_limit)
            ).all()
        )

    def search_employee_links(
        self,
        *,
        query: str | None = None,
        organization_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[Employee, CompanyProfile]]:
        bounded_limit = max(1, min(limit, 100))
        bounded_offset = max(0, min(offset, 10000))
        statement = (
            select(Employee, CompanyProfile)
            .join(CompanyProfile, CompanyProfile.id == Employee.organization_id)
            .where(Employee.status != "archived")
        )
        if organization_id is not None:
            statement = statement.where(Employee.organization_id == organization_id)
        if query and query.strip():
            needle = f"%{query.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Employee.employee_code).like(needle),
                    func.lower(Employee.display_name).like(needle),
                )
            )
        return list(
            self.session.execute(
                statement.order_by(
                    CompanyProfile.display_name,
                    Employee.employee_code,
                    Employee.display_name,
                )
                .offset(bounded_offset)
                .limit(bounded_limit)
            ).all()
        )

    def update_user(
        self,
        *,
        user_id: UUID,
        actor_user_id: UUID,
        username: str | None = None,
        display_name: str | None = None,
        employee_id: UUID | None = None,
        employee_id_supplied: bool = False,
    ) -> UserAccount:
        user = self.session.get(UserAccount, user_id)
        if user is None:
            raise LookupError("user not found")
        before = {
            "username": user.username,
            "display_name": user.display_name,
            "employee_id": str(user.employee_id) if user.employee_id else None,
        }
        security_change = False
        if username is not None:
            normalized = self.identity.normalize_username(username)
            duplicate = self.session.scalar(
                select(UserAccount.id).where(
                    UserAccount.username == normalized,
                    UserAccount.id != user.id,
                )
            )
            if duplicate:
                raise DuplicateUsername(normalized)
            if normalized != user.username:
                if user.id == actor_user_id:
                    raise ValueError("users cannot change their own login identifier here")
                user.username = normalized
                security_change = True
        if display_name is not None:
            normalized_name = display_name.strip()
            if not normalized_name:
                raise ValueError("display name cannot be blank")
            if len(normalized_name) > 200:
                raise ValueError("display name cannot exceed 200 characters")
            user.display_name = normalized_name
        if employee_id_supplied:
            if user.id == actor_user_id:
                raise ValueError("users cannot change their own employee link")
            if employee_id is not None:
                employee = self.session.get(Employee, employee_id)
                if employee is None or employee.status == "archived":
                    raise LookupError("employee not found")
                existing_link = self.session.scalar(
                    select(UserAccount.id).where(
                        UserAccount.employee_id == employee_id,
                        UserAccount.id != user.id,
                    )
                )
                if existing_link:
                    raise ValueError("employee is already linked to another user")
            if employee_id != user.employee_id:
                user.employee_id = employee_id
                security_change = True
        if security_change:
            user.session_version += 1
            now = datetime.now(UTC)
            self.session.query(AuthSession).filter(
                AuthSession.user_id == user.id,
                AuthSession.revoked_at.is_(None),
            ).update({AuthSession.revoked_at: now})
        after = {
            "username": user.username,
            "display_name": user.display_name,
            "employee_id": str(user.employee_id) if user.employee_id else None,
        }
        if before != after:
            self.identity.add_audit(
                actor_user_id=actor_user_id,
                action="identity.user.updated",
                object_type="user_account",
                object_id=str(user.id),
                before_data=before,
                after_data=after,
            )
        self.session.flush()
        return user
