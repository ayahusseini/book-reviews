"""Application CLI commands."""

from __future__ import annotations

import hashlib
from pathlib import Path

import click
from flask.cli import with_appcontext

from content.markdown_posts import (
    extract_tags,
    parse_markdown_with_frontmatter,
)
from app.database.models import VALID_POST_TYPES, Author, Book, Post, Tag
from seed_database.open_library import fetch_book_data
from app.extensions import db


def upsert_tag(tag_name: str) -> Tag:
    """Return existing tag by name, or create and stage a new one."""
    tag = Tag.query.filter_by(tag_name=tag_name).first()
    if tag:
        return tag
    tag = Tag(tag_name=tag_name)
    db.session.add(tag)
    return tag


def attach_tags(book: Book, tags: list[str]) -> None:
    """Add any missing tags to the book, creating tags that don't exist yet."""
    existing = {t.tag_name for t in book.tags}
    for tag_name in tags:
        if tag_name not in existing:
            book.tags.append(upsert_tag(tag_name))
            existing.add(tag_name)


def upsert_author(author) -> object:
    """Return existing author by OL id, or stage the new one for insert."""
    if author.author_openlibrary_id:
        existing = Author.query.filter_by(
            author_openlibrary_id=author.author_openlibrary_id
        ).first()
        if existing:
            return existing
    db.session.add(author)
    return author


def upsert_book(ol_key: str) -> Book:
    """Return existing book by OL key,
    or fetch from Open Library and create it."""
    book = Book.query.filter_by(book_ol_key=ol_key).first()
    if book:
        return book
    click.echo(f"Book {ol_key!r} not in DB — fetching from Open Library")
    book = fetch_book_data(ol_key)
    book.authors = [upsert_author(a) for a in book.authors]
    db.session.add(book)
    return book


def validate_post_type(post_type: str | None, path: Path) -> None:
    """Raise ClickException if post_type is set but not a recognised value."""
    if post_type is not None and post_type not in VALID_POST_TYPES:
        raise click.ClickException(
            f"{path}: invalid type {post_type!r}."
            f" Must be one of: {', '.join(sorted(VALID_POST_TYPES))}"
        )


def validate_book_post_has_ol_key(
    post_type: str | None, ol_key: str | None, path: Path
) -> None:
    """Warn if a review or essay post is missing a book_ol_key."""
    if post_type in {"review", "essay"} and not ol_key:
        click.echo(
            f"WARNING {path.name}: type={post_type!r} but no book_ol_key set."
            " Post will be created as standalone."
        )


def validate_rating(
    rating: object, post_type: str | None, path: Path
) -> float | None:
    """Return a validated float rating, or None.

    Rating is only read for review posts. Raises ClickException if the
    value is present but invalid.
    """
    if post_type != "review" or rating is None:
        return None
    if not isinstance(rating, (int, float)):
        raise click.ClickException(
            f"{path}: 'rating' must be a number, got {type(rating)}"
        )
    rating_f = float(rating)
    if not 0 <= rating_f <= 5:
        raise click.ClickException(
            f"{path}: 'rating' must be between 0 and 5, got {rating_f}"
        )
    return rating_f


def resolve_book(ol_key: str | None, path: Path) -> Book | None:
    """Return the Book for ol_key, fetching from OL if needed, or None."""
    if ol_key is None:
        return None
    if not isinstance(ol_key, str) or not ol_key.strip():
        raise click.ClickException(
            f"{path}: 'book_ol_key' must be a non-empty string"
        )
    return upsert_book(ol_key.strip())


def upsert_post(
    *,
    slug: str,
    rel_source: str,
    title: str,
    author: str,
    body: str,
    post_type: str | None,
    post_rating: float | None,
    book: Book | None,
) -> tuple[Post, bool]:
    """Update an existing post or create a new one.

    Returns the post and a boolean indicating whether it was newly created.
    """
    post = Post.query.filter_by(post_source_path=rel_source).first()
    if not post:
        post = Post.query.filter_by(post_slug=slug).first()

    is_new = post is None
    if is_new:
        post = Post(
            post_slug=slug,
            post_source_path=rel_source,
            post_title=title,
            post_body_markdown=body,
            post_type=post_type,
            post_author=author,
            post_rating=post_rating,
            book=book,
        )
        db.session.add(post)
    else:
        post.post_slug = slug
        post.post_source_path = rel_source
        post.post_title = title
        post.post_body_markdown = body
        post.post_type = post_type
        post.post_author = author
        post.post_rating = post_rating
        post.book = book

    return post, is_new


