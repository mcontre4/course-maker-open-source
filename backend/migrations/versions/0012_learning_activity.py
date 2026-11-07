"""Remember when each person last opened a course or lesson, across devices."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_activity",
        sa.Column("owner_id", sa.String(41), primary_key=True),
        sa.Column("item_id", sa.String(43), primary_key=True),
        sa.Column(
            "last_opened_at",
            sa.DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), "mysql"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_learning_activity_owner_recent",
        "learning_activity",
        ["owner_id", "last_opened_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_activity_owner_recent", table_name="learning_activity")
    op.drop_table("learning_activity")
