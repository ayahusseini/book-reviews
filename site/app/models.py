"""SQLAlchemy models for the book review website.

Schema (from ERD):
    author          ←── book_author_mapping ──→ book
    book            ←── book_to_tag_map     ──→ tag
    book            ──→ post
"""

from datetime import datetime, timezone
from app.extensions import db


def get_registered_models() -> list[str]:
    """Return a list of model names registered with SQLAlchemy."""
    return [mapper.class_.__name__ for mapper in db.Model.registry.mappers]


class BookAuthorMapping(db.Model):
    """Junction table containing book-author mappings"""

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


class BookToTagMaping(db.Model):
    """Junction table containing book-tag mappings"""

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
    """Model containing author details"""

    __tablename__ = "author"

    author_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    author_name = db.Column(db.String, nullable=False)
    author_openlibrary_id = db.Column(db.String, nullable=True, unique=True)

    books = db.relationship(
        "Book",
        secondary="book_author_mapping",
        back_populates="authors",
        lazy="select",
    )

    def __repr__(self):
        return f"<Author id={self.author_id} name={self.author_name!r}>"

    def to_dict(self) -> dict:
        return {
            "author_id": self.author_id,
            "author_name": self.author_name,
            "author_openlibrary_id": self.author_openlibrary_id,
        }


class Book(db.Model):
    """Model containing book details"""

    __tablename__ = "book"

    book_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    book_title = db.Column(db.String, nullable=False)
    book_description = db.Column(db.Text, nullable=True)
    book_publication_year = db.Column(db.Integer, nullable=True)
    book_rating = db.Column(db.Integer, nullable=True)
    book_cover_url = db.Column(db.Text, nullable=True)
    book_page_count = db.Column(db.Integer, nullable=True)
    book_isbn = db.Column(db.Text, nullable=False, unique=True)

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

    def to_dict(self) -> dict:
        return {
            "book_id": self.book_id,
            "book_isbn": self.book_isbn,
            "book_title": self.book_title,
            "book_description": self.book_description,
            "book_publication_year": self.book_publication_year,
            "book_rating": self.book_rating,
            "book_cover_url": self.book_cover_url,
            "book_page_count": self.book_page_count,
            "authors": [a.to_dict() for a in self.authors],
            "tags": [t.to_dict() for t in self.tags],
        }


class Tag(db.Model):
    """Model contianing tag details"""

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

    def to_dict(self) -> dict:
        return {
            "tag_id": self.tag_id,
            "tag_name": self.tag_name,
            "tag_description": self.tag_description,
        }


class Post(db.Model):
    """Model containing Post details"""

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

    def to_dict(self) -> dict:
        return {
            "post_id": self.post_id,
            "book_id": self.book_id,
            "post_title": self.post_title,
            "post_author": self.post_author,
            "post_type": self.post_type,
            "post_body_markdown": self.post_body_markdown,
            "post_created_at": self.post_created_at.isoformat(),
            "post_updated_at": self.post_updated_at.isoformat(),
        }
