from datetime import UTC, datetime

from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.domain.learning_activity import LearningActivity, learning_item_id
from app.courses.domain.standalone import LessonOwnerId
from app.shared.infrastructure.database import Base


class LearningActivityRecord(Base):
    __tablename__ = "learning_activity"
    owner_id: Mapped[str] = mapped_column(String(41), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(43), primary_key=True)
    last_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), "mysql"), nullable=False
    )


class SqlAlchemyLearningActivities:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, activity: LearningActivity) -> None:
        try:
            with self._session.begin_nested():
                self._session.merge(
                    LearningActivityRecord(
                        owner_id=str(activity.owner_id),
                        item_id=str(activity.item_id),
                        last_opened_at=datetime.fromisoformat(activity.last_opened_at),
                    )
                )
        except IntegrityError:
            # Another request recorded this first open at the same moment; its time stands.
            pass

    def recent_by_owner(self, owner_id: LessonOwnerId, limit: int) -> tuple[LearningActivity, ...]:
        records = self._session.scalars(
            select(LearningActivityRecord)
            .where(LearningActivityRecord.owner_id == str(owner_id))
            .order_by(LearningActivityRecord.last_opened_at.desc(), LearningActivityRecord.item_id)
            .limit(limit)
        )
        return tuple(
            LearningActivity(
                owner_id,
                learning_item_id(record.item_id),
                # MySQL drops the zone from stored times; they are always written in UTC.
                record.last_opened_at.replace(
                    tzinfo=record.last_opened_at.tzinfo or UTC
                ).isoformat(),
            )
            for record in records
        )
