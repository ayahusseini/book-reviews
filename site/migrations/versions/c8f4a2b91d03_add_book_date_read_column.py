"""Add book_date_read column.

Revision ID: c8f4a2b91d03
Revises: b67065c6ea17
Create Date: 2026-09-13 18:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8f4a2b91d03"
down_revision = "b67065c6ea17"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("book_date_read", sa.Date(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.drop_column("book_date_read")
