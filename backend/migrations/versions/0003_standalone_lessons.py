"""Lessons owned independently of a course."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "standalone_lessons",
        sa.Column("id", sa.String(43), primary_key=True),
        sa.Column("owner_id", sa.String(41), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("minutes BETWEEN 1 AND 10", name="ck_standalone_minutes"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_standalone_lessons_owner_id", "standalone_lessons", ["owner_id"])


def downgrade() -> None:
    op.drop_table("standalone_lessons")
