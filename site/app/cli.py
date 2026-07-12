"""Application CLI commands."""

from __future__ import annotations

import json
import re
from pathlib import Path

import click
from flask.cli import with_appcontext

from app.backend.markdown import (
    MarkdownPost,
    parse_markdown_with_frontmatter,
)
from app.backend.models import Book
from app.backend.upserts import (
    sync_quotes_for_book,
    sync_tags,
    upsert_books,
    upsert_poem,
    upsert_review,
)
from app.backend.book_data import AuthorData, BookData
from app.extensions import cache, db

DEFAULT_SEED_PATH = Path(__file__).parents[3] / "writing" / "book_seed.json"
DEFAULT_POSTS_PATH = Path(__file__).parents[3] / "writing" / "posts"
REVIEWS_SUBDIR = "reviews"
POEMS_SUBDIR = "poetry"


def _slugify(text: str) -> str:
    """Derive a stable slug: lowercase, alphanumeric and hyphens only."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text)


def resolve_book(parsed: MarkdownPost) -> Book | None:
    """Return the Book for this post, or None if no book_key is set.

    The book must already exist in the database (seeded via book_seed.json).
    """
    key = parsed.book_key
    if not key:
        return None
    book = Book.query.filter_by(book_ol_key=key).first()
    if book is None:
        raise ValueError(
            f"Post '{parsed.slug}': book {key!r} not in database. "
            "Add it to book_seed.json and run 'make seed' first."
        )
    return book


def import_review_file(path: Path) -> bool:
    """Upsert a single review file. Returns True if the review is new."""
    parsed = parse_markdown_with_frontmatter(path)

    if not parsed.book_key:
        raise ValueError(f"Review '{parsed.slug}' has no book_key set.")

    book = resolve_book(parsed)

    _, is_new = upsert_review(
        book=book,
        body=parsed.body_markdown,
        created_at=parsed.date,
    )

    sync_quotes_for_book(book, parsed.quotes)

    return is_new


def import_poem_file(path: Path) -> bool:
    """Upsert a single poem file. Returns True if the poem is new."""
    parsed = parse_markdown_with_frontmatter(path)

    _, is_new = upsert_poem(
        slug=parsed.slug,
        title=parsed.title,
        author=parsed.author,
        body=parsed.body_markdown,
        created_at=parsed.date,
    )

    return is_new


def _import_files(md_files: list[Path], importer) -> tuple[int, int, int]:
    """Run importer over a list of paths, tallying results."""
    created = updated = errors = 0
    for path in md_files:
        try:
            if importer(path):
                created += 1
            else:
                updated += 1
        except (ValueError, TypeError) as exc:
            click.echo(f"ERROR: {exc}")
            errors += 1
    return created, updated, errors


@click.command("seed-books")
@click.option(
    "--path",
    "path_str",
    default=str(DEFAULT_SEED_PATH),
    show_default=True,
    help="Path to book seed JSON file.",
)
@with_appcontext
def seed_books_command(path_str: str) -> None:
    """Seed or update books from a JSON seed file.

    Each entry must have a 'key' and, for new books, a 'title'. All other
    metadata ('authors', 'publication_year', 'page_count', 'description')
    is optional and supplied directly in the seed entry.
    """
    seed_path = Path(path_str)
    if not seed_path.exists():
        raise click.ClickException(f"Seed file does not exist: {seed_path}")

    with open(seed_path, "r") as f:
        seeds: list[dict] = json.load(f)

    if not seeds:
        click.echo("Seed file is empty.")
        return

    created = updated = skipped = 0

    for s in seeds:
        key = s.get("key")
        if not key:
            click.echo(f"  WARNING: seed entry missing 'key', skipping: {s}")
            skipped += 1
            continue

        tags: list[str] = s.get("tags", [])
        rating: float | None = s.get("rating")
        title_override: str | None = s.get("title")
        description_override: str | None = s.get("description")

        existing = Book.query.filter_by(book_ol_key=key).first()
        if existing:
            if title_override:
                existing.book_title = title_override
            if description_override:
                existing.book_description = description_override
            if rating is not None:
                existing.book_rating = rating
            sync_tags(existing, tags)
            updated += 1
        else:
            title = title_override
            if not title:
                click.echo(
                    f"  WARNING: {key!r} not in DB and no title, skipping."
                )
                skipped += 1
                continue
            authors = [
                AuthorData(ol_id=_slugify(name), name=name)
                for name in s.get("authors", [])
            ]
            upsert_books(
                [
                    BookData(
                        ol_key=key,
                        title=title,
                        description=description_override,
                        publication_year=s.get("publication_year"),
                        page_count=s.get("page_count"),
                        authors=authors,
                    )
                ],
                tag_map={key: tags},
                rating_map={key: rating},
            )
            created += 1

    db.session.commit()
    cache.clear()
    click.echo(
        f"Seeded {len(seeds)} book(s): "
        f"{created} created, "
        f"{updated} updated, "
        f"{skipped} skipped."
    )


@click.command("reset-posts")
@click.option(
    "--path",
    "path_str",
    default=str(DEFAULT_POSTS_PATH),
    show_default=True,
    help="Directory containing 'reviews/' and 'poetry/' subdirectories.",
)
@with_appcontext
def reset_posts_command(path_str: str) -> None:
    """Clear all reviews, poems, and quotes, then re-import from --path.

    Books, authors, and tags are not touched.
    """
    from app.backend.models import Poem, Quote

    deleted_poems = Poem.query.delete()
    deleted_quotes = Quote.query.delete()
    for book in Book.query.filter(Book.review_markdown.isnot(None)).all():
        book.review_markdown = None
        book.review_created_at = None
        book.review_updated_at = None
    db.session.commit()
    click.echo(
        f"Cleared reviews, {deleted_poems} poem(s), "
        f"and {deleted_quotes} quote(s) from the database."
    )

    posts_dir = Path(path_str)
    if not posts_dir.exists():
        raise click.ClickException(f"Posts dir does not exist: {posts_dir}")

    reviews_dir = posts_dir / REVIEWS_SUBDIR
    poems_dir = posts_dir / POEMS_SUBDIR

    review_files = (
        sorted(p for p in reviews_dir.rglob("*.md") if p.is_file())
        if reviews_dir.exists()
        else []
    )
    poem_files = (
        sorted(p for p in poems_dir.rglob("*.md") if p.is_file())
        if poems_dir.exists()
        else []
    )

    r_created, r_updated, r_errors = _import_files(
        review_files, import_review_file
    )
    p_created, p_updated, p_errors = _import_files(
        poem_files, import_poem_file
    )
    db.session.commit()
    click.echo(
        f"Reviews from {reviews_dir}: "
        f"created={r_created}, updated={r_updated}, errors={r_errors}"
    )
    click.echo(
        f"Poems from {poems_dir}: "
        f"created={p_created}, updated={p_updated}, errors={p_errors}"
    )
    cache.clear()
    click.echo("Cache cleared.")


def init_app(app) -> None:
    """Register CLI commands with the Flask app."""
    app.cli.add_command(seed_books_command)
    app.cli.add_command(reset_posts_command)
