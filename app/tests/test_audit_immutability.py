import pytest
from sqlalchemy import select

from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.session import get_session_factory


def test_shared_audit_event_is_immutable(database) -> None:
    del database
    session = get_session_factory()()
    try:
        event = AuditEvent(
            action="security.test",
            object_type="test_object",
            object_id="object-1",
            reason="Verify append-only audit semantics.",
            after_data={"status": "created"},
            context_data={"organization_id": "test-org"},
        )
        session.add(event)
        session.flush()

        persisted = session.scalar(select(AuditEvent).where(AuditEvent.id == event.id))
        assert persisted is not None
        persisted.reason = "tampered"

        with pytest.raises(RuntimeError, match="immutable"):
            session.flush()
        session.rollback()
    finally:
        session.close()
