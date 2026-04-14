"""Tests for site/app/database/upserts.py.

Each test focuses on one behaviour. Database state is rolled back after
every test via the session fixture, so tests are fully isolated.
"""

import pytest
from app.backend.models import Book, Post, Tag
from app.backend.upserts import (
    attach_tags,
    upsert_books,
    upsert_post,
    upsert_single_manual_book,
    upsert_tags,
)
from app.backend.open_library import AuthorData, BookData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_book_data(ol_key="OL1W", title="A Book", authors=None):
    return BookData(
        ol_key=ol_key,
        title=title,
        description="A description.",
        publication_year=2000,
        page_count=300,
        authors=authors or [AuthorData(name="An Author", ol_id="OLA1")],
    )


def make_book(session, ol_key="OL1W", title="A Book"):
    book = Book(book_ol_key=ol_key, book_title=title)
    session.add(book)
    session.flush()
    return book


def make_post(session, slug, post_type="standalone", book=None, **kwargs):
    post = Post(
        post_slug=slug,
        post_title=kwargs.get("title", "A Post"),
        post_body_markdown=kwargs.get("body", "body text"),
        post_type=post_type,
        post_author=kwargs.get("author", "Aya"),
        book=book,
    )
    session.add(post)
    session.flush()
    return post


# ---------------------------------------------------------------------------
# upsert_tags
# ---------------------------------------------------------------------------


class TestUpsertTags:
    def test_creates_new_tags(self, session):
        result = upsert_tags(["fiction", "non-fiction"])
        assert set(result.keys()) == {"fiction", "non-fiction"}
        assert all(t.tag_id is not None for t in result.values())

    def test_returns_existing_tags_without_duplicating(self, session):
        upsert_tags(["classics"])
        result = upsert_tags(["classics"])
        assert len(result) == 1
        assert session.query(Tag).filter_by(tag_name="classics").count() == 1

    def test_deduplicates_input(self, session):
        result = upsert_tags(["poetry", "poetry", "poetry"])
        assert len(result) == 1

    def test_empty_input_returns_empty_dict(self, session):
        assert upsert_tags([]) == {}

    def test_mixes_new_and_existing(self, session):
        upsert_tags(["existing"])
        result = upsert_tags(["existing", "brand-new"])
        assert set(result.keys()) == {"existing", "brand-new"}


# ---------------------------------------------------------------------------
# upsert_books
# ---------------------------------------------------------------------------


class TestUpsertBooks:
    def test_inserts_new_books_into_db(self, session):
        upsert_books([make_book_data("OL1W", "Dune")])
        book = session.query(Book).filter_by(book_ol_key="OL1W").first()
        assert book is not None
        assert book.book_title == "Dune"

    def test_returns_ol_key_to_book_map(self, session):
        result = upsert_books([make_book_data("OL1W"), make_book_data("OL2W")])
        assert set(result.keys()) == {"OL1W", "OL2W"}

    def test_empty_input_returns_empty(self, session):
        assert upsert_books([]) == {}

    def test_title_override_applied_to_new_book(self, session):
        upsert_books(
            [make_book_data("OL1W", "Wrong Title")],
            title_overrides={"OL1W": "Correct Title"},
        )
        book = session.query(Book).filter_by(book_ol_key="OL1W").first()
        assert book.book_title == "Correct Title"

    def test_description_override_applied(self, session):
        upsert_books(
            [make_book_data("OL1W")],
            description_overrides={"OL1W": "My custom description"},
        )
        book = session.query(Book).filter_by(book_ol_key="OL1W").first()
        assert book.book_description == "My custom description"

    def test_rating_applied(self, session):
        upsert_books([make_book_data("OL1W")], rating_map={"OL1W": 4.5})
        book = session.query(Book).filter_by(book_ol_key="OL1W").first()
        assert book.book_rating == 4.5

    def test_tags_attached(self, session):
        upsert_books(
            [make_book_data("OL1W")],
            tag_map={"OL1W": ["fiction", "read-2026"]},
        )
        book = session.query(Book).filter_by(book_ol_key="OL1W").first()
        tag_names = {t.tag_name for t in book.tags}
        assert tag_names == {"fiction", "read-2026"}

    def test_existing_book_is_updated_not_duplicated(self, session):
        upsert_books([make_book_data("OL1W", "Original")])
        upsert_books([make_book_data("OL1W", "Updated")])
        count = session.query(Book).filter_by(book_ol_key="OL1W").count()
        assert count == 1

    def test_authors_attached(self, session):
        data = make_book_data(
            "OL1W", authors=[AuthorData(name="Jane Austen", ol_id="OLA99")]
        )
        upsert_books([data])
        book = session.query(Book).filter_by(book_ol_key="OL1W").first()
        assert len(book.authors) == 1
        assert book.authors[0].author_name == "Jane Austen"

    def test_batch_uses_bulk_inserts(self, session, execute_spy):
        upsert_books(
            [make_book_data("OL1W"), make_book_data("OL2W")],
            tag_map={"OL1W": ["fiction"]},
        )
        # 1 insert books, 1 insert authors, 1 upsert tags, 1 attach tags
        assert execute_spy.call_count == 4


# ---------------------------------------------------------------------------
# upsert_single_manual_book
# ---------------------------------------------------------------------------


