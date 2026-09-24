"""Render book/poem/about pages to static HTML using Jinja2."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from builder.content import Book, Poem
from builder.markdown import render_markdown_to_safe_html

NEW_POST_DAYS = 5


BOOKS_URL = "/books/"
POEMS_URL = "/poems/"
ABOUT_URL = "/about/"


def collect_quotes(books: list[Book]) -> list[dict]:
    """Return [{quote_html, book_title, book_url}] for every book's quotes."""
    quotes = []
    for book in books:
        for quote in book.quotes:
            quotes.append(
                {
                    "quote_html": render_markdown_to_safe_html(
                        quote.quote_text
                    ),
                    "book_title": book.book_title,
                    "book_url": f"/books/{book.book_id}/",
                }
            )
    return quotes


def create_environment(templates_dir: Path, quotes: list[dict]) -> Environment:
    """Create a standalone Jinja2 Environment for rendering templates."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["BOOKS_URL"] = BOOKS_URL
    env.globals["POEMS_URL"] = POEMS_URL
    env.globals["ABOUT_URL"] = ABOUT_URL
    env.globals["random_quote"] = bool(quotes)
    env.globals["random_quote_html"] = ""
    env.globals["random_quote_source"] = ""
    return env


def write_page(output_dir: Path, url_path: str, html: str) -> None:
    """Write rendered HTML to output_dir at the given url path.

    '/books/my-book/' is written to output_dir/books/my-book/index.html
    so links without a trailing filename resolve via directory indexes.
    """
    target = output_dir / url_path.strip("/") / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


def copy_static_assets(static_dir: Path, output_dir: Path) -> None:
    """Copy every file under static_dir into output_dir/static."""
    shutil.copytree(static_dir, output_dir / "static", dirs_exist_ok=True)


def find_books_with_reviews(books: list[Book]) -> set[str]:
    """Return book_ids that have a review."""
    return {b.book_id for b in books if b.review_markdown}


# --- Date policy -----------------------------------------------------
#
# The two questions the site asks about a book's dates are different,
# and this is the one place both are answered:
#   - display order: book_sort_date() -> when it was actually read
#   - "new" badge:    book_new_date()  -> earliest of read date / review
#                                          date, whichever happened first
# Tweak the policy here; everything else just calls these.


def _as_date(value: datetime | None) -> date | None:
    """Normalize a tz-aware datetime down to a plain date, or None."""
    return value.date() if value is not None else None


def book_sort_date(book: Book) -> date | None:
    """Date a book is ordered by: the day it was actually read."""
    return book.book_date_read


def book_new_date(book: Book) -> date | None:
    """Date a book counts as new by: earliest of read date or review date."""
    candidates = [
        d
        for d in (book.book_date_read, _as_date(book.review_created_at))
        if d is not None
    ]
    return min(candidates) if candidates else None


def _is_within(as_of: date | None, today: date, days: int) -> bool:
    """Whether as_of falls within the last `days` days of today."""
    return as_of is not None and (today - as_of).days <= days


def find_recently_reviewed_book_ids(
    books: list[Book], today: date
) -> set[str]:
    """Return book_ids that are "new" as of today (see book_new_date)."""
    return {
        b.book_id
        for b in books
        if _is_within(book_new_date(b), today, NEW_POST_DAYS)
    }


def find_recently_created_poem_ids(poems: list[Poem], today: date) -> set[str]:
    """Return poem_ids created within NEW_POST_DAYS of today."""
    return {
        p.poem_id
        for p in poems
        if _is_within(_as_date(p.poem_created_at), today, NEW_POST_DAYS)
    }


def _book_recency_sort_key(book: Book) -> tuple[int, int, str]:
    """Sort key for sort_books_by_recency: most-recently-read first.

    Books with no read date sort last, then alphabetically by title.
    """
    read_date = book_sort_date(book)
    if read_date is None:
        return (1, 0, book.book_title.lower())
    return (0, -read_date.toordinal(), book.book_title.lower())


def sort_books_by_recency(books: list[Book]) -> list[Book]:
    """Sort books by book_sort_date, most-recently-read first."""
    return sorted(books, key=_book_recency_sort_key)


def split_books_by_year(
    books: list[Book], year: int
) -> tuple[list[Book], list[Book]]:
    """Split books into (read this year, read previously/unread)."""
    this_year = [
        b for b in books if b.book_date_read and b.book_date_read.year == year
    ]
    previous = [
        b
        for b in books
        if not (b.book_date_read and b.book_date_read.year == year)
    ]
    return sort_books_by_recency(this_year), sort_books_by_recency(previous)


def render_book_list_page(
    env: Environment, books: list[Book], today: date
) -> str:
    """Render the /books/ list page."""
    books_this_year, books_previous = split_books_by_year(books, today.year)
    template = env.get_template("books.html")
    return template.render(
        books_current_year=books_this_year,
        books_previous=books_previous,
        current_year=today.year,
        has_posts=find_books_with_reviews(books),
        new_book_ids=find_recently_reviewed_book_ids(books, today),
    )


def render_book_detail_page(env: Environment, book: Book) -> str:
    """Render a single /books/<key>/ detail page."""
    review_html = (
        render_markdown_to_safe_html(book.review_markdown)
        if book.review_markdown
        else None
    )
    template = env.get_template("book_detail.html")
    return template.render(book=book, review_html=review_html)


def _poem_recency_sort_key(poem: Poem) -> datetime:
    """Sort key for render_poem_list_page: most-recently-created first."""
    return poem.poem_created_at or datetime.min.replace(tzinfo=timezone.utc)


def render_poem_list_page(
    env: Environment, poems: list[Poem], today: date | None = None
) -> str:
    """Render the /poems/ list page."""
    today = today or date.today()
    ordered = sorted(poems, key=_poem_recency_sort_key, reverse=True)
    template = env.get_template("poems.html")
    return template.render(
        poems=ordered,
        new_poem_ids=find_recently_created_poem_ids(poems, today),
    )


def render_poem_detail_page(env: Environment, poem: Poem) -> str:
    """Render a single /poems/<slug>/ detail page."""
    parts = poem.poem_body_markdown.split("\n---\n", 1)
    poem_html = render_markdown_to_safe_html(parts[0])
    comments_html = (
        render_markdown_to_safe_html(parts[1]) if len(parts) > 1 else None
    )
    template = env.get_template("poem_detail.html")
    return template.render(
        poem=poem, poem_html=poem_html, comments_html=comments_html
    )


def render_about_page(
    env: Environment, heatmap_cells: list[tuple[date, int, int]]
) -> str:
    """Render the /about/ page."""
    template = env.get_template("about.html")
    return template.render(heatmap_cells=heatmap_cells)
