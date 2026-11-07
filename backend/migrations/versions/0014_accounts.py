"""Account credentials, revocable sessions, one-time actions and mail outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fail on case-fold collisions rather than silently assigning an existing identity.
    op.execute("UPDATE users SET email = LOWER(TRIM(email))")
    op.create_table(
        "accounts",
        sa.Column("user_id", sa.String(41), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("google_subject", sa.String(255), unique=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.CheckConstraint("password_hash IS NOT NULL OR google_subject IS NOT NULL",
                           name="ck_account_auth_method"),
    )
    op.create_table(
        "login_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(41), sa.ForeignKey("accounts.user_id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.Double(), nullable=False),
        sa.Column("expires_at", sa.Double(), nullable=False, index=True),
        sa.Column("last_seen_at", sa.Double(), nullable=False),
    )
    op.create_table(
        "account_actions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(41), sa.ForeignKey("accounts.user_id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("purpose", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.Double(), nullable=False, index=True),
    )
    op.create_table(
        "account_mail_outbox",
        sa.Column("id", sa.String(41), primary_key=True),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Double(), nullable=False, index=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.Double(), nullable=False),
    )


def downgrade() -> None:
    for table in ("account_mail_outbox", "account_actions", "login_sessions", "accounts"):
        op.drop_table(table)
