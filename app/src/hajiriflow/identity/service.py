from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings
from hajiriflow.db.models.identity import (
    AuditEvent,
    AuthenticationAttempt,
    AuthSession,
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
)
from hajiriflow.identity.audit import redact_audit_payload
from hajiriflow.identity.exceptions import (
    AuthenticationRateLimited,
    DuplicateUsername,
    InvalidAccountStatus,
    InvalidCredentials,
    InvalidSession,
)
from hajiriflow.identity.permissions import PermissionGrant, ScopeType
from hajiriflow.identity.security import (
    hash_password,
    password_hash_needs_upgrade,
    verify_password,
)
from hajiriflow.identity.tokens import generate_session_token, hash_token


@dataclass(frozen=True, slots=True)
class CreatedSession:
    token: str
    session: AuthSession
    user: UserAccount


@dataclass(frozen=True, slots=True)
class SessionPrincipal:
    session: AuthSession
    user: UserAccount
    grants: frozenset[PermissionGrant]


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class IdentityService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    @staticmethod
    def normalize_username(username: str) -> str:
        value = username.strip().lower()
        if not 3 <= len(value) <= 100:
            raise ValueError("username must contain between 3 and 100 characters")
        return value

    def _protected_hash(self, value: str | None) -> str | None:
        if not value:
            return None
        return hash_token(value.strip().lower(), self.settings.session_secret)

    def _record_attempt(
        self,
        subject_hash: str,
        client_ip_hash: str | None,
        result: str,
        reason: str,
        now: datetime,
    ) -> None:
        self.session.add(
            AuthenticationAttempt(
                subject_hash=subject_hash,
                client_ip_hash=client_ip_hash,
                result=result,
                reason=reason,
                attempted_at=now,
            )
        )

    def _enforce_login_limit(
        self,
        subject_hash: str,
        client_ip_hash: str | None,
        now: datetime,
    ) -> None:
        window_start = now - timedelta(seconds=self.settings.login_window_seconds)
        conditions = [AuthenticationAttempt.subject_hash == subject_hash]
        if client_ip_hash:
            conditions.append(AuthenticationAttempt.client_ip_hash == client_ip_hash)
        failures = self.session.scalar(
            select(func.count(AuthenticationAttempt.id)).where(
                AuthenticationAttempt.result == "failure",
                AuthenticationAttempt.attempted_at >= window_start,
                or_(*conditions),
            )
        )
        if int(failures or 0) >= self.settings.login_max_attempts:
            raise AuthenticationRateLimited(self.settings.login_window_seconds)

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        password: str,
        must_change_password: bool = True,
        actor_user_id: UUID | None = None,
    ) -> UserAccount:
        normalized = self.normalize_username(username)
        if self.session.scalar(
            select(UserAccount.id).where(UserAccount.username == normalized)
        ):
            raise DuplicateUsername(normalized)
        user = UserAccount(
            username=normalized,
            display_name=display_name.strip(),
            password_hash=hash_password(password),
            must_change_password=must_change_password,
            status="active",
            session_version=1,
        )
        self.session.add(user)
        self.session.flush()
        self.add_audit(
            actor_user_id=actor_user_id,
            action="identity.user.created",
            object_type="user_account",
            object_id=str(user.id),
            after_data={
                "username": user.username,
                "display_name": user.display_name,
                "status": user.status,
            },
        )
        return user

    def authenticate(
        self,
        *,
        username: str,
        password: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> CreatedSession:
        now = datetime.now(UTC)
        normalized = self.normalize_username(username)
        subject_hash = hash_token(normalized, self.settings.session_secret)
        client_ip_hash = self._protected_hash(client_ip)
        self._enforce_login_limit(subject_hash, client_ip_hash, now)

        user = self.session.scalar(
            select(UserAccount).where(UserAccount.username == normalized)
        )
        if user is None or user.status != "active":
            reason = "unknown_user" if user is None else "disabled"
            self._record_attempt(subject_hash, client_ip_hash, "failure", reason, now)
            raise InvalidCredentials
        if not verify_password(password, user.password_hash):
            self._record_attempt(
                subject_hash,
                client_ip_hash,
                "failure",
                "invalid_password",
                now,
            )
            raise InvalidCredentials

        if password_hash_needs_upgrade(user.password_hash):
            user.password_hash = hash_password(password)

        raw_token = generate_session_token()
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=hash_token(raw_token, self.settings.session_secret),
            user_session_version=user.session_version,
            created_at=now,
            expires_at=now + timedelta(minutes=self.settings.session_ttl_minutes),
            last_seen_at=now,
            client_ip_hash=client_ip_hash,
            user_agent=(user_agent or "")[:500] or None,
        )
        self.session.add(auth_session)
        self._record_attempt(subject_hash, client_ip_hash, "success", "authenticated", now)
        self.session.flush()
        self.add_audit(
            actor_user_id=user.id,
            action="identity.session.created",
            object_type="auth_session",
            object_id=str(auth_session.id),
        )
        return CreatedSession(token=raw_token, session=auth_session, user=user)

    def resolve_session(self, raw_token: str) -> SessionPrincipal:
        now = datetime.now(UTC)
        token_digest = hash_token(raw_token, self.settings.session_secret)
        row = self.session.execute(
            select(AuthSession, UserAccount)
            .join(UserAccount, UserAccount.id == AuthSession.user_id)
            .where(AuthSession.token_hash == token_digest)
        ).one_or_none()
        if row is None:
            raise InvalidSession
        auth_session, user = row
        if (
            auth_session.revoked_at is not None
            or as_utc(auth_session.expires_at) <= now
            or user.status != "active"
            or auth_session.user_session_version != user.session_version
        ):
            raise InvalidSession
        auth_session.last_seen_at = now
        return SessionPrincipal(
            session=auth_session,
            user=user,
            grants=self.grants_for_user(user.id, now=now),
        )

    def revoke_session(self, session_id: UUID, actor_user_id: UUID | None) -> None:
        auth_session = self.session.get(AuthSession, session_id)
        if auth_session is None or auth_session.revoked_at is not None:
            return
        auth_session.revoked_at = datetime.now(UTC)
        self.add_audit(
            actor_user_id=actor_user_id,
            action="identity.session.revoked",
            object_type="auth_session",
            object_id=str(session_id),
        )

    def change_password(
        self,
        *,
        user: UserAccount,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentials
        if verify_password(new_password, user.password_hash):
            raise ValueError("new password must be different")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.session_version += 1
        now = datetime.now(UTC)
        self.session.query(AuthSession).filter(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        ).update({AuthSession.revoked_at: now})
        self.add_audit(
            actor_user_id=user.id,
            action="identity.password.changed",
            object_type="user_account",
            object_id=str(user.id),
        )

    def set_user_status(
        self,
        *,
        user_id: UUID,
        status: str,
        actor_user_id: UUID,
    ) -> UserAccount:
        if status not in {"active", "disabled"}:
            raise InvalidAccountStatus(status)
        user = self.session.get(UserAccount, user_id)
        if user is None:
            raise LookupError("user not found")
        before = user.status
        if before == status:
            return user
        user.status = status
        user.disabled_at = datetime.now(UTC) if status == "disabled" else None
        user.session_version += 1
        self.add_audit(
            actor_user_id=actor_user_id,
            action="identity.user.status_changed",
            object_type="user_account",
            object_id=str(user.id),
            before_data={"status": before},
            after_data={"status": status},
        )
        return user

    def assign_role(
        self,
        *,
        user_id: UUID,
        role_code: str,
        actor_user_id: UUID | None,
        scope_type: ScopeType = ScopeType.GLOBAL,
        scope_id: UUID | None = None,
    ) -> UserRole:
        role = self.session.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise LookupError("role not found")
        if self.session.get(UserAccount, user_id) is None:
            raise LookupError("user not found")
        if scope_type is ScopeType.GLOBAL and scope_id is not None:
            raise ValueError("global role assignments cannot contain a scope_id")
        if scope_type is ScopeType.ORGANIZATION and scope_id is None:
            raise ValueError("organization role assignments require a scope_id")
        existing = self.session.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
                UserRole.scope_type == scope_type.value,
                UserRole.scope_id == scope_id,
                UserRole.ends_at.is_(None),
            )
        )
        if existing is not None:
            return existing
        assignment = UserRole(
            user_id=user_id,
            role_id=role.id,
            scope_type=scope_type.value,
            scope_id=scope_id,
            assigned_by=actor_user_id,
        )
        self.session.add(assignment)
        self.session.flush()
        self.add_audit(
            actor_user_id=actor_user_id,
            action="identity.role.assigned",
            object_type="user_role",
            object_id=str(assignment.id),
            after_data={"role": role_code, "scope_type": scope_type.value},
        )
        return assignment

    def grants_for_user(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> frozenset[PermissionGrant]:
        effective_at = now or datetime.now(UTC)
        rows = self.session.execute(
            select(Permission.code, UserRole.scope_type, UserRole.scope_id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                UserRole.starts_at <= effective_at,
                or_(UserRole.ends_at.is_(None), UserRole.ends_at > effective_at),
            )
        ).all()
        return frozenset(
            PermissionGrant(
                permission=permission,
                scope_type=ScopeType(scope_type),
                scope_id=scope_id,
            )
            for permission, scope_type, scope_id in rows
        )

    def list_users(self) -> list[UserAccount]:
        return list(
            self.session.scalars(
                select(UserAccount).order_by(UserAccount.display_name, UserAccount.username)
            )
        )

    def add_audit(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        object_type: str,
        object_id: str | None,
        before_data: dict | None = None,
        after_data: dict | None = None,
        context_data: dict | None = None,
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                before_data=redact_audit_payload(before_data),
                after_data=redact_audit_payload(after_data),
                context_data=redact_audit_payload(context_data),
            )
        )
