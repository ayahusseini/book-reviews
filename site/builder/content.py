"""Load book and poem content from writing/ into plain data objects."""

from __future__ import annotations

import json
import re
import unicodedata
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
    poem_title: str
    poem_author: str
    poem_body_markdown: str
    poem_created_at: datetime | None = None


def slugify(text: str) -> str:
    """Lowercase, strip accents, and collapse everything else to '_'."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def generate_id(title: str, authors: list[str]) -> str:
    """Generate a stable id from a title and its author name(s)."""
    parts = [slugify(title)] + [slugify(author) for author in authors]
    id_ = "_".join(part for part in parts if part)
    if not id_:
        raise ValueError(
            f"Could not generate an id from title {title!r} and authors "
            f"{authors!r} — they contain no ASCII letters or digits."
        )
    return id_


def parse_date_read(value: object) -> date | None:
    """Parse an ISO date string from a seed entry, or return None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"date_read must be an ISO date string or null, got {value!r}"
        )
    return date.fromisoformat(value)


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
    title = entry.get("title")
    if not title:
        raise ValueError(f"Seed entry missing required 'title': {entry}")
    authors = entry.get("authors") or []

    return Book(
        book_id=generate_id(title, authors),
        book_title=title,
        book_description=entry.get("description"),
        book_publication_year=entry.get("publication_year"),
        book_page_count=entry.get("page_count"),
        book_rating=entry.get("rating"),
        book_date_read=parse_date_read(entry.get("date_read")),
        authors=[Author(author_name=name) for name in authors],
        tags=[Tag(tag_name=name) for name in entry.get("tags", [])],
        review_markdown=review.body_markdown if review else None,
        review_created_at=review.date if review else None,
        quotes=review.quotes if review else [],
    )


def load_books(seed_path: Path, reviews_dir: Path) -> list[Book]:
    """Load all books, joining book_seed.json entries with their reviews."""
    reviews = load_reviews(reviews_dir)

    with open(seed_path) as f:
        seed = json.load(f)

    book_ids = [build_book(entry, None).book_id for entry in seed]
    dupes = sorted({i for i in book_ids if book_ids.count(i) > 1})
    if dupes:
        raise ValueError(
            f"Duplicate book id(s) generated from title+authors: {dupes}. "
            "Book titles/authors must be unique across book_seed.json."
        )

    unmatched = set(reviews) - set(book_ids)
    if unmatched:
        raise ValueError(
            f"""Review(s) reference unknown book_key(s):
            {sorted(unmatched)}.
            Add them to book_seed.json first."""
        )

    return [
        build_book(entry, reviews.get(book_id))
        for entry, book_id in zip(seed, book_ids)
    ]


def build_poem(post: MarkdownPost) -> Poem:
    """Build a Poem from a parsed poem markdown file."""
    poem_id = generate_id(post.title, [post.author])
    return Poem(
        poem_id=poem_id,
        poem_title=post.title,
        poem_author=post.author,
        poem_body_markdown=post.body_markdown,
        poem_created_at=post.date,
    )


def load_poems(poems_dir: Path) -> list[Poem]:
    """Load all poems from poems_dir, one per markdown file.

    Each poem's id is generated from its title and author, so two poem
    files that resolve to the same title/author raise an error instead
    of one silently overwriting the other.
    """
    if not poems_dir.exists():
        return []
    poems: list[Poem] = []
    seen_ids: set[str] = set()
    for path in sorted(poems_dir.rglob("*.md")):
        poem = build_poem(parse_markdown_with_frontmatter(path))
        if poem.poem_id in seen_ids:
            raise ValueError(
                f"Duplicate poem id {poem.poem_id!r} generated from "
                f"{path} — poem title/author combinations must be unique."
            )
        seen_ids.add(poem.poem_id)
        poems.append(poem)
    return poems
