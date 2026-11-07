"""SQLAlchemy primitives kept at the infrastructure boundary."""

from sqlalchemy import Connection, MetaData, inspect
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    """Base class for persistence records."""


def verify_database_schema(
    connection: Connection, metadata: MetaData, *, excluded_tables: frozenset[str] = frozenset()
) -> None:
    """Reject stale schemas before serving requests that could incur provider costs."""
    inspector = inspect(connection)
    missing: list[str] = []
    for table in metadata.sorted_tables:
        if table.name in excluded_tables:
            continue
        if not inspector.has_table(table.name, schema=table.schema):
            missing.append(table.name)
            continue
        columns = {
            column["name"] for column in inspector.get_columns(table.name, schema=table.schema)
        }
        missing.extend(
            f"{table.name}.{column.name}" for column in table.columns if column.name not in columns
        )
    if missing:
        raise RuntimeError(
            "Database schema is out of date; missing: "
            + ", ".join(missing)
            + ". Apply migrations with `alembic upgrade head` against the API database "
            "before starting the API."
        )


def get_session() -> Session:
    """FastAPI dependency — composition root provides the session.

    This is the only place that creates a ``Session`` directly.
    All other layers receive it via DI from the composition root.
    """
    raise NotImplementedError("Composition root must override get_session dependency")
