"""Application CLI commands."""

from __future__ import annotations

from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext

from app.content.markdown_posts import (
    extract_tags,
    parse_markdown_with_frontmatter,
)
from app.database.models import Book, Post, Tag
from app.extensions import db


def _content_posts_dir() -> Path:
    # `site/app` is the package root; content lives inside it.
    return Path(current_app.root_path) / "content" / "posts"


def _upsert_tag(tag_name: str) -> Tag:
    tag = Tag.query.filter_by(tag_name=tag_name).first()
    if tag:
        return tag
    tag = Tag(tag_name=tag_name)
    db.session.add(tag)
    return tag


@click.command("import-posts")
@click.option(
    "--path",
    "path_str",
    default=None,
    help="Directory of markdown posts (defaults to site/app/content/posts).",
)
@with_appcontext
def import_posts_command(path_str: str | None):
    posts_dir = Path(path_str) if path_str else _content_posts_dir()
    if not posts_dir.exists():
        raise click.ClickException(f"Posts dir does not exist: {posts_dir}")

    md_files = sorted(p for p in posts_dir.rglob("*.md") if p.is_file())
    if not md_files:
        click.echo(f"No markdown files found under {posts_dir}")
        return

    created = 0
    updated = 0
    skipped = 0

    for path in md_files:
        parsed = parse_markdown_with_frontmatter(path)
        meta = parsed.metadata

        title = meta.get("title")
        author = meta.get("author")
        post_type = meta.get("type")
        book_ol_key = meta.get("book_ol_key")

        if not isinstance(title, str) or not title.strip():
            raise click.ClickException(f"{path}: missing frontmatter 'title'")
        if not isinstance(author, str) or not author.strip():
            raise click.ClickException(f"{path}: missing frontmatter 'author'")

        book = None
        if book_ol_key is not None:
            if not isinstance(book_ol_key, str) or not book_ol_key.strip():
                raise click.ClickException(
                    f"{path}: 'book_ol_key' must be a non-empty string"
                )
            book = Book.query.filter_by(book_ol_key=book_ol_key).first()
            if not book:
                skipped += 1
                click.echo(
                    f"SKIP {path.name}:"
                    + f"book_ol_key not found in DB: {book_ol_key}"
                )
                continue

        rel_source = str(path.relative_to(posts_dir))
        slug = parsed.slug

        post = Post.query.filter_by(post_source_path=rel_source).first()
        if not post:
            post = Post.query.filter_by(post_slug=slug).first()

        is_new = post is None
        if is_new:
            post = Post(
                post_slug=slug,
                post_source_path=rel_source,
                post_title=title.strip(),
                post_body_markdown=parsed.body_markdown,
                post_type=post_type.strip()
                if isinstance(post_type, str)
                else None,
                post_author=author.strip(),
                book=book,
            )
            db.session.add(post)
            created += 1
        else:
            post.post_slug = slug
            post.post_source_path = rel_source
            post.post_title = title.strip()
            post.post_body_markdown = parsed.body_markdown
            post.post_type = (
                post_type.strip() if isinstance(post_type, str) else None
            )
            post.post_author = author.strip()
            post.book = book
            updated += 1

        tags = extract_tags(meta)
        if book and tags:
            existing = {t.tag_name for t in book.tags}
            for tname in tags:
                if tname in existing:
                    continue
                tag = _upsert_tag(tname)
                book.tags.append(tag)
                existing.add(tname)

    db.session.commit()
    click.echo(
        f"Imported posts from {posts_dir}: "
        f"created={created}, updated={updated}, skipped={skipped}"
    )


def init_app(app):
    app.cli.add_command(import_posts_command)
