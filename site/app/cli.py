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
from app.backend.extract_quotes import Quote
from app.backend.models import Book
from app.backend.upserts import (
    sync_tags,
    upsert_books,
    upsert_post,
)
from app.backend.open_library import AuthorData, BookData, fetch_book_data
from app.extensions import cache, db

DEFAULT_SEED_PATH = Path(__file__).parents[3] / "writing" / "book_seed.json"


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


def sync_quotes(
    *,
    quotes: list[Quote],
    author: str,
    book: Book | None,
    parent_slug: str | None,
) -> tuple[int, int]:
    created = updated = 0

    for quote in quotes:
        _, is_new = upsert_post(
            slug=quote.quote_slug,
            title=f"Quote ({quote.quote_slug})",
            author=author,
            body=quote.quote_text,
            post_parent_slug=parent_slug,
            post_type="quotes",
            book=book,
        )

        if is_new:
            created += 1
        else:
            updated += 1

    return created, updated


def import_post_file(path: Path) -> bool:
    """Upsert a single post file. Returns True if the post is new."""
    parsed = parse_markdown_with_frontmatter(path)

    if parsed.post_type in {"review", "essay"} and not parsed.book_key:
        click.echo(
            f"WARNING {path.name}: type={parsed.post_type!r} "
            "but no book_key set. Standalone post."
        )

    book = resolve_book(parsed)

    _, is_new = upsert_post(
        slug=parsed.slug,
        title=parsed.title,
        author=parsed.author,
        post_parent_slug=parsed.parent_slug,
        body=parsed.body_markdown,
        post_type=parsed.post_type,
        book=book,
        created_at=parsed.date,
    )

    sync_quotes(
        quotes=parsed.quotes,
        author=parsed.author,
        book=book,
        parent_slug=parsed.slug,
    )

    return is_new


def _import_files(md_files: list[Path]) -> tuple[int, int, int]:
    """Run import_post_file over a list of paths, tallying results."""
    created = updated = errors = 0
    for path in md_files:
        try:
            if import_post_file(path):
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

    Each entry must have a 'key' field. Set 'enrich': true on an entry to
    fetch its metadata from Open Library (key must start with 'OL').
    Otherwise supply 'title', 'authors', etc. directly in the seed entry.
    """
    seed_path = Path(path_str)
    if not seed_path.exists():
        raise click.ClickException(f"Seed file does not exist: {seed_path}")

    with open(seed_path, "r") as f:
        seeds: list[dict] = json.load(f)

    if not seeds:
        click.echo("Seed file is empty.")
        return

    # Fail fast on invalid enrich entries before any DB writes.
    for s in seeds:
        if s.get("enrich") and not (s.get("key") or "").startswith("OL"):
            raise click.ClickException(
                f"enrich=true for key {s.get('key')!r} "
                "but key does not start with 'OL'"
            )

    fetched = created = updated = skipped = 0

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

        if s.get("enrich"):
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
                click.echo(f"  Fetching {key} from Open Library...")
                try:
                    book_data = fetch_book_data(key)
                except Exception as exc:  # noqa: BLE001
                    click.echo(f"  WARNING: could not fetch {key}: {exc}")
                    skipped += 1
                    continue
                upsert_books(
                    [book_data],
                    tag_map={key: tags},
                    rating_map={key: rating},
                    title_overrides={key: title_override}
                    if title_override
                    else {},
                    description_overrides={key: description_override}
                    if description_override
                    else {},
                )
                fetched += 1
        else:
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
        f"{fetched} fetched from Open Library, "
        f"{created} created, "
        f"{updated} updated, "
        f"{skipped} skipped."
    )


_EXT_TO_LANG: dict[str, str] = {
    ".sql": "sql",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".sh": "bash",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".css": "css",
    ".r": "r",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".java": "java",
}


@click.command("import-code")
@click.option(
    "--path",
    "path_str",
    required=True,
    help="Directory containing code files (.sql, .py, etc.).",
)
@click.option(
    "--author",
    required=True,
    help="Author name to assign to all imported code posts.",
)
@with_appcontext
def import_code_command(path_str: str, author: str) -> None:
    """Import code files as code-type posts."""
    code_dir = Path(path_str)
    if not code_dir.exists():
        raise click.ClickException(f"Directory does not exist: {code_dir}")

    code_files = sorted(
        p
        for p in code_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in _EXT_TO_LANG
    )

    if not code_files:
        click.echo(f"No supported code files found under {code_dir}")
        return

    created = updated = errors = 0
    for path in code_files:
        try:
            lang = _EXT_TO_LANG[path.suffix.lower()]
            content = path.read_text(encoding="utf-8")
            body = f"```{lang}\n{content}\n```"
            slug = path.name
            title = path.name

            _, is_new = upsert_post(
                slug=slug,
                title=title,
                author=author,
                body=body,
                post_parent_slug=None,
                post_type="code",
                book=None,
            )
            if is_new:
                created += 1
                click.echo(f"  Created: {path.name}")
            else:
                updated += 1
                click.echo(f"  Updated: {path.name}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"ERROR {path.name}: {exc}")
            errors += 1

    db.session.commit()
    click.echo(
        f"Imported code from {code_dir}: "
        f"created={created}, updated={updated}, errors={errors}"
    )
    cache.clear()
    click.echo("Cache cleared.")


@click.command("reset-posts")
@click.option(
    "--path",
    "path_str",
    default=str(Path(__file__).parents[3] / "writing" / "posts"),
    show_default=True,
    help="Directory of markdown posts to re-import after reset.",
)
@with_appcontext
def reset_posts_command(path_str: str) -> None:
    """Delete all posts from the database and re-import from --path.

    Books, authors, and tags are not touched.
    """
    from app.backend.models import Post

    deleted = Post.query.delete()
    db.session.commit()
    click.echo(f"Deleted {deleted} post(s) from the database.")

    posts_dir = Path(path_str)
    if not posts_dir.exists():
        raise click.ClickException(f"Posts dir does not exist: {posts_dir}")

    md_files = sorted(p for p in posts_dir.rglob("*.md") if p.is_file())
    if not md_files:
        click.echo(f"No markdown files found under {posts_dir}")
        return

    created, updated, errors = _import_files(md_files)
    db.session.commit()
    click.echo(
        f"Re-imported posts from {posts_dir}: "
        f"created={created}, updated={updated}, errors={errors}"
    )
    cache.clear()
    click.echo("Cache cleared.")


def init_app(app) -> None:
    """Register CLI commands with the Flask app."""
    app.cli.add_command(import_code_command)
    app.cli.add_command(seed_books_command)
    app.cli.add_command(reset_posts_command)
