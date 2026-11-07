from app.users.adapters.persistence.user_repository import SqlAlchemyUserRepository


class MySqlUserRepository(SqlAlchemyUserRepository):
    """MySQL implementation using the shared SQLAlchemy mapping."""
