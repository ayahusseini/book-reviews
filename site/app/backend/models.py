"""SQLAlchemy models for the book review website.

Schema (from ERD):
    author          ←── book_author_mapping ──→ book
    book            ←── book_to_tag_map     ──→ tag
    book            ──→ quote
"""

from datetime import datetime, timezone
from sqlalchemy import CheckConstraint
from app.extensions import db


def get_registered_models(database=db) -> list[str]:
    """Return a list of model names registered with SQLAlchemy."""
    return [
        mapper.class_.__name__ for mapper in database.Model.registry.mappers
    ]


class BookAuthorMapping(db.Model):
    """Junction table containing book-author mappings."""

    __tablename__ = "book_author_mapping"

    book_author_mapping_id = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    author_id = db.Column(
        db.Integer(), db.ForeignKey("author.author_id"), nullable=False
    )
    book_id = db.Column(
        db.Integer(), db.ForeignKey("book.book_id"), nullable=False
    )

    def __repr__(self):
        return (
            f"<BookAuthorMapping book={self.book_id} author={self.author_id}>"
        )


class BookToTagMapping(db.Model):
    """Junction table containing book-tag mappings."""

    __tablename__ = "book_to_tag_map"

    book_to_tag_map_id = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    book_id = db.Column(
        db.Integer(), db.ForeignKey("book.book_id"), nullable=False
    )
    tag_id = db.Column(
        db.Integer(), db.ForeignKey("tag.tag_id"), nullable=False
    )

    def __repr__(self):
        return f"<BookToTagMapping book={self.book_id} tag={self.tag_id}>"


class Author(db.Model):
    """Model containing author details."""

    __tablename__ = "author"

    author_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    author_name = db.Column(db.String(750), nullable=False)
    author_ol_id = db.Column(db.String(250), nullable=False, unique=True)

    books = db.relationship(
        "Book",
        secondary="book_author_mapping",
        back_populates="authors",
        lazy="select",
    )

    def __repr__(self):
        return f"<Author id={self.author_id} name={self.author_name!r}>"


class Book(db.Model):
    """Model containing book details."""

    __tablename__ = "book"
    __table_args__ = (
        CheckConstraint(
            "book_rating IS NULL OR (book_rating >= 0 AND book_rating <= 5)",
            name="ck_book_rating_0_5",
        ),
    )

    book_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    book_ol_key = db.Column(db.String(250), nullable=False, unique=True)
    book_title = db.Column(db.String(250), nullable=False)
    book_description = db.Column(db.Text, nullable=True)
    book_publication_year = db.Column(db.Integer(), nullable=True)
    book_rating = db.Column(db.Float(), nullable=True)
    book_page_count = db.Column(db.Integer(), nullable=True)

    authors = db.relationship(
        "Author",
        secondary="book_author_mapping",
        back_populates="books",
        lazy="select",
    )

    tags = db.relationship(
        "Tag",
        secondary="book_to_tag_map",
        back_populates="books",
        lazy="select",
    )

    review_markdown = db.Column(db.Text, nullable=True)
    review_created_at = db.Column(db.DateTime, nullable=True)
    review_updated_at = db.Column(db.DateTime, nullable=True)

    quotes = db.relationship(
        "Quote",
        back_populates="book",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Book id={self.book_id} title={self.book_title!r}>"


class Tag(db.Model):
    """Model containing tag details."""

    __tablename__ = "tag"

    tag_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tag_name = db.Column(db.String, nullable=False, unique=True)

    books = db.relationship(
        "Book",
        secondary="book_to_tag_map",
        back_populates="tags",
        lazy="select",
    )

    def __repr__(self):
        return f"<Tag id={self.tag_id} name={self.tag_name!r}>"


class Poem(db.Model):
    """Model containing poem details."""

    __tablename__ = "poem"

    poem_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    poem_slug = db.Column(db.String(250), nullable=False, unique=True)
    poem_title = db.Column(db.Text, nullable=False)
    poem_body_markdown = db.Column(db.Text, nullable=False)
    poem_author = db.Column(db.String, nullable=False)

    poem_created_at = db.Column(db.DateTime, nullable=True)
    poem_updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Poem id={self.poem_id} title={self.poem_title!r}>"


class Quote(db.Model):
    """Model containing a quote extracted from a book review."""

    __tablename__ = "quote"

    quote_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    quote_slug = db.Column(db.String(250), nullable=False, unique=True)
    quote_text = db.Column(db.Text, nullable=False)

    book_id = db.Column(
        db.Integer, db.ForeignKey("book.book_id"), nullable=False
    )

    book = db.relationship("Book", back_populates="quotes")

    def __repr__(self):
        return f"<Quote id={self.quote_id} slug={self.quote_slug!r}>"
