"""Tests for site/app/database/upserts.py.

Each test focuses on one behaviour. Database state is rolled back after
every test via the session fixture, so tests are fully isolated.
"""

from datetime import datetime, timezone

from app.backend.extract_quotes import ExtractedQuote
from app.backend.models import Book, Poem, Quote, Tag
from app.backend.upserts import (
    sync_quotes_for_book,
    upsert_books,
    upsert_poem,
    upsert_review,
    upsert_tags,
)
from app.backend.book_data import AuthorData, BookData


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


def make_poem(session, slug, **kwargs):
    poem = Poem(
        poem_slug=slug,
        poem_title=kwargs.get("title", "A Poem"),
        poem_body_markdown=kwargs.get("body", "body text"),
        poem_author=kwargs.get("author", "Aya"),
    )
    session.add(poem)
    session.flush()
    return poem


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
# upsert_review
# ---------------------------------------------------------------------------


class TestUpsertReview:
    def test_creates_new_review(self, session):
        book = make_book(session)
        _, is_new = upsert_review(book=book, body="Some content.")
        assert is_new is True
        assert book.review_markdown == "Some content."

    def test_updates_existing_review(self, session):
        book = make_book(session)
        upsert_review(book=book, body="Old review.")
        _, is_new = upsert_review(book=book, body="New review.")
        assert is_new is False
        assert book.review_markdown == "New review."

    def test_created_at_set_only_once(self, session):
        book = make_book(session)
        first = datetime(2026, 1, 1, tzinfo=timezone.utc)
        second = datetime(2026, 2, 1, tzinfo=timezone.utc)
        upsert_review(book=book, body="v1", created_at=first)
        upsert_review(book=book, body="v2", created_at=second)
        assert book.review_created_at == first

    def test_updated_at_changes_when_body_changes(self, session):
        book = make_book(session)
        upsert_review(book=book, body="original")
        original_updated_at = book.review_updated_at

        upsert_review(book=book, body="changed body")
        session.flush()
        assert book.review_updated_at > original_updated_at

    def test_updated_at_unchanged_when_body_same(self, session):
        book = make_book(session)
        upsert_review(book=book, body="same body")
        original_updated_at = book.review_updated_at

        upsert_review(book=book, body="same body")
        session.flush()
        assert book.review_updated_at == original_updated_at


# ---------------------------------------------------------------------------
# upsert_poem
# ---------------------------------------------------------------------------


class TestUpsertPoem:
    def test_creates_new_poem(self, session):
        _, is_new = upsert_poem(
            slug="my-poem", title="My Poem", author="Aya", body="line one"
        )
        assert is_new is True
        assert session.query(Poem).filter_by(poem_slug="my-poem").count() == 1

    def test_updates_existing_poem_by_slug(self, session):
        make_poem(session, "existing", title="Old Title")
        _, is_new = upsert_poem(
            slug="existing", title="New Title", author="Aya", body="updated"
        )
        assert is_new is False
        poem = session.query(Poem).filter_by(poem_slug="existing").first()
        assert poem.poem_title == "New Title"

    def test_updated_at_changes_when_body_changes(self, session):
        poem = make_poem(session, "editable", body="original")
        original_updated_at = poem.poem_updated_at

        upsert_poem(
            slug="editable", title="A Poem", author="Aya", body="changed body"
        )
        session.flush()
        assert poem.poem_updated_at > original_updated_at

    def test_updated_at_unchanged_when_body_same(self, session):
        poem = make_poem(session, "stable", body="same body")
        original_updated_at = poem.poem_updated_at

        upsert_poem(
            slug="stable", title="A Poem", author="Aya", body="same body"
        )
        session.flush()
        assert poem.poem_updated_at == original_updated_at


# ---------------------------------------------------------------------------
# sync_quotes_for_book
# ---------------------------------------------------------------------------


class TestSyncQuotesForBook:
    def test_creates_quote_linked_to_book(self, session):
        book = make_book(session)
        sync_quotes_for_book(
            book, [ExtractedQuote(quote_text="A quoted passage.")]
        )
        session.flush()
        quote = session.query(Quote).first()
        assert quote is not None
        assert quote.book_id == book.book_id
        assert quote.quote_text == "A quoted passage."

    def test_updates_existing_quote_text_for_same_slug(self, session):
        # quote_slug is derived from the first 100 chars of the text, so
        # a 100-char-identical prefix with a different suffix maps to the
        # same slug — this exercises the update-in-place path.
        prefix = "A" * 100
        book = make_book(session)
        sync_quotes_for_book(book, [ExtractedQuote(quote_text=prefix)])
        session.flush()

        sync_quotes_for_book(
            book, [ExtractedQuote(quote_text=prefix + " extended")]
        )
        session.flush()

        assert session.query(Quote).count() == 1
        quote = session.query(Quote).first()
        assert quote.quote_text == prefix + " extended"
