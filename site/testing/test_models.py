"""Tests for SQLAlchemy models."""

from app.backend.models import get_registered_models, Author, Book, Post, Tag


def test_get_registered_models(db):
    assert set(get_registered_models(db)) == {
        "Author",
        "Book",
        "BookAuthorMapping",
        "BookToTagMapping",
        "Post",
        "Tag",
    }


def test_author_repr(app, db):
    with app.app_context():
        author = Author(author_name="Aya", author_ol_id="OL1A")
        db.session.add(author)
        db.session.commit()
        assert "Aya" in repr(author)


def test_book_repr(app, db):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Dune")
        db.session.add(book)
        db.session.commit()
        assert "Dune" in repr(book)


def test_tag_repr(app, db):
    with app.app_context():
        tag = Tag(tag_name="fiction")
        db.session.add(tag)
        db.session.commit()
        assert "fiction" in repr(tag)
