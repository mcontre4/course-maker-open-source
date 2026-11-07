"""Initial MySQL schema for users and course aggregates."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", sa.String(41), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("courses",
        sa.Column("id", sa.String(43), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'ready')", name="ck_courses_status"),
        sa.CheckConstraint("revision > 0", name="ck_courses_revision"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_courses_title", "courses", ["title"])
    op.create_index("ix_courses_status", "courses", ["status"])


def downgrade() -> None:
    op.drop_table("courses")
    op.drop_table("users")