class TestUpsertSingleManualBook:
    def test_creates_book_from_book_data(self, session):
        data = make_book_data("my-manual-key", "A Manual Book")
        book = upsert_single_manual_book(data)
        assert book.book_ol_key == "my-manual-key"
        assert book.book_title == "A Manual Book"

    def test_returns_existing_book_without_creating_duplicate(self, session):
        existing = make_book(session, "my-manual-key", "Existing Book")
        result = upsert_single_manual_book(make_book_data("my-manual-key"))
        assert result.book_id == existing.book_id
        assert (
            session.query(Book).filter_by(book_ol_key="my-manual-key").count()
            == 1
        )

    def test_attaches_authors(self, session):
        data = make_book_data(
            "manual-key",
            authors=[AuthorData(name="Some Author", ol_id="some-author")],
        )
        book = upsert_single_manual_book(data)
        assert len(book.authors) == 1
        assert book.authors[0].author_name == "Some Author"


# ---------------------------------------------------------------------------
# upsert_post
# ---------------------------------------------------------------------------


class TestUpsertPost:
    def test_creates_new_post(self, session):
        _, is_new = upsert_post(
            slug="my-post",
            title="My Post",
            author="Aya",
            body="Some content.",
            post_parent_slug=None,
            post_type="standalone",
            post_rating=None,
            book=None,
        )
        assert is_new is True
        assert session.query(Post).filter_by(post_slug="my-post").count() == 1

    def test_updates_existing_post_by_slug(self, session):
        make_post(session, "existing", title="Old Title")
        _, is_new = upsert_post(
            slug="existing",
            title="New Title",
            author="Aya",
            body="updated body",
            post_parent_slug=None,
            post_type="standalone",
            post_rating=None,
            book=None,
        )
        assert is_new is False
        post = session.query(Post).filter_by(post_slug="existing").first()
        assert post.post_title == "New Title"

    def test_review_without_book_raises(self, session):
        with pytest.raises(ValueError, match="must have a book"):
            upsert_post(
                slug="review-no-book",
                title="Review",
                author="Aya",
                body="body",
                post_parent_slug=None,
                post_type="review",
                post_rating=4.0,
                book=None,
            )

    def test_non_review_with_rating_raises(self, session):
        with pytest.raises(ValueError, match="not a review"):
            upsert_post(
                slug="essay-with-rating",
                title="Essay",
                author="Aya",
                body="body",
                post_parent_slug=None,
                post_type="essay",
                post_rating=3.0,
                book=None,
            )

    def test_duplicate_review_for_same_book_raises(self, session):
        book = make_book(session)
        make_post(session, "first-review", post_type="review", book=book)
        with pytest.raises(ValueError, match="already has a review"):
            upsert_post(
                slug="second-review",
                title="Second Review",
                author="Aya",
                body="body",
                post_parent_slug=None,
                post_type="review",
                post_rating=None,
                book=book,
            )

    def test_review_sets_book_rating(self, session):
        book = make_book(session)
        upsert_post(
            slug="my-review",
            title="My Review",
            author="Aya",
            body="Great book.",
            post_parent_slug=None,
            post_type="review",
            post_rating=4.5,
            book=book,
        )
        session.flush()
        assert book.book_rating == 4.5

    def test_updated_at_changes_when_body_changes(self, session):
        post = make_post(session, "editable", body="original")
        original_updated_at = post.post_updated_at

        upsert_post(
            slug="editable",
            title="A Post",
            author="Aya",
            body="changed body",
            post_parent_slug=None,
            post_type="standalone",
            post_rating=None,
            book=None,
        )
        session.flush()
        assert post.post_updated_at > original_updated_at

    def test_updated_at_unchanged_when_body_same(self, session):
        post = make_post(session, "stable", body="same body")
        original_updated_at = post.post_updated_at

        upsert_post(
            slug="stable",
            title="A Post",
            author="Aya",
            body="same body",
            post_parent_slug=None,
            post_type="standalone",
            post_rating=None,
            book=None,
        )
        session.flush()
        assert post.post_updated_at == original_updated_at

    def test_quote_child_links_to_parent(self, session):
        make_post(session, "parent-post")
        upsert_post(
            slug="child-quote",
            title="Quote",
            author="Aya",
            body="A quoted passage.",
            post_parent_slug="parent-post",
            post_type="quotes",
            post_rating=None,
            book=None,
        )
        session.flush()
        child = session.query(Post).filter_by(post_slug="child-quote").first()
        parent = session.query(Post).filter_by(post_slug="parent-post").first()
        assert child.parent_id == parent.post_id


# ---------------------------------------------------------------------------
# attach_tags
# ---------------------------------------------------------------------------


class TestAttachTags:
    def test_adds_tags_to_book(self, session):
        book = make_book(session)
        attach_tags(book, ["history", "biography"])
        tag_names = {t.tag_name for t in book.tags}
        assert tag_names == {"history", "biography"}

    def test_does_not_duplicate_existing_tags(self, session):
        book = make_book(session)
        attach_tags(book, ["fiction"])
        attach_tags(book, ["fiction"])
        assert len(book.tags) == 1

    def test_empty_list_is_safe(self, session):
        book = make_book(session)
        attach_tags(book, [])
        assert book.tags == []
