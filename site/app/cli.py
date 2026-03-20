"""Application CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click
from flask.cli import with_appcontext

from content.markdown_posts import (
    MarkdownPost,
    parse_markdown_with_frontmatter,
)
from content.extract_quotes import Quote
from app.database.models import Book, Post
from app.database.upserts import (
    attach_tags,
    upsert_books,
    upsert_post,
    upsert_single_book,
)
from app.open_library import fetch_book_data
from app.extensions import cache, db

DEFAULT_SEED_PATH = (
    Path(__file__).parents[1] / "content" / "seeds" / "book_seed.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_book(parsed: MarkdownPost) -> Book | None:
    """Return the Book for the post's book_ol_key, fetching from OL if
    needed. Returns None for posts with no book_ol_key."""
    if parsed.book_ol_key is None:
        return None
    return upsert_single_book(parsed.book_ol_key)


def sync_quotes(
    *,
    quotes: list[Quote],
    author: str,
    book: Book | None,
) -> tuple[int, int]:
    """Upsert quote posts from a parsed markdown file.

    Quotes whose slug is no longer present in the current set are deleted.
    Returns (created_count, updated_count).
    """
    current_slugs: set[str] = set()
    created = updated = 0

    for quote in quotes:
        current_slugs.add(quote.quote_slug)
        _, is_new = upsert_post(
            slug=quote.quote_slug,
            title=f"Quote ({quote.quote_slug})",
            author=author,
            body=quote.quote_text,
            post_type="quotes",
            post_rating=None,
            book=book,
        )
        if is_new:
            created += 1
        else:
            updated += 1

    if current_slugs:
        stale = Post.query.filter(
            Post.post_type == "quotes",
            Post.post_slug.like("quote-%"),
            Post.post_slug.notin_(current_slugs),
        ).all()
        for post in stale:
            db.session.delete(post)

    return created, updated


# ---------------------------------------------------------------------------
# Post importer
# ---------------------------------------------------------------------------


def import_post_file(path: Path) -> bool:
    """Parse and upsert a single markdown post file.

    Validation is handled by MarkdownPost.__post_init__ and its properties —
    ValueError/TypeError raised there are caught and re-raised as
    ClickException so the CLI reports them cleanly.

    Returns True if the post was newly created, False if updated.
    """
    try:
        parsed = parse_markdown_with_frontmatter(path)
        post_rating = parsed.rating if parsed.post_type == "review" else None
    except (ValueError, TypeError) as exc:
        raise click.ClickException(str(exc))

    if parsed.post_type in {"review", "essay"} and not parsed.book_ol_key:
        click.echo(
            f"WARNING {path.name}: type={parsed.post_type!r} "
            "but no book_ol_key set. Post will be created as standalone."
        )

    book = resolve_book(parsed)

    _, is_new = upsert_post(
        slug=parsed.slug,
        title=parsed.title,
        author=parsed.author,
        body=parsed.body_markdown,
        post_type=parsed.post_type,
        post_rating=post_rating,
        book=book,
    )

    if book is not None:
        attach_tags(book, parsed.tags)

    sync_quotes(quotes=parsed.quotes, author=parsed.author, book=book)

    return is_new


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.command("import-posts")
@click.option(
    "--path",
    "path_str",
    required=True,
    help="Directory of markdown posts.",
)
@with_appcontext
def import_posts_command(path_str: str) -> None:
    """Import or update all markdown posts found under --path."""
    posts_dir = Path(path_str)
    if not posts_dir.exists():
        raise click.ClickException(f"Posts dir does not exist: {posts_dir}")

    md_files = sorted(p for p in posts_dir.rglob("*.md") if p.is_file())
    if not md_files:
        click.echo(f"No markdown files found under {posts_dir}")
        return

    created = updated = errors = 0
    for path in md_files:
        try:
            is_new = import_post_file(path)
            if is_new:
                created += 1
            else:
                updated += 1
        except click.ClickException as exc:
            click.echo(f"ERROR: {exc.format_message()}")
            errors += 1

    db.session.commit()
    click.echo(
        f"Imported posts from {posts_dir}: "
        f"created={created}, updated={updated}, errors={errors}"
    )
    cache.clear()
    click.echo("Cache cleared.")


@click.command("seed-books")
@click.option(
    "--path",
    "path_str",
    default=str(DEFAULT_SEED_PATH),
    show_default=True,
    help="Path to book seed JSON file.",
)
@click.option(
    "--refresh",
    is_flag=True,
    default=False,
    help=(
        "Re-fetch metadata from Open Library for books already in the DB. "
        "Without this flag, existing books are not re-fetched but tags and "
        "description overrides from the seed file are still applied."
    ),
)
@with_appcontext
def seed_books_command(path_str: str, refresh: bool) -> None:
    """Seed or update books from a JSON seed file."""
    seed_path = Path(path_str)
    if not seed_path.exists():
        raise click.ClickException(f"Seed file does not exist: {seed_path}")

    with open(seed_path, "r") as f:
        seeds: list[dict] = json.load(f)

    if not seeds:
        click.echo("Seed file is empty.")
        return

    ol_keys = [s["olid"] for s in seeds]
    tag_map = {s["olid"]: s.get("tags", []) for s in seeds}
    description_overrides = {
        s["olid"]: s["description"] for s in seeds if "description" in s
    }

    if refresh:
        keys_to_fetch = ol_keys
    else:
        existing_keys = {
            b.book_ol_key
            for b in Book.query.filter(Book.book_ol_key.in_(ol_keys)).all()
        }
        keys_to_fetch = [k for k in ol_keys if k not in existing_keys]

    click.echo(
        f"Fetching {len(keys_to_fetch)} book(s) from Open Library "
        f"({len(ol_keys) - len(keys_to_fetch)} already in DB)."
    )

    book_datas = []
    for ol_key in keys_to_fetch:
        click.echo(f"  Fetching {ol_key}...")
        try:
            book_datas.append(fetch_book_data(ol_key))
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  WARNING: could not fetch {ol_key}: {exc}")

    upsert_books(
        book_datas,
        tag_map=tag_map,
        description_overrides=description_overrides,
    )

    # For books already in the DB (not re-fetched), still apply tag and
    # description overrides from the seed file
    if not refresh and existing_keys:
        existing_books = {
            b.book_ol_key: b
            for b in Book.query.filter(
                Book.book_ol_key.in_(existing_keys)
            ).all()
        }
        for ol_key, book in existing_books.items():
            if ol_key in description_overrides:
                book.book_description = description_overrides[ol_key]
            attach_tags(book, tag_map.get(ol_key, []))

    db.session.commit()
    click.echo(
        f"Seeded {len(seeds)} book(s): "
        f"{len(keys_to_fetch)} fetched from Open Library, "
        f"{len(ol_keys) - len(keys_to_fetch)} updated from seed file."
    )


def init_app(app) -> None:
    """Register CLI commands with the Flask app."""
    app.cli.add_command(import_posts_command)
    app.cli.add_command(seed_books_command)
