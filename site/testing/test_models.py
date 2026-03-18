"""Tests for SQLAlchemy models."""

from app.database.models import get_registered_models, Author, Book, Post, Tag


def test_get_registered_models(db):
    assert set(get_registered_models(db)) == {
        "Author",
        "Book",
        "BookAuthorMapping",
        "BookToTagMapping",
        "Post",
        "Tag",
    }


def test_book_rating_is_none_with_no_posts(app, db):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        db.session.add(book)
        db.session.commit()
        assert book.book_rating is None


def test_book_rating_is_none_with_no_review_posts(app, db):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        post = Post(
            post_slug="essay-1",
            post_source_path="essay-1.md",
            post_title="An Essay",
            post_body_markdown="body",
            post_author="Aya",
            post_type="essay",
            post_rating=None,
            book=book,
        )
        db.session.add_all([book, post])
        db.session.commit()
        assert book.book_rating is None


def test_book_rating_averages_review_post_ratings(app, db):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        post_a = Post(
            post_slug="review-1",
            post_source_path="review-1.md",
            post_title="Review 1",
            post_body_markdown="body",
            post_author="Aya",
            post_type="review",
            post_rating=4.0,
            book=book,
        )
        post_b = Post(
            post_slug="review-2",
            post_source_path="review-2.md",
            post_title="Review 2",
            post_body_markdown="body",
            post_author="Aya",
            post_type="review",
            post_rating=5.0,
            book=book,
        )
        db.session.add_all([book, post_a, post_b])
        db.session.commit()
        assert book.book_rating == 4.5


def test_book_rating_ignores_reviews_without_rating(app, db):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        post_a = Post(
            post_slug="review-1",
            post_source_path="review-1.md",
            post_title="Review 1",
            post_body_markdown="body",
            post_author="Aya",
            post_type="review",
            post_rating=4.0,
            book=book,
        )
        post_b = Post(
            post_slug="review-2",
            post_source_path="review-2.md",
            post_title="Review 2",
            post_body_markdown="body",
            post_author="Aya",
            post_type="review",
            post_rating=None,
            book=book,
        )
        db.session.add_all([book, post_a, post_b])
        db.session.commit()
        assert book.book_rating == 4.0


def test_author_repr(app, db):
    with app.app_context():
        author = Author(author_name="Aya", author_openlibrary_id="OL1A")
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
