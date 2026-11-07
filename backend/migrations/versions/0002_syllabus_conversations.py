"""Persist syllabus conversations separately from public course content."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "syllabus_conversations",
        sa.Column("course_id", sa.String(43), sa.ForeignKey("courses.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("history_json", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=False),
        sa.Column("curriculum_json", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
        sa.Column("turns", sa.JSON(), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_syllabus_conversation_revision"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("syllabus_conversations")
