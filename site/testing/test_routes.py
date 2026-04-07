"""Smoke tests for all Flask blueprint routes.

These tests verify that routes return the expected status codes and
content types. They use the client fixture (which shares the session
fixture's database state) so test data is immediately visible to routes.
"""

import json
import pytest
from app.database.models import Book, Post


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_book(session, ol_key="OL1W", title="Test Book"):
    book = Book(book_ol_key=ol_key, book_title=title)
    session.add(book)
    session.flush()
    return book


def make_post(session, slug, post_type="standalone", book=None, body="body"):
    post = Post(
        post_slug=slug,
        post_title="Test Post",
        post_body_markdown=body,
        post_type=post_type,
        post_author="Aya",
        book=book,
    )
    session.add(post)
    session.flush()
    return post


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

    def test_book_detail_renders_posts(self, client, session):
        book = make_book(session)
        make_post(
            session,
            "my-review",
            post_type="review",
            book=book,
            body="Great read.",
        )
        response = client.get(f"/books/{book.book_id}")
        assert b"Great read." in response.data

    def test_book_detail_renders_with_no_posts(self, client, session):
        book = make_book(session, title="Unreviewed Book")
        response = client.get(f"/books/{book.book_id}")
        # Page should still load — not a 404
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# /posts
# ---------------------------------------------------------------------------


class TestPostsRoutes:
    def test_post_list_returns_200(self, client):
        response = client.get("/posts/")
        assert response.status_code == 200

    def test_misc_post_list_returns_200(self, client):
        response = client.get("/posts/misc_posts")
        assert response.status_code == 200

    def test_post_detail_returns_200_for_existing_post(self, client, session):
        make_post(session, "my-standalone")
        response = client.get("/posts/my-standalone")
        assert response.status_code == 200

    def test_post_detail_shows_post_title(self, client, session):
        post = make_post(session, "titled-post")
        response = client.get(f"/posts/{post.post_slug}")
        assert b"Test Post" in response.data

    def test_post_detail_404_for_unknown_slug(self, client):
        response = client.get("/posts/does-not-exist")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /posts — code type
# ---------------------------------------------------------------------------


class TestCodePostRoutes:
    def test_code_post_accessible_by_slug_with_dot(self, client, session):
        make_post(session, "demo.sql", post_type="code")
        response = client.get("/posts/demo.sql")
        assert response.status_code == 200

    def test_code_post_excluded_from_post_list(self, client, session):
        make_post(session, "demo.sql", post_type="code")
        response = client.get("/posts/")
        assert b"demo.sql" not in response.data

    def test_code_post_excluded_from_misc_post_list(self, client, session):
        make_post(session, "demo.sql", post_type="code")
        response = client.get("/posts/misc_posts")
        assert b"demo.sql" not in response.data

    def test_code_post_has_copy_button(self, client, session):
        make_post(
            session,
            "demo.sql",
            post_type="code",
            body="```sql\nSELECT 1;\n```",
        )
        response = client.get("/posts/demo.sql")
        assert b"copy-btn" in response.data

    def test_code_post_has_no_back_link(self, client, session):
        make_post(session, "demo.sql", post_type="code")
        response = client.get("/posts/demo.sql")
        assert b"Back to posts" not in response.data

    def test_non_code_post_has_back_link(self, client, session):
        make_post(session, "regular-post", post_type="standalone")
        response = client.get("/posts/regular-post")
        assert b"Back to posts" in response.data

    def test_standalone_post_visible_in_post_list(self, client, session):
        make_post(session, "regular-post", post_type="standalone")
        response = client.get("/posts/")
        assert b"regular-post" in response.data


# ---------------------------------------------------------------------------
# /poems
# ---------------------------------------------------------------------------


class TestPoemsRoutes:
    def test_poems_list_returns_200(self, client):
        response = client.get("/poems/")
        assert response.status_code == 200

    def test_poem_detail_returns_200(self, client, session):
        make_post(session, "my-poem", post_type="poem")
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
        make_post(
            session, "q-abc123", post_type="quotes", body="A fine passage."
        )
        data = json.loads(client.get("/random-quote").data)
        assert data["quote_html"] != ""
