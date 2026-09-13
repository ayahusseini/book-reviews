"""Load book and poem content from writing/ into plain data objects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from builder.extract_quotes import ExtractedQuote
from builder.markdown import MarkdownPost, parse_markdown_with_frontmatter


@dataclass
class Author:
    """A book author, as listed in book_seed.json."""

    author_name: str


@dataclass
class Tag:
    """A tag attached to a book, as listed in book_seed.json."""

    tag_name: str


@dataclass
class Book:
    """A book, joining its book_seed.json entry with its review file."""

    book_id: str
    book_title: str
    book_description: str | None
    book_publication_year: int | None
    book_page_count: int | None
    book_rating: float | None
    book_date_read: date | None
    authors: list[Author] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    review_markdown: str | None = None
    review_created_at: datetime | None = None
    quotes: list[ExtractedQuote] = field(default_factory=list)


@dataclass
class Poem:
    """A poem, parsed from a single markdown file."""

    poem_id: str
    poem_slug: str
    poem_title: str
    poem_author: str
    poem_body_markdown: str
    poem_created_at: datetime | None = None


def parse_date_read(value: object) -> date | None:
    """Parse an ISO date string from a seed entry, or return None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"date_read must be an ISO date string or null, got {value!r}"
        )
    return date.fromisoformat(value)


def load_book_seed(seed_path: Path) -> list[dict]:
    """Load and return the raw list of book entries from book_seed.json."""
    with open(seed_path) as f:
        return json.load(f)


def load_reviews(reviews_dir: Path) -> dict[str, MarkdownPost]:
    """Return {book_key: MarkdownPost} for every review under reviews_dir."""
    if not reviews_dir.exists():
        return {}
    reviews: dict[str, MarkdownPost] = {}
    for path in sorted(reviews_dir.rglob("*.md")):
        post = parse_markdown_with_frontmatter(path)
        if not post.book_key:
            raise ValueError(f"Review '{path}' has no book_key set.")
        reviews[post.book_key] = post
    return reviews


def build_book(entry: dict, review: MarkdownPost | None) -> Book:
    """Build a Book from one book_seed.json entry and its matching review."""
    key = entry.get("key")
    if not key:
        raise ValueError(f"Seed entry missing 'key': {entry}")
    title = entry.get("title")
    if not title:
        raise ValueError(f"Seed entry {key!r} missing required 'title'")

    return Book(
        book_id=key,
        book_title=title,
        book_description=entry.get("description"),
        book_publication_year=entry.get("publication_year"),
        book_page_count=entry.get("page_count"),
        book_rating=entry.get("rating"),
        book_date_read=parse_date_read(entry.get("date_read")),
        authors=[
            Author(author_name=name) for name in entry.get("authors", [])
        ],
        tags=[Tag(tag_name=name) for name in entry.get("tags", [])],
        review_markdown=review.body_markdown if review else None,
        review_created_at=review.date if review else None,
        quotes=review.quotes if review else [],
    )


def load_books(seed_path: Path, reviews_dir: Path) -> list[Book]:
    """Load all books, joining book_seed.json entries with their reviews."""
    reviews = load_reviews(reviews_dir)
    seed_keys = {entry.get("key") for entry in load_book_seed(seed_path)}

    unmatched = set(reviews) - seed_keys
    if unmatched:
        raise ValueError(
            f"Review(s) reference unknown book_key(s): {sorted(unmatched)}. "
            "Add them to book_seed.json first."
        )

    return [
        build_book(entry, reviews.get(entry.get("key")))
        for entry in load_book_seed(seed_path)
    ]


def build_poem(post: MarkdownPost) -> Poem:
    """Build a Poem from a parsed poem markdown file."""
    return Poem(
        poem_id=post.slug,
        poem_slug=post.slug,
        poem_title=post.title,
        poem_author=post.author,
        poem_body_markdown=post.body_markdown,
        poem_created_at=post.date,
    )


def load_poems(poems_dir: Path) -> list[Poem]:
    """Load all poems from poems_dir, one per markdown file.

    If two files produce the same slug, the one that sorts last by
    filename wins — matching the "last import wins" behavior documented
    in docs/writing-posts.md.
    """
    if not poems_dir.exists():
        return []
    poems_by_slug: dict[str, Poem] = {}
    for path in sorted(poems_dir.rglob("*.md")):
        poem = build_poem(parse_markdown_with_frontmatter(path))
        poems_by_slug[poem.poem_slug] = poem
    return list(poems_by_slug.values())
