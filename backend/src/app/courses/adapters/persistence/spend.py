from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, Numeric, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.domain.spend import GenerationStep, ModelCharge
from app.shared.infrastructure.database import Base


class ModelChargeRecord(Base):
    __tablename__ = "model_charges"
    __table_args__ = (
        CheckConstraint(
            "course_id IS NOT NULL OR standalone_lesson_id IS NOT NULL",
            name="ck_model_charge_owner",
        ),
        CheckConstraint("usd IS NULL OR usd >= 0", name="ck_model_charge_usd"),
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0", name="ck_model_charge_tokens"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    course_id: Mapped[str | None] = mapped_column(
        String(43), ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[str | None] = mapped_column(String(43))
    standalone_lesson_id: Mapped[str | None] = mapped_column(
        String(43), ForeignKey("standalone_lessons.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(200))
    provider_request_id: Mapped[str | None] = mapped_column(String(200))
    usd: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    credits: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    estimated: Mapped[bool]


class GenerationStepRecord(Base):
    __tablename__ = "generation_steps"
    __table_args__ = (
        CheckConstraint(
            "course_id IS NOT NULL OR standalone_lesson_id IS NOT NULL",
            name="ck_generation_step_owner",
        ),
        CheckConstraint(
            "started_at >= 0 AND (finished_at IS NULL OR finished_at >= started_at)",
            name="ck_generation_step_time",
        ),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    course_id: Mapped[str | None] = mapped_column(
        String(43), ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[str | None] = mapped_column(String(43), index=True)
    standalone_lesson_id: Mapped[str | None] = mapped_column(
        String(43), ForeignKey("standalone_lessons.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[float] = mapped_column(Float(53))
    finished_at: Mapped[float | None] = mapped_column(Float(53))
    backend: Mapped[str | None] = mapped_column(String(32))


class SqlSpendRepository:
    """Each ledger write survives content rollback and owns a separate short session."""

    def __init__(self, sessions: Callable[[], Session]) -> None:
        self._sessions = sessions

    def save_step(self, step: GenerationStep) -> None:
        with self._sessions() as session, session.begin():
            values = asdict(step)
            values["standalone_lesson_id"] = step.lesson_id if step.course_id is None else None
            session.merge(GenerationStepRecord(**values))

    def list_steps(
        self, *, course_id: str | None = None, lesson_id: str | None = None
    ) -> tuple[GenerationStep, ...]:
        with self._sessions() as session:
            query = select(GenerationStepRecord)
            if course_id is not None:
                query = query.where(GenerationStepRecord.course_id == course_id)
            else:
                query = query.where(
                    GenerationStepRecord.course_id.is_(None),
                    GenerationStepRecord.lesson_id == lesson_id,
                )
            return tuple(
                GenerationStep(
                    **{
                        field: getattr(record, field)
                        for field in GenerationStep.__dataclass_fields__
                    }
                )
                for record in session.scalars(query.order_by(GenerationStepRecord.started_at))
            )

    def list_by_course_id(self, course_id: str) -> tuple[ModelCharge, ...]:
        with self._sessions() as session:
            records = session.scalars(
                select(ModelChargeRecord)
                .where(ModelChargeRecord.course_id == course_id)
                .order_by(ModelChargeRecord.id)
            ).all()
            return tuple(
                ModelCharge(
                    **{field: getattr(record, field) for field in ModelCharge.__dataclass_fields__}
                )
                for record in records
            )

    def save(self, charge: ModelCharge) -> None:
        with self._sessions() as session, session.begin():
            record = session.scalar(
                select(ModelChargeRecord).where(ModelChargeRecord.id == charge.id).with_for_update()
            )
            values = asdict(charge)
            values["standalone_lesson_id"] = charge.lesson_id if charge.course_id is None else None
            if record is None:
                session.add(ModelChargeRecord(**values))
                return
            # A delayed response/journal replay must not erase reconciled billing.
            if record.usd is not None and charge.usd is None:
                values.pop("usd")
                values.pop("estimated")
            for field in ("credits", "provider_request_id"):
                if values[field] is None:
                    values.pop(field)
            if record.provider_request_id is not None and charge.provider_request_id is None:
                values.pop("model")
            values["input_tokens"] = max(record.input_tokens, charge.input_tokens)
            values["output_tokens"] = max(record.output_tokens, charge.output_tokens)
            for field, value in values.items():
                setattr(record, field, value)

    def list_by_lesson_id(self, lesson_id: str) -> tuple[ModelCharge, ...]:
        with self._sessions() as session:
            records = session.scalars(
                select(ModelChargeRecord)
                .where(ModelChargeRecord.standalone_lesson_id == lesson_id)
                .order_by(ModelChargeRecord.id)
            ).all()
            return tuple(
                ModelCharge(
                    **{field: getattr(record, field) for field in ModelCharge.__dataclass_fields__}
                )
                for record in records
            )
