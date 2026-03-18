"""SQLAlchemy models for the book review website.

Schema (from ERD):
    author          ←── book_author_mapping ──→ book
    book            ←── book_to_tag_map     ──→ tag
    book            ──→ post
"""

from datetime import datetime, timezone
import re
from sqlalchemy import CheckConstraint
from app.extensions import db


VALID_POST_TYPES = {"review", "essay", "standalone", "note", "quotes"}


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
    author_openlibrary_id = db.Column(
        db.String(250), nullable=True, unique=True
    )

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

    book_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    book_ol_key = db.Column(db.String(250), nullable=False, unique=True)
    book_title = db.Column(db.String(250), nullable=False)
    book_description = db.Column(db.Text, nullable=True)
    book_publication_year = db.Column(db.Integer(), nullable=True)
    book_rating_goodreads = db.Column(db.Float(), nullable=True)
    book_cover_url = db.Column(db.Text(), nullable=True)
    book_page_count = db.Column(db.Integer(), nullable=True)
    book_isbn = db.Column(db.Text(), nullable=True)

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

    posts = db.relationship(
        "Post",
        back_populates="book",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Book id={self.book_id} title={self.book_title!r}>"

    @property
    def book_rating(self) -> float | None:
        """Average rating across all review-type posts,
        or None if no reviews."""
        ratings = [
            p.post_rating
            for p in self.posts
            if p.post_type == "review" and p.post_rating is not None
        ]
        if not ratings:
            return None
        return round(sum(ratings) / len(ratings), 2)

    @property
    def cover_id(self) -> int | None:
        """Extract Open Library cover id from book_cover_url, if present."""
        if not self.book_cover_url:
            return None
        match = re.search(r"/b/id/(\d+)-[A-Z]\.jpg$", self.book_cover_url)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None


class Tag(db.Model):
    """Model containing tag details."""

    __tablename__ = "tag"

    tag_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tag_name = db.Column(db.String, nullable=False, unique=True)
    tag_description = db.Column(db.Text, nullable=True)

    books = db.relationship(
        "Book",
        secondary="book_to_tag_map",
        back_populates="tags",
        lazy="select",
    )

    def __repr__(self):
        return f"<Tag id={self.tag_id} name={self.tag_name!r}>"


class Post(db.Model):
    """Model containing post details."""

    __tablename__ = "post"
    __table_args__ = (
        CheckConstraint(
            "post_rating IS NULL OR (post_rating >= 0 AND post_rating <= 5)",
            name="ck_post_rating_0_5",
        ),
    )

    post_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    post_slug = db.Column(db.String(250), nullable=False, unique=True)
    post_source_path = db.Column(db.Text, nullable=False, unique=True)
    book_id = db.Column(
        db.Integer, db.ForeignKey("book.book_id"), nullable=True
    )
    post_title = db.Column(db.Text, nullable=False)
    post_body_markdown = db.Column(db.Text, nullable=False)
    post_type = db.Column(db.String, nullable=True)
    post_author = db.Column(db.String, nullable=False)
    post_rating = db.Column(db.Float(), nullable=True)

    post_updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    post_created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    book = db.relationship("Book", back_populates="posts")

    def __repr__(self):
        return (
            f"<Post id={self.post_id}"
            f" title={self.post_title!r}"
            f" type={self.post_type!r}>"
        )
