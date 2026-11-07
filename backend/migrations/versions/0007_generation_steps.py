"""Persist generation timing independently of model billing."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_steps",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("course_id", sa.String(43), sa.ForeignKey("courses.id", ondelete="CASCADE")),
        sa.Column("lesson_id", sa.String(43)),
        sa.Column(
            "standalone_lesson_id",
            sa.String(43),
            sa.ForeignKey("standalone_lessons.id", ondelete="CASCADE"),
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("started_at", sa.Float(53), nullable=False),
        sa.Column("finished_at", sa.Float(53)),
        sa.CheckConstraint(
            "course_id IS NOT NULL OR standalone_lesson_id IS NOT NULL",
            name="ck_generation_step_owner",
        ),
        sa.CheckConstraint(
            "started_at >= 0 AND (finished_at IS NULL OR finished_at >= started_at)",
            name="ck_generation_step_time",
        ),
    )
    op.create_index("ix_generation_steps_course_id", "generation_steps", ["course_id"])
    op.create_index("ix_generation_steps_lesson_id", "generation_steps", ["lesson_id"])
    op.create_index(
        "ix_generation_steps_standalone_lesson_id", "generation_steps", ["standalone_lesson_id"]
    )


def downgrade() -> None:
    op.drop_table("generation_steps")
