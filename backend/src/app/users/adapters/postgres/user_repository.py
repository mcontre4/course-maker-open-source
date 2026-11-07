from app.users.adapters.persistence.user_repository import SqlAlchemyUserRepository


class PostgresUserRepository(SqlAlchemyUserRepository):
    """PostgreSQL implementation using the shared SQLAlchemy mapping."""
