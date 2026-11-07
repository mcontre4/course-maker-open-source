"""SQLAlchemy persistence records for users."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class UserRecord(Base):
    """Database representation of a user; never exposed outside this adapter."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(41), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
