"""Persist standalone lesson quizzes and learner attempts independently of media."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_quizzes",
        sa.Column(
            "lesson_id",
            sa.String(43),
            sa.ForeignKey("standalone_lessons.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_lesson_quiz_revision"),
    )
    op.create_table(
        "lesson_quiz_attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "lesson_id",
            sa.String(43),
            sa.ForeignKey("standalone_lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("learner_id", sa.String(100), nullable=False),
        sa.Column("quiz_revision", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "score >= 0 AND score <= total AND total BETWEEN 1 AND 20",
            name="ck_lesson_quiz_attempt_score",
        ),
        sa.CheckConstraint("quiz_revision >= 1", name="ck_lesson_quiz_attempt_revision"),
    )
    op.create_index(
        "ix_lesson_quiz_attempt_learner", "lesson_quiz_attempts", ["lesson_id", "learner_id"]
    )


def downgrade() -> None:
    op.drop_table("lesson_quiz_attempts")
    op.drop_table("lesson_quizzes")
