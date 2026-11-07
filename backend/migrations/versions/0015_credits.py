"""Credit balances, immutable ledger and Stripe checkout snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_accounts",
        sa.Column("owner_id", sa.String(41), primary_key=True),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.CheckConstraint("credits >= 0", name="ck_credits_nonnegative"),
    )
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.String(43), primary_key=True),
        sa.Column("owner_id", sa.String(41), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("created_at", sa.Double(), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False, unique=True),
        sa.CheckConstraint("credits <> 0", name="ck_credit_transaction_nonzero"),
        sa.CheckConstraint(
            "(kind = 'usage' AND credits < 0) OR "
            "(kind IN ('purchase', 'refund', 'bonus') AND credits > 0) OR kind = 'adjustment'",
            name="ck_credit_transaction_direction",
        ),
    )
    op.create_index("ix_credit_history", "credit_transactions", ["owner_id", "created_at", "id"])
    op.create_table(
        "credit_checkouts",
        sa.Column("id", sa.String(45), primary_key=True),
        sa.Column("owner_id", sa.String(41), nullable=False),
        sa.Column("pack_id", sa.String(50), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("provider_id", sa.String(255), unique=True),
        sa.Column("expires_at", sa.Double()),
        sa.CheckConstraint("credits > 0 AND price_cents > 0", name="ck_checkout_positive"),
    )
    op.create_index("ix_credit_checkouts_owner_id", "credit_checkouts", ["owner_id"])


def downgrade() -> None:
    for table in ("credit_checkouts", "credit_transactions", "credit_accounts"):
        op.drop_table(table)
