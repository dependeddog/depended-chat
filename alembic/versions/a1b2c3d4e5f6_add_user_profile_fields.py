"""add user profile fields

Revision ID: a1b2c3d4e5f6
Revises: c9c521647d0e
Create Date: 2026-03-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "c9c521647d0e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("avatar", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("avatar_mime_type", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_mime_type")
    op.drop_column("users", "avatar")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "bio")
