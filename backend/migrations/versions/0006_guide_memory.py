"""Persistent guide chats, scoped memories, and immutable outline revisions."""

import json

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    long_text = sa.Text().with_variant(sa.Text(length=4294967295), "mysql")
    op.create_table(
        "guide_threads",
        sa.Column("id", sa.String(41), primary_key=True),
        sa.Column("owner_id", sa.String(41), nullable=False, index=True),
        sa.Column("resource_id", sa.String(43), nullable=False, index=True),
        sa.Column("guide", sa.String(20), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("history_json", long_text, nullable=False),
        sa.Column("summary", long_text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision >= 0", name="ck_guide_thread_revision"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "guide_turns",
        sa.Column("id", sa.String(44), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(41),
            sa.ForeignKey("guide_threads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("request_id", sa.String(80), nullable=False),
        sa.Column("user", long_text, nullable=False),
        sa.Column("assistant", long_text, nullable=False),
        sa.Column("tool_history_json", long_text, nullable=False),
        sa.UniqueConstraint("thread_id", "revision", name="uq_guide_turn_revision"),
        sa.UniqueConstraint("thread_id", "request_id", name="uq_guide_turn_request"),
        sa.CheckConstraint("revision > 0", name="ck_guide_turn_revision"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "guide_memories",
        sa.Column("id", sa.String(43), primary_key=True),
        sa.Column("owner_id", sa.String(41), nullable=False, index=True),
        sa.Column("resource_id", sa.String(43), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_message_id", sa.String(44), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.UniqueConstraint("owner_id", "resource_id", "key", name="uq_guide_memory_scope_key"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "outline_versions",
        sa.Column("resource_id", sa.String(43), primary_key=True),
        sa.Column("revision", sa.Integer, primary_key=True),
        sa.Column("parent_revision", sa.Integer, nullable=True),
        sa.Column("outline_json", long_text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_message_id", sa.String(44), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
    )
    # Preserve the current baseline. Older outlines were overwritten before this migration
    # and cannot be reconstructed faithfully from the legacy conversation summaries.
    connection = op.get_bind()
    versions = sa.table(
        "outline_versions",
        sa.column("resource_id"),
        sa.column("revision"),
        sa.column("outline_json"),
        sa.column("description"),
        sa.column("source_message_id"),
    )
    for row in connection.execute(sa.text("SELECT id, payload FROM standalone_lessons")):
        payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
        plan = payload["content"].get("plan")
        if plan:
            connection.execute(
                versions.insert().values(
                    resource_id=row.id,
                    revision=payload["revision"],
                    outline_json=json.dumps(plan),
                    description="Existing outline",
                    source_message_id="",
                )
            )
    for row in connection.execute(
        sa.text("SELECT course_id, revision, curriculum_json FROM syllabus_conversations")
    ):
        if row.curriculum_json:
            connection.execute(
                versions.insert().values(
                    resource_id=row.course_id,
                    revision=row.revision,
                    outline_json=row.curriculum_json,
                    description="Existing syllabus",
                    source_message_id="",
                )
            )


def downgrade() -> None:
    for table in ("outline_versions", "guide_memories", "guide_turns", "guide_threads"):
        op.drop_table(table)
