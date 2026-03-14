"""add mvp direct chats

Revision ID: 9f3f7e6a1c2b
Revises: 443ec278cab1
Create Date: 2026-03-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "9f3f7e6a1c2b"
down_revision = "443ec278cab1"
branch_labels = None
depends_on = None


chat_type_enum = sa.Enum("DIRECT", name="chattype")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    chat_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("chats", sa.Column("type", chat_type_enum, nullable=True))
    op.add_column("chats", sa.Column("direct_key", sa.String(length=73), nullable=True))

    op.execute("UPDATE chats SET type = 'DIRECT'")
    op.execute(
        """
        UPDATE chats
        SET direct_key = CASE
            WHEN user1_id::text < user2_id::text THEN user1_id::text || ':' || user2_id::text
            ELSE user2_id::text || ':' || user1_id::text
        END
        """
    )

    op.alter_column("chats", "type", nullable=False)
    op.alter_column("chats", "direct_key", nullable=False)
    op.create_unique_constraint("uq_chats_direct_key", "chats", ["direct_key"])

    op.create_table(
        "chat_participants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chat_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_chat_participants_chat_user"),
    )

    op.execute(
        """
        INSERT INTO chat_participants (id, chat_id, user_id, joined_at, last_read_at)
        SELECT gen_random_uuid(), id, user1_id, created_at, created_at FROM chats
        """
    )
    op.execute(
        """
        INSERT INTO chat_participants (id, chat_id, user_id, joined_at, last_read_at)
        SELECT gen_random_uuid(), id, user2_id, created_at, created_at FROM chats
        ON CONFLICT (chat_id, user_id) DO NOTHING
        """
    )

    op.alter_column("messages", "user_id", new_column_name="sender_id")
    op.alter_column("messages", "content", new_column_name="text")
    op.execute("UPDATE messages SET text = '' WHERE text IS NULL")
    op.alter_column("messages", "text", nullable=False)
    op.drop_column("messages", "media_url")
    op.drop_column("messages", "type")


def downgrade() -> None:
    op.add_column("messages", sa.Column("type", postgresql.ENUM("TEXT", "IMAGE", "CALL", name="messagetype", create_type=False), nullable=False, server_default="TEXT"))
    op.add_column("messages", sa.Column("media_url", sa.String(length=255), nullable=True))
    op.alter_column("messages", "text", nullable=True)
    op.alter_column("messages", "text", new_column_name="content")
    op.alter_column("messages", "sender_id", new_column_name="user_id")

    op.drop_table("chat_participants")
    op.drop_constraint("uq_chats_direct_key", "chats", type_="unique")
    op.drop_column("chats", "direct_key")
    op.drop_column("chats", "type")

    chat_type_enum.drop(op.get_bind(), checkfirst=True)
