"""SQLAlchemy models for the book review website.

Schema (from ERD):
    author          ←── book_author_mapping ──→ book
    book            ←── book_to_tag_map     ──→ tag
    book            ──→ post
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class BookAuthorMapping(db.Model):
    __tablename__ = "book_author_mapping"

    book_author_mapping_id = db.Column(
        db.BigInteger, primary_key=True, autoincrement=True
    )
    author_id = db.Column(
        db.BigInteger, db.ForeignKey("author.author_id"), nullable=False
    )
    book_id = db.Column(
        db.BigInteger, db.ForeignKey("book.book_id"), nullable=False
    )

    def __repr__(self):
        return (
            f"<BookAuthorMapping book={self.book_id} author={self.author_id}>"
        )


class BookToTagMap(db.Model):
    __tablename__ = "book_to_tag_map"

    book_to_tag_map_id = db.Column(
        db.BigInteger, primary_key=True, autoincrement=True
    )
    book_id = db.Column(
        db.BigInteger, db.ForeignKey("book.book_id"), nullable=False
    )
    tag_id = db.Column(
        db.BigInteger, db.ForeignKey("tag.tag_id"), nullable=False
    )

    def __repr__(self):
        return f"<BookToTagMap book={self.book_id} tag={self.tag_id}>"


class Author(db.Model):
    __tablename__ = "author"

    author_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    author_name = db.Column(db.String, nullable=False)

    books = db.relationship(
        "Book",
        secondary="book_author_mapping",
        back_populates="authors",
        lazy="select",
    )

    def __repr__(self):
        return f"<Author id={self.author_id} name={self.author_name!r}>"


class Book(db.Model):
    __tablename__ = "book"

    book_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    book_title = db.Column(db.String, nullable=False)
    book_description = db.Column(db.Text, nullable=True)
    book_publication_year = db.Column(db.Integer, nullable=True)
    book_rating = db.Column(db.Integer, nullable=True)
    book_cover_url = db.Column(db.Text, nullable=True)
    book_page_count = db.Column(db.Integer, nullable=True)
    book_isbn = db.Column(db.Text, nullable=True)

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


class Tag(db.Model):
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
    __tablename__ = "post"

    post_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    book_id = db.Column(
        db.Integer, db.ForeignKey("book.book_id"), nullable=True
    )
    post_title = db.Column(db.Text, nullable=False)
    post_body_markdown = db.Column(db.Text, nullable=False)

    post_type = db.Column(db.String, nullable=True)

    post_author = db.Column(db.String, nullable=False)

    post_updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    post_created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship: post → book (many posts can reference one book)
    book = db.relationship("Book", back_populates="posts")

    def __repr__(self):
        return (
            f"<Post id={self.post_id}"
            + f" title={self.post_title!r}"
            + f" type={self.post_type!r}"
        )
