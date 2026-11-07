from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class CourseRecord(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'ready')", name="ck_courses_status"),
        CheckConstraint("revision > 0", name="ck_courses_revision"),
    )

    id: Mapped[str] = mapped_column(String(43), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}
