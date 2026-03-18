"""Move rating from book to post.

Revision ID: abc123
Revises: 525b350d19d0
Create Date: 2026-03-18

"""

from alembic import op
import sqlalchemy as sa


revision = "abc123"
down_revision = "525b350d19d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("post", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("post_rating", sa.Float(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_post_rating_0_5",
            "post_rating IS NULL OR (post_rating >= 0 AND post_rating <= 5)",
        )

    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.drop_constraint("ck_book_rating_0_5", type_="check")
        batch_op.drop_column("book_rating")


def downgrade():
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("book_rating", sa.Float(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_book_rating_0_5",
            "book_rating IS NULL OR (book_rating >= 0 AND book_rating <= 5)",
        )

    with op.batch_alter_table("post", schema=None) as batch_op:
        batch_op.drop_constraint("ck_post_rating_0_5", type_="check")
        batch_op.drop_column("post_rating")
