from app.database.models import get_registered_models


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
