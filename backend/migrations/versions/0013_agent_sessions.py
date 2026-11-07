"""User- and task-scoped native agent conversations."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("syllabus_conversations", sa.Column("agent_session_id", sa.String(42)))
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(42), primary_key=True),
        sa.Column("owner_id", sa.String(100), nullable=False, index=True),
        sa.Column("agent", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True, index=True),
        sa.Column("job_id", sa.String(100), nullable=True, index=True),
        sa.Column(
            "history_json",
            sa.Text().with_variant(sa.Text(length=4294967295), "mysql"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_agent_session_revision"),
    )


def downgrade() -> None:
    op.drop_table("agent_sessions")
    op.drop_column("syllabus_conversations", "agent_session_id")