def _quote_hash(text: str) -> str:
    """Return an 8-char hex hash of the first min(100, len) chars of text."""
    sample = text[: min(100, len(text))]
    return hashlib.sha1(sample.encode("utf-8")).hexdigest()[:8]


def _quote_source_path(rel_source: str, h: str) -> str:
    """Encode a stable source path for a quote post."""
    return f"{rel_source}::quote:{h}"


def _quote_slug(h: str) -> str:
    """Return a slug for a quote post."""
    return f"quote-{h}"


def sync_quotes(
    *,
    quotes: list[str],
    rel_source: str,
    author: str,
    book: Book | None,
) -> tuple[int, int]:
    """Upsert quote posts extracted from a parent markdown file.

    - Creates or updates one Post(post_type='quotes') per quote.
    - Deletes any stale quote posts from this source file whose hash
      is no longer present in the current set.

    Returns (created_count, updated_count).
    """
    current_hashes: set[str] = set()
    created = updated = 0

    for quote_text in quotes:
        h = _quote_hash(quote_text)
        current_hashes.add(h)
        source_path = _quote_source_path(rel_source, h)
        slug = _quote_slug(h)

        _, is_new = upsert_post(
            slug=slug,
            rel_source=source_path,
            title=f"Quote ({h})",
            author=author,
            body=quote_text,
            post_type="quotes",
            post_rating=None,
            book=book,
        )
        if is_new:
            created += 1
        else:
            updated += 1

    # Remove stale quote posts from this source file
    prefix = f"{rel_source}::quote:"
    all_quotes_for_source = Post.query.filter(
        Post.post_source_path.like(f"{prefix}%"),
        Post.post_type == "quotes",
    ).all()

    for stale in all_quotes_for_source:
        # Extract hash from source path suffix
        stored_hash = stale.post_source_path[len(prefix) :]
        if stored_hash not in current_hashes:
            db.session.delete(stale)

    return created, updated


def import_post_file(path: Path, posts_dir: Path) -> bool:
    """Parse and upsert a single markdown post file.

    Returns True if the post was newly created, False if updated.
    Raises ClickException on validation errors.
    """
    parsed = parse_markdown_with_frontmatter(path)
    meta = parsed.metadata

    title = meta.get("title")
    author = meta.get("author")

    if not isinstance(title, str) or not title.strip():
        raise click.ClickException(f"{path}: missing frontmatter 'title'")
    if not isinstance(author, str) or not author.strip():
        raise click.ClickException(f"{path}: missing frontmatter 'author'")

    post_type = meta.get("type")
    if isinstance(post_type, str):
        post_type = post_type.strip() or None

    validate_post_type(post_type, path)

    ol_key = meta.get("book_ol_key")
    validate_book_post_has_ol_key(post_type, ol_key, path)

    book = resolve_book(ol_key, path)
    post_rating = validate_rating(meta.get("rating"), post_type, path)

    rel_source = str(path.relative_to(posts_dir))
    slug = parsed.slug

    post, is_new = upsert_post(
        slug=slug,
        rel_source=rel_source,
        title=title.strip(),
        author=author.strip(),
        body=parsed.body_markdown,
        post_type=post_type,
        post_rating=post_rating,
        book=book,
    )

    if book:
        attach_tags(book, extract_tags(meta))

    # Sync extracted ad-quote blocks as separate quote posts
    sync_quotes(
        quotes=parsed.quotes,
        rel_source=rel_source,
        author=author.strip(),
        book=book,
    )

    return is_new


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

    created = updated = 0

    for path in md_files:
        is_new = import_post_file(path, posts_dir)
        if is_new:
            created += 1
        else:
            updated += 1

    db.session.commit()
    click.echo(
        f"Imported posts from {posts_dir}: "
        f"created={created}, updated={updated}"
    )


def init_app(app) -> None:
    """Register CLI commands with the Flask app."""
    app.cli.add_command(import_posts_command)
