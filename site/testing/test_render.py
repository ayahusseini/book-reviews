"""Tests for builder.render."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from builder.content import Author, Book, Poem, Tag
from builder.render import (
    collect_quotes,
    copy_static_assets,
    create_environment,
    find_books_with_reviews,
    find_recently_reviewed_book_ids,
    render_about_page,
    render_book_detail_page,
    render_book_list_page,
    render_poem_detail_page,
    render_poem_list_page,
    resolve_url,
    split_books_by_year,
    write_page,
)

TEMPLATES_DIR = Path(__file__).parents[1] / "templates"
STATIC_DIR = Path(__file__).parents[1] / "static"


def make_book(**overrides) -> Book:
    defaults = dict(
        book_id="k",
        book_title="Title",
        book_description=None,
        book_publication_year=None,
        book_page_count=None,
        book_rating=None,
        book_date_read=None,
    )
    defaults.update(overrides)
    return Book(**defaults)


class TestResolveUrl:
    def test_static_endpoint(self):
        assert resolve_url("static", filename="style/style.css") == (
            "/static/style/style.css"
        )

    def test_book_detail_endpoint(self):
        assert resolve_url("books.book_detail", book_id="orbital") == (
            "/books/orbital/"
        )

    def test_unknown_endpoint_raises(self):
        with pytest.raises(ValueError):
            resolve_url("nonsense.endpoint")


class TestSplitBooksByYear:
    def test_splits_by_date_read_year(self):
        this_year = make_book(book_id="a", book_date_read=date(2026, 1, 1))
        last_year = make_book(book_id="b", book_date_read=date(2025, 1, 1))
        unread = make_book(book_id="c", book_date_read=None)

        current, previous = split_books_by_year(
            [this_year, last_year, unread], year=2026
        )

        assert current == [this_year]
        assert {b.book_id for b in previous} == {"b", "c"}


class TestFindBooksWithReviews:
    def test_only_includes_books_with_review_markdown(self):
        reviewed = make_book(book_id="a", review_markdown="text")
        unreviewed = make_book(book_id="b", review_markdown=None)

        assert find_books_with_reviews([reviewed, unreviewed]) == {"a"}


class TestFindRecentlyReviewedBookIds:
    def test_includes_recent_review(self):
        recent = make_book(
            book_id="a", review_created_at=datetime.now(timezone.utc)
        )
        old = make_book(
            book_id="b",
            review_created_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        )

        assert find_recently_reviewed_book_ids([recent, old]) == {"a"}


class TestCollectQuotes:
    def test_collects_quote_with_book_link(self):
        from builder.extract_quotes import ExtractedQuote

        book = make_book(
            book_id="orbital",
            book_title="Orbital",
            quotes=[ExtractedQuote(quote_text="A striking line.")],
        )

        quotes = collect_quotes([book])

        assert len(quotes) == 1
        assert quotes[0]["book_title"] == "Orbital"
        assert quotes[0]["book_url"] == "/books/orbital/"
        assert "striking line" in quotes[0]["quote_html"]


class TestWritePage:
    def test_writes_index_html_under_url_path(self, tmp_path):
        write_page(tmp_path, "/books/orbital/", "<h1>Orbital</h1>")

        written = tmp_path / "books" / "orbital" / "index.html"
        assert written.read_text() == "<h1>Orbital</h1>"


class TestCopyStaticAssets:
    def test_copies_static_dir_contents(self, tmp_path):
        copy_static_assets(STATIC_DIR, tmp_path)

        assert (tmp_path / "static" / "style" / "style.css").exists()


class TestRenderPages:
    def test_render_book_list_page_includes_reviewed_title(self):
        book = make_book(
            book_id="orbital",
            book_title="Orbital",
            review_markdown="text",
            review_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            book_date_read=date(2026, 6, 1),
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_book_list_page(env, [book], today=date(2026, 6, 1))

        assert "Orbital" in html
        assert '/books/orbital/"' in html
        assert "<h3>2026</h3>" in html

    def test_render_book_detail_page_renders_review_markdown(self):
        book = make_book(
            book_id="orbital",
            book_title="Orbital",
            authors=[Author(author_name="Samantha Harvey")],
            tags=[Tag(tag_name="fiction")],
            review_markdown="**Loved it.**",
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_book_detail_page(env, book)

        assert "Orbital" in html
        assert "Samantha Harvey" in html
        assert "<strong>Loved it.</strong>" in html

    def test_render_poem_list_page_links_to_poem(self):
        poem = Poem(
            poem_id="fire-and-ice",
            poem_slug="fire-and-ice",
            poem_title="Fire and Ice",
            poem_author="Robert Frost",
            poem_body_markdown="Some say the world will end in fire.",
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_poem_list_page(env, [poem])

        assert '/poems/fire-and-ice/"' in html

    def test_render_poem_detail_page_splits_comments_section(self):
        poem = Poem(
            poem_id="p",
            poem_slug="p",
            poem_title="P",
            poem_author="A",
            poem_body_markdown="The poem.\n\n---\n\nA note about it.",
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_poem_detail_page(env, poem)

        assert "The poem." in html
        assert "A note about it." in html

    def test_render_about_page_includes_heatmap_grid(self):
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_about_page(env, heatmap_cells=[(date.today(), 1, 1)])

        assert "post-heatmap__grid" in html
