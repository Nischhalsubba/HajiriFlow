from sqlalchemy import create_engine, inspect

from hajiriflow.db import models  # noqa: F401
from hajiriflow.db.base import Base


def test_identity_schema_can_be_created() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    tables = set(inspect(engine).get_table_names())
    assert {
        "audit_events",
        "auth_sessions",
        "authentication_attempts",
        "permissions",
        "role_permissions",
        "roles",
        "user_accounts",
        "user_roles",
    }.issubset(tables)
