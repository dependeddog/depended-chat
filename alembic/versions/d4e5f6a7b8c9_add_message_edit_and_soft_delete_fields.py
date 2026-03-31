"""add message edit and soft delete fields

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-03-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("messages", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("messages", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "deleted_at")
    op.drop_column("messages", "is_deleted")
    op.drop_column("messages", "edited_at")
    op.drop_column("messages", "is_edited")
