"""Smoke tests for all Flask blueprint routes.

These tests verify that routes return the expected status codes and
content types. They use the client fixture (which shares the session
fixture's database state) so test data is immediately visible to routes.
"""

import json
from app.backend.models import Book, Poem, Quote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_book(session, ol_key="OL1W", title="Test Book", review_markdown=None):
    book = Book(
        book_ol_key=ol_key, book_title=title, review_markdown=review_markdown
    )
    session.add(book)
    session.flush()
    return book


def make_poem(session, slug, title="Test Poem", author="Aya", body="body"):
    poem = Poem(
        poem_slug=slug,
        poem_title=title,
        poem_body_markdown=body,
        poem_author=author,
    )
    session.add(poem)
    session.flush()
    return poem


def make_quote(session, slug, book, text="A fine passage."):
    quote = Quote(quote_slug=slug, quote_text=text, book=book)
    session.add(quote)
    session.flush()
    return quote


# ---------------------------------------------------------------------------
# Home / about
# ---------------------------------------------------------------------------


class TestHomeRoutes:
    def test_home_redirects_to_books(self, client):
        response = client.get("/")
        assert response.status_code == 302
        assert "/books" in response.headers["Location"]

    def test_about_returns_200(self, client):
        response = client.get("/about")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# /books
# ---------------------------------------------------------------------------


class TestBooksRoutes:
    def test_book_list_returns_200(self, client):
        response = client.get("/books/")
        assert response.status_code == 200

    def test_book_detail_returns_200_for_existing_book(self, client, session):
        book = make_book(session)
        response = client.get(f"/books/{book.book_id}")
        assert response.status_code == 200

    def test_book_detail_shows_book_title(self, client, session):
        book = make_book(session, title="Moby-Dick")
        response = client.get(f"/books/{book.book_id}")
        assert b"Moby-Dick" in response.data

    def test_book_detail_404_for_unknown_id(self, client):
        response = client.get("/books/99999")
        assert response.status_code == 404

    def test_book_detail_renders_review(self, client, session):
        book = make_book(session, review_markdown="Great read.")
        response = client.get(f"/books/{book.book_id}")
        assert b"Great read." in response.data

    def test_book_detail_renders_with_no_review(self, client, session):
        book = make_book(session, title="Unreviewed Book")
        response = client.get(f"/books/{book.book_id}")
        # Page should still load — not a 404
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# /poems
# ---------------------------------------------------------------------------


class TestPoemsRoutes:
    def test_poems_list_returns_200(self, client):
        response = client.get("/poems/")
        assert response.status_code == 200

    def test_poem_detail_returns_200(self, client, session):
        make_poem(session, "my-poem")
        response = client.get("/poems/my-poem")
        assert response.status_code == 200

    def test_poem_detail_404_for_unknown_slug(self, client):
        response = client.get("/poems/no-such-poem")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /random-quote
# ---------------------------------------------------------------------------


class TestRandomQuoteRoute:
    def test_returns_json(self, client):
        response = client.get("/random-quote")
        assert response.status_code == 200
        assert response.content_type.startswith("application/json")

    def test_returns_quote_html_and_source_keys(self, client):
        data = json.loads(client.get("/random-quote").data)
        assert "quote_html" in data
        assert "source" in data

    def test_empty_when_no_quotes(self, client):
        # No quotes in DB → both fields are empty strings
        data = json.loads(client.get("/random-quote").data)
        assert data["quote_html"] == ""
        assert data["source"] == ""

    def test_returns_quote_content_when_quotes_exist(self, client, session):
        book = make_book(session)
        make_quote(session, "q-abc123", book, text="A fine passage.")
        data = json.loads(client.get("/random-quote").data)
        assert data["quote_html"] != ""
