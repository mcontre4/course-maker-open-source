"""Record content creation time for newest-first public discovery."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("courses", "standalone_lessons"):
        op.add_column(
            table,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(f"ix_{table}_created_at", table, ["created_at"])


def downgrade() -> None:
    for table in ("courses", "standalone_lessons"):
        op.drop_index(f"ix_{table}_created_at", table_name=table)
        op.drop_column(table, "created_at")
