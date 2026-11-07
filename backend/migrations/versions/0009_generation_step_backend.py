"""Record the execution engine without guessing the engine of historical steps."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_steps", sa.Column("backend", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_steps", "backend")
