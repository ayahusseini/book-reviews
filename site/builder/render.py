"""Render book/poem/about pages to static HTML using Jinja2."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from builder.content import Book, Poem
from builder.markdown import render_markdown_to_safe_html

NEW_POST_DAYS = 5


def resolve_url(endpoint: str, **kwargs: str) -> str:
    """Map a Flask-style endpoint name to a static site path.

    Registered under the name 'url_for' in the Jinja environment so the
    templates (written against Flask's url_for) need no changes.
    """
    if endpoint == "static":
        return f"/static/{kwargs['filename']}"
    if endpoint == "books.book_list":
        return "/books/"
    if endpoint == "books.book_detail":
        return f"/books/{kwargs['book_id']}/"
    if endpoint == "homepage.about":
        return "/about/"
    if endpoint == "poems.poem_list":
        return "/poems/"
    if endpoint == "poems.poem_detail":
        return f"/poems/{kwargs['slug']}/"
    raise ValueError(f"Unknown endpoint for static site: {endpoint}")


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
                    "book_url": resolve_url(
                        "books.book_detail", book_id=book.book_id
                    ),
                }
            )
    return quotes


def create_environment(templates_dir: Path, quotes: list[dict]) -> Environment:
    """Create a standalone Jinja2 Environment for rendering templates."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["url_for"] = resolve_url
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


def find_recently_reviewed_book_ids(books: list[Book]) -> set[str]:
    """Return book_ids whose review was created within NEW_POST_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return {
        b.book_id
        for b in books
        if b.review_created_at and b.review_created_at >= cutoff
    }


def find_recently_created_poem_ids(poems: list[Poem]) -> set[str]:
    """Return poem_ids created within NEW_POST_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return {
        p.poem_id
        for p in poems
        if p.poem_created_at and p.poem_created_at >= cutoff
    }


def sort_books_by_recency(books: list[Book]) -> list[Book]:
    """Sort books: reviewed most-recent-first, unreviewed last, by title."""

    def sort_key(book: Book) -> tuple[int, float, str]:
        if book.review_created_at is None:
            return (1, 0.0, book.book_title.lower())
        return (
            0,
            -book.review_created_at.timestamp(),
            book.book_title.lower(),
        )

    return sorted(books, key=sort_key)


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
        books_2026=books_this_year,
        books_previous=books_previous,
        has_posts=find_books_with_reviews(books),
        new_book_ids=find_recently_reviewed_book_ids(books),
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


def render_poem_list_page(env: Environment, poems: list[Poem]) -> str:
    """Render the /poems/ list page."""
    ordered = sorted(
        poems,
        key=lambda p: (
            p.poem_created_at or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    template = env.get_template("poems.html")
    return template.render(
        poems=ordered, new_poem_ids=find_recently_created_poem_ids(poems)
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
