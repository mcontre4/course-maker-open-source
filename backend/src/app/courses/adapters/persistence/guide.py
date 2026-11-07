"""SQL persistence for chats and memory; all writes share the caller's unit of work."""

import json
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.guide import (
    GuideMemory,
    GuideMemoryId,
    GuideMessageId,
    GuideThread,
    GuideThreadId,
    GuideTurn,
    OutlineVersion,
)
from app.shared.infrastructure.database import Base

LONG_TEXT = Text().with_variant(LONGTEXT(), "mysql")


class GuideThreadRecord(Base):
    __tablename__ = "guide_threads"
    __table_args__ = (CheckConstraint("revision >= 0", name="ck_guide_thread_revision"),)
    id: Mapped[str] = mapped_column(String(41), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(41), index=True)
    resource_id: Mapped[str] = mapped_column(String(43), index=True)
    guide: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    revision: Mapped[int] = mapped_column(Integer)
    history_json: Mapped[str] = mapped_column(LONG_TEXT)
    summary: Mapped[str] = mapped_column(LONG_TEXT)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GuideTurnRecord(Base):
    __tablename__ = "guide_turns"
    __table_args__ = (
        UniqueConstraint("thread_id", "revision", name="uq_guide_turn_revision"),
        UniqueConstraint("thread_id", "request_id", name="uq_guide_turn_request"),
        CheckConstraint("revision > 0", name="ck_guide_turn_revision"),
    )
    id: Mapped[str] = mapped_column(String(44), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String(41), ForeignKey("guide_threads.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String(80))
    user: Mapped[str] = mapped_column(LONG_TEXT)
    assistant: Mapped[str] = mapped_column(LONG_TEXT)
    tool_history_json: Mapped[str] = mapped_column(LONG_TEXT)


class GuideMemoryRecord(Base):
    __tablename__ = "guide_memories"
    __table_args__ = (
        UniqueConstraint("owner_id", "resource_id", "key", name="uq_guide_memory_scope_key"),
    )
    id: Mapped[str] = mapped_column(String(43), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(41), index=True)
    resource_id: Mapped[str] = mapped_column(String(43))
    key: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[str] = mapped_column(String(44))
    revision: Mapped[int] = mapped_column(Integer)


class OutlineVersionRecord(Base):
    __tablename__ = "outline_versions"
    resource_id: Mapped[str] = mapped_column(String(43), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outline_json: Mapped[str] = mapped_column(LONG_TEXT)
    description: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[str] = mapped_column(String(44), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def snapshot_outline(
    session: Session,
    resource_id: str,
    revision: int,
    outline_json: str,
    description: str = "Saved outline",
) -> None:
    """Called inside aggregate persistence, so manual edits are versioned too."""
    existing = session.get(OutlineVersionRecord, (resource_id, revision))
    if existing is not None:
        if json.loads(existing.outline_json) != json.loads(outline_json):
            raise CourseConflict("A saved outline version cannot be overwritten")
    else:
        parent = session.scalar(
            select(func.max(OutlineVersionRecord.revision)).where(
                OutlineVersionRecord.resource_id == resource_id,
                OutlineVersionRecord.revision < revision,
            )
        )
        session.add(
            OutlineVersionRecord(
                resource_id=resource_id,
                revision=revision,
                parent_revision=parent,
                outline_json=outline_json,
                description=description,
                source_message_id="",
            )
        )


def _thread(record: GuideThreadRecord) -> GuideThread:
    return GuideThread(
        GuideThreadId(record.id),
        record.owner_id,
        record.resource_id,
        record.guide,
        record.title,
        record.revision,
        record.history_json,
        record.summary,
    )


def _turn(record: GuideTurnRecord) -> GuideTurn:
    return GuideTurn(
        GuideMessageId(record.id),
        GuideThreadId(record.thread_id),
        record.revision,
        record.request_id,
        record.user,
        record.assistant,
        record.tool_history_json,
    )


def _version(record: OutlineVersionRecord) -> OutlineVersion:
    return OutlineVersion(
        record.resource_id,
        record.revision,
        record.outline_json,
        record.description,
        record.source_message_id,
        record.created_at.isoformat(),
        record.parent_revision,
    )


class SqlAlchemyGuideRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, thread: GuideThread) -> None:
        self._session.add(GuideThreadRecord(**{**asdict(thread), "id": str(thread.id)}))

    def require_by_id(self, thread_id: GuideThreadId) -> GuideThread:
        record = self._session.get(GuideThreadRecord, str(thread_id), populate_existing=True)
        if record is None:
            raise CourseNotFound("Chat not found")
        return _thread(record)

    def list_threads(self, owner_id: str, resource_id: str, guide: str) -> tuple[GuideThread, ...]:
        records = self._session.scalars(
            select(GuideThreadRecord)
            .where(
                GuideThreadRecord.owner_id == owner_id,
                GuideThreadRecord.resource_id == resource_id,
                GuideThreadRecord.guide == guide,
            )
            .order_by(GuideThreadRecord.created_at, GuideThreadRecord.id)
        )
        return tuple(_thread(r) for r in records)

    def save(self, thread: GuideThread, expected_revision: int) -> None:
        result = self._session.connection().execute(
            update(GuideThreadRecord)
            .where(
                GuideThreadRecord.id == str(thread.id),
                GuideThreadRecord.revision == expected_revision,
            )
            .values(**{**asdict(thread), "id": str(thread.id)})
        )
        if result.rowcount != 1:
            raise CourseConflict("Chat changed; reload and retry")

    def add_turn(self, turn: GuideTurn) -> None:
        self._session.add(
            GuideTurnRecord(
                **{**asdict(turn), "id": str(turn.id), "thread_id": str(turn.thread_id)}
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise CourseConflict("Message already sent or chat changed; reload and retry") from exc

    def list_turns(
        self, thread_id: GuideThreadId, before: int | None = None, limit: int = 100
    ) -> tuple[GuideTurn, ...]:
        query = select(GuideTurnRecord).where(GuideTurnRecord.thread_id == str(thread_id))
        if before is not None:
            query = query.where(GuideTurnRecord.revision < before)
        records = self._session.scalars(
            query.order_by(GuideTurnRecord.revision.desc()).limit(limit)
        )
        return tuple(reversed([_turn(r) for r in records]))

    def get_by_request_id(self, thread_id: GuideThreadId, request_id: str) -> GuideTurn | None:
        record = self._session.scalar(
            select(GuideTurnRecord).where(
                GuideTurnRecord.thread_id == str(thread_id),
                GuideTurnRecord.request_id == request_id,
            )
        )
        return _turn(record) if record else None

    def list_memories(self, owner_id: str, resource_id: str) -> tuple[GuideMemory, ...]:
        records = self._session.scalars(
            select(GuideMemoryRecord)
            .where(
                GuideMemoryRecord.owner_id == owner_id,
                GuideMemoryRecord.resource_id.in_(("", resource_id)),
            )
            .order_by(GuideMemoryRecord.key)
        )
        return tuple(
            GuideMemory(
                GuideMemoryId(r.id),
                r.owner_id,
                r.resource_id,
                r.key,
                r.content,
                r.source_message_id,
                r.revision,
            )
            for r in records
        )

    def save_memory(self, memory: GuideMemory, expected_revision: int) -> None:
        if expected_revision == 0:
            self._session.add(GuideMemoryRecord(**{**asdict(memory), "id": str(memory.id)}))
            try:
                self._session.flush()
            except IntegrityError as exc:
                raise CourseConflict("Memory changed; reload and retry") from exc
        else:
            result = self._session.connection().execute(
                update(GuideMemoryRecord)
                .where(
                    GuideMemoryRecord.id == str(memory.id),
                    GuideMemoryRecord.owner_id == memory.owner_id,
                    GuideMemoryRecord.revision == expected_revision,
                )
                .values(**{**asdict(memory), "id": str(memory.id)})
            )
            if result.rowcount != 1:
                raise CourseConflict("Memory changed; reload and retry")

    def delete_memory(self, owner_id: str, memory_id: str, expected_revision: int) -> None:
        result = self._session.connection().execute(
            delete(GuideMemoryRecord).where(
                GuideMemoryRecord.id == memory_id,
                GuideMemoryRecord.owner_id == owner_id,
                GuideMemoryRecord.revision == expected_revision,
            )
        )
        if result.rowcount != 1:
            raise CourseConflict("Memory changed; reload and retry")

    def list_versions(
        self, resource_id: str, limit: int = 50, before: int | None = None
    ) -> tuple[OutlineVersion, ...]:
        query = select(OutlineVersionRecord).where(OutlineVersionRecord.resource_id == resource_id)
        if before is not None:
            query = query.where(OutlineVersionRecord.revision < before)
        return tuple(
            _version(r)
            for r in self._session.scalars(
                query.order_by(OutlineVersionRecord.revision.desc()).limit(limit)
            )
        )

    def require_version(self, resource_id: str, revision: int) -> OutlineVersion:
        record = self._session.get(OutlineVersionRecord, (resource_id, revision))
        if record is None:
            raise CourseNotFound("Outline version not found")
        return _version(record)

    def annotate_version(
        self, resource_id: str, revision: int, description: str, source_message_id: str
    ) -> None:
        self._session.flush()
        record = self._session.get(OutlineVersionRecord, (resource_id, revision))
        if record:
            record.description, record.source_message_id = description[:2000], source_message_id

    def add_version(self, version: OutlineVersion) -> None:
        snapshot_outline(
            self._session,
            version.resource_id,
            version.revision,
            version.outline_json,
            version.description,
        )
        self.annotate_version(
            version.resource_id, version.revision, version.description, version.source_message_id
        )

    def search_history(self, owner_id: str, resource_id: str, query: str) -> tuple[GuideTurn, ...]:
        # contains(autoescape) prevents user text becoming SQL wildcards.
        records = self._session.scalars(
            select(GuideTurnRecord)
            .join(GuideThreadRecord)
            .where(
                GuideThreadRecord.owner_id == owner_id,
                GuideThreadRecord.resource_id == resource_id,
                or_(
                    GuideTurnRecord.user.icontains(query, autoescape=True),
                    GuideTurnRecord.assistant.icontains(query, autoescape=True),
                ),
            )
            .order_by(GuideTurnRecord.thread_id, GuideTurnRecord.revision.desc())
            .limit(20)
        )
        return tuple(_turn(r) for r in records)
