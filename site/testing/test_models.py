from app.database.models import get_registered_models, Author, Book
from app.database.convertor import is_author_in_db, is_book_in_db


def test_get_registered_models(db):
    assert set(get_registered_models(db)) == set(
        [
            "Author",
            "Book",
            "BookAuthorMapping",
            "BookToTagMaping",
            "Post",
            "Tag",
        ]
    )


def test_author_in_db(app, db):
    with app.app_context():
        author = Author(author_name="a", author_openlibrary_id="EXISTING_ID")
        from sqlalchemy import inspect

        db.session.add(author)
        db.session.commit()

    assert is_author_in_db("EXISTING_ID")


def test_book_in_db(app, db):
    with app.app_context():
        b = Book(book_ol_key="h", book_title="a")
        from sqlalchemy import inspect

        db.session.add(b)
        db.session.commit()

    assert is_book_in_db("h")


def test_author_not_in_db(app, db):
    with app.app_context():
        author = Author(author_name="a", author_openlibrary_id="EXISTING_ID")
        db.session.add(author)
        db.session.commit()

    assert not is_author_in_db("NOT_EXISTING_ID")
