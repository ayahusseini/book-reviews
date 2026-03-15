from app.database.models import get_registered_models, Author
from app.database.convertor import is_author_in_db


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

        inpsector = inspect(db.engine)
        print(inpsector.get_columns("author"))
        db.session.add(author)
        db.session.commit()

    assert is_author_in_db("EXISTING_ID")
