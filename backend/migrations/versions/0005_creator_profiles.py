"""Public creator identities; course ownership lives in the aggregate payload."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_profiles",
        sa.Column("id", sa.String(41), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("picture", sa.Text().with_variant(sa.Text(length=16777215), "mysql"), nullable=True),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("creator_profiles")
