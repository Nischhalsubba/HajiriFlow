"""Protect shared audit events from update and deletion.

Revision ID: 20260907_0008
Revises: 20260907_0007
Create Date: 2026-09-07
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260907_0008"
down_revision: str | None = "20260907_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_audit_event_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events are immutable';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_immutable ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation()")
