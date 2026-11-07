"""Versioned interactives for standalone and course lessons."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_interactives",
        sa.Column("id", sa.String(48), primary_key=True),
        sa.Column("lesson_id", sa.String(43), nullable=False),
        sa.Column(
            "standalone_lesson_id",
            sa.String(43),
            sa.ForeignKey("standalone_lessons.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "course_id",
            sa.String(43),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_lesson_interactive_revision"),
        sa.CheckConstraint("slot BETWEEN 1 AND 10", name="ck_lesson_interactive_slot"),
        sa.CheckConstraint(
            "(standalone_lesson_id IS NOT NULL AND standalone_lesson_id = lesson_id "
            "AND course_id IS NULL) OR "
            "(standalone_lesson_id IS NULL AND course_id IS NOT NULL)",
            name="ck_lesson_interactive_parent",
        ),
        sa.UniqueConstraint("lesson_id", "slot", name="uq_lesson_interactive_slot"),
    )
    op.create_index("ix_lesson_interactive_order", "lesson_interactives", ["lesson_id", "position"])
    op.create_index("ix_lesson_interactives_course_id", "lesson_interactives", ["course_id"])


def downgrade() -> None:
    op.drop_table("lesson_interactives")
