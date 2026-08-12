import pytest
from sqlalchemy.orm import Session

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.identity import AuthenticationAttempt
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.exceptions import (
    AuthenticationRateLimited,
    InvalidCredentials,
    InvalidSession,
)
from hajiriflow.identity.permissions import FULL_ACCESS, ScopeType, has_permission
from hajiriflow.identity.service import IdentityService

pytestmark = pytest.mark.usefixtures("database")


def make_service() -> tuple[Session, IdentityService]:
    session = get_session_factory()()
    seed_identity_catalog(session)
    return session, IdentityService(session, get_settings())


def test_login_creates_resolvable_revocable_session() -> None:
    session, service = make_service()
    user = service.create_user(
        username="Admin",
        display_name="Admin User",
        password="correct-password-123",
    )
    service.assign_role(
        user_id=user.id,
        role_code="system_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.GLOBAL,
    )
    created = service.authenticate(
        username="admin",
        password="correct-password-123",
        client_ip="127.0.0.1",
        user_agent="pytest",
    )
    session.commit()

    principal = service.resolve_session(created.token)
    assert principal.user.id == user.id
    assert has_permission(principal.grants, FULL_ACCESS)

    service.revoke_session(principal.session.id, user.id)
    session.commit()
    with pytest.raises(InvalidSession):
        service.resolve_session(created.token)
    session.close()


def test_failed_logins_are_recorded_and_throttled() -> None:
    session, service = make_service()
    service.create_user(
        username="operator",
        display_name="Operator",
        password="correct-password-123",
    )
    session.commit()

    for _ in range(3):
        with pytest.raises(InvalidCredentials):
            service.authenticate(
                username="operator",
                password="wrong-password",
                client_ip="127.0.0.1",
                user_agent="pytest",
            )
        session.commit()

    assert session.query(AuthenticationAttempt).count() == 3
    with pytest.raises(AuthenticationRateLimited) as exc_info:
        service.authenticate(
            username="operator",
            password="correct-password-123",
            client_ip="127.0.0.1",
            user_agent="pytest",
        )
    assert exc_info.value.retry_after_seconds == 300
    session.close()


def test_disabling_user_invalidates_existing_sessions() -> None:
    session, service = make_service()
    user = service.create_user(
        username="manager",
        display_name="Manager",
        password="correct-password-123",
    )
    created = service.authenticate(
        username="manager",
        password="correct-password-123",
        client_ip=None,
        user_agent=None,
    )
    session.commit()

    service.set_user_status(
        user_id=user.id,
        status="disabled",
        actor_user_id=user.id,
    )
    session.commit()

    with pytest.raises(InvalidSession):
        service.resolve_session(created.token)
    session.close()
