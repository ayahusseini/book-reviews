"""Make author_ol_id non-nullable.

Revision ID: b7e2a4f91c03
Revises: f53c90fe7bbc
Create Date: 2026-04-13

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7e2a4f91c03"
down_revision = "f53c90fe7bbc"
branch_labels = None
depends_on = None


def upgrade():
    # Fill any NULL author_ol_id values before enforcing the constraint.
    # In practice all existing authors come from Open Library and have an ID,
    # but this guards against edge cases.
    op.execute(
        "UPDATE author SET author_ol_id = 'manual-' || author_id "
        "WHERE author_ol_id IS NULL"
    )
    with op.batch_alter_table("author") as batch_op:
        batch_op.alter_column(
            "author_ol_id",
            existing_type=sa.String(length=250),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("author") as batch_op:
        batch_op.alter_column(
            "author_ol_id",
            existing_type=sa.String(length=250),
            nullable=True,
        )
