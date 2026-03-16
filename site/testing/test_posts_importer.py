from __future__ import annotations

from pathlib import Path

import pytest

from app.database.models import Book, Post, Tag


def _write_post(
    posts_dir: Path,
    filename: str,
    *,
    title: str = "T",
    author: str = "A",
    post_type: str | None = "review",
    book_ol_key: str | None = None,
    tags: list[str] | None = None,
    body: str = "Hello",
    slug: str | None = None,
) -> Path:
    tags = tags or []
    lines: list[str] = ["---"]
    if slug is not None:
        lines.append(f"slug: {slug}")
    lines.append(f'title: "{title}"')
    lines.append(f'author: "{author}"')
    if post_type is not None:
        lines.append(f'type: "{post_type}"')
    if book_ol_key is not None:
        lines.append(f'book_ol_key: "{book_ol_key}"')
    if tags:
        lines.append("tags:")
        lines.extend([f'  - "{t}"' for t in tags])
    lines.append("---")
    lines.append("")
    lines.append(body)
    p = posts_dir / filename
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_import_posts_creates_post_and_attaches_tags(app, db, tmp_path: Path):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        db.session.add(book)
        db.session.commit()

        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        _write_post(
            posts_dir,
            "first.md",
            title="My Post",
            author="Aya",
            book_ol_key="OL1W",
            tags=["Non-Fiction", "Favourites", "non-fiction"],
            body="## Hi",
        )

        runner = app.test_cli_runner()
        result = runner.invoke(args=["import-posts", "--path", str(posts_dir)])
        assert result.exit_code == 0, result.output

        post = Post.query.one()
        assert post.post_title == "My Post"
        assert post.post_author == "Aya"
        assert post.post_source_path == "first.md"
        assert post.book_id == book.book_id
        assert {t.tag_name for t in Tag.query.all()} == {
            "non-fiction",
            "favourites",
        }
        assert {t.tag_name for t in book.tags} == {"non-fiction", "favourites"}


def test_import_posts_is_idempotent_updates_existing_by_source_path(
    app, db, tmp_path: Path
):
    with app.app_context():
        db.session.add(Book(book_ol_key="OL1W", book_title="Book 1"))
        db.session.commit()

        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()

        _write_post(
            posts_dir,
            "same.md",
            title="V1",
            author="Aya",
            book_ol_key="OL1W",
            tags=["tag-a"],
            body="Body v1",
        )

        runner = app.test_cli_runner()
        r1 = runner.invoke(args=["import-posts", "--path", str(posts_dir)])
        assert r1.exit_code == 0, r1.output
        assert Post.query.count() == 1
        assert Tag.query.count() == 1

        _write_post(
            posts_dir,
            "same.md",
            title="V2",
            author="Aya",
            book_ol_key="OL1W",
            tags=["tag-a", "tag-b"],
            body="Body v2",
        )
        r2 = runner.invoke(args=["import-posts", "--path", str(posts_dir)])
        assert r2.exit_code == 0, r2.output

        assert Post.query.count() == 1
        post = Post.query.one()
        assert post.post_title == "V2"
        assert "Body v2" in post.post_body_markdown
        book = Book.query.filter_by(book_ol_key="OL1W").one()
        assert {t.tag_name for t in book.tags} == {"tag-a", "tag-b"}


def test_import_posts_skips_when_book_missing(app, db, tmp_path: Path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        _write_post(
            posts_dir,
            "missing-book.md",
            title="Nope",
            author="Aya",
            book_ol_key="DOES_NOT_EXIST",
        )
        runner = app.test_cli_runner()
        result = runner.invoke(args=["import-posts", "--path", str(posts_dir)])
        assert result.exit_code == 0, result.output
        assert "SKIP missing-book.md" in result.output
        assert Post.query.count() == 0


def test_import_posts_requires_title_and_author(app, db, tmp_path: Path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "bad.md").write_text(
            '---\nauthor: "Aya"\n---\nBody\n', encoding="utf-8"
        )
        runner = app.test_cli_runner()
        result = runner.invoke(args=["import-posts", "--path", str(posts_dir)])
        assert result.exit_code != 0
        assert "missing frontmatter 'title'" in result.output
