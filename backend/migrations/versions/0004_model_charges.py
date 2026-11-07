"""Durable per-request model spend, independent of generated content."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_charges",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(43),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("lesson_id", sa.String(43)),
        sa.Column(
            "standalone_lesson_id",
            sa.String(43),
            sa.ForeignKey("standalone_lessons.id", ondelete="CASCADE"),
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("provider_request_id", sa.String(200)),
        sa.Column("usd", sa.Numeric(24, 12)),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Numeric(24, 6)),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.CheckConstraint("usd IS NULL OR usd >= 0", name="ck_model_charge_usd"),
        sa.CheckConstraint(
            "course_id IS NOT NULL OR standalone_lesson_id IS NOT NULL",
            name="ck_model_charge_owner",
        ),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0", name="ck_model_charge_tokens"
        ),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_model_charges_course_id", "model_charges", ["course_id"])
    op.create_index(
        "ix_model_charges_standalone_lesson_id", "model_charges", ["standalone_lesson_id"]
    )


def downgrade() -> None:
    op.drop_table("model_charges")
