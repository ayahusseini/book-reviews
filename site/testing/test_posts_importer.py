"""Tests for the import-posts CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.database.models import Book, Post, Tag


def write_post(
    posts_dir: Path,
    filename: str,
    *,
    slug: str,
    title: str = "T",
    author: str = "A",
    post_type: str | None = "review",
    book_ol_key: str | None = None,
    rating: float | None = None,
    tags: list[str] | None = None,
    body: str = "Hello",
) -> Path:
    """Write a markdown post file with frontmatter to posts_dir.

    slug is required — all posts must declare it explicitly.
    """
    tags = tags or []
    lines: list[str] = ["---"]
    lines.append(f"slug: {slug}")
    lines.append(f'title: "{title}"')
    lines.append(f'author: "{author}"')
    if post_type is not None:
        lines.append(f'type: "{post_type}"')
    if book_ol_key is not None:
        lines.append(f'book_ol_key: "{book_ol_key}"')
    if rating is not None:
        lines.append(f"rating: {rating}")
    if tags:
        lines.append("tags:")
        lines.extend([f'  - "{t}"' for t in tags])
    lines.append("---")
    lines.append("")
    lines.append(body)
    p = posts_dir / filename
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def run_import(app, posts_dir: Path):
    """Invoke the import-posts command and return the result."""
    runner = app.test_cli_runner()
    return runner.invoke(args=["import-posts", "--path", str(posts_dir)])


def test_import_creates_post_and_attaches_tags(app, db, tmp_path):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        db.session.add(book)
        db.session.commit()

        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "first.md",
            slug="my-post",
            title="My Post",
            author="Aya",
            book_ol_key="OL1W",
            tags=["Non-Fiction", "Favourites", "non-fiction"],
            body="## Hi",
        )

        result = run_import(app, posts_dir)
        assert result.exit_code == 0, result.output

        post = Post.query.one()
        assert post.post_title == "My Post"
        assert post.post_author == "Aya"
        assert post.post_slug == "my-post"
        assert post.book_id == book.book_id
        assert {t.tag_name for t in Tag.query.all()} == {
            "non-fiction",
            "favourites",
        }
        assert {t.tag_name for t in book.tags} == {"non-fiction", "favourites"}


def test_import_sets_rating_on_review_post(app, db, tmp_path):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        db.session.add(book)
        db.session.commit()

        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "review.md",
            slug="my-review",
            post_type="review",
            book_ol_key="OL1W",
            rating=4.5,
        )

        result = run_import(app, posts_dir)
        assert result.exit_code == 0, result.output

        post = Post.query.one()
        assert post.post_rating == 4.5


def test_import_ignores_rating_on_non_review_post(app, db, tmp_path):
    with app.app_context():
        book = Book(book_ol_key="OL1W", book_title="Book 1")
        db.session.add(book)
        db.session.commit()

        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "essay.md",
            slug="my-essay",
            post_type="essay",
            book_ol_key="OL1W",
            rating=4.5,
        )

        result = run_import(app, posts_dir)
        assert result.exit_code == 0, result.output

        post = Post.query.one()
        assert post.post_rating is None


def test_import_creates_standalone_post_without_book(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "standalone.md",
            slug="my-standalone",
            post_type="standalone",
            book_ol_key=None,
        )

        result = run_import(app, posts_dir)
        assert result.exit_code == 0, result.output

        post = Post.query.one()
        assert post.book_id is None
        assert post.post_rating is None


def test_import_fetches_missing_book_from_open_library(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "review.md",
            slug="fetched-book-review",
            post_type="review",
            book_ol_key="OL999W",
            rating=3.0,
        )

        from app.open_library import BookData

        fake_book_data = BookData(
            ol_key="OL999W",
            title="Fetched Book",
            isbn=None,
            description=None,
            publication_year=None,
            page_count=None,
            authors=[],
        )

        with patch(
            "app.open_library.fetch_book_data", return_value=fake_book_data
        ) as mock_fetch:
            result = run_import(app, posts_dir)

        assert result.exit_code == 0, result.output
        mock_fetch.assert_called_once_with("OL999W")

        book = Book.query.filter_by(book_ol_key="OL999W").one()
        assert book.book_title == "Fetched Book"

        post = Post.query.one()
        assert post.book_id == book.book_id


def test_import_is_idempotent_updates_existing_by_slug(app, db, tmp_path):
    with app.app_context():
        db.session.add(Book(book_ol_key="OL1W", book_title="Book 1"))
        db.session.commit()

        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()

        write_post(
            posts_dir,
            "same.md",
            slug="stable-slug",
            title="V1",
            author="Aya",
            book_ol_key="OL1W",
            tags=["tag-a"],
            body="Body v1",
        )

        r1 = run_import(app, posts_dir)
        assert r1.exit_code == 0, r1.output
        assert Post.query.count() == 1
        assert Tag.query.count() == 1

        write_post(
            posts_dir,
            "same.md",
            slug="stable-slug",
            title="V2",
            author="Aya",
            book_ol_key="OL1W",
            tags=["tag-a", "tag-b"],
            body="Body v2",
        )

        r2 = run_import(app, posts_dir)
        assert r2.exit_code == 0, r2.output

        assert Post.query.count() == 1
        post = Post.query.one()
        assert post.post_title == "V2"
        assert "Body v2" in post.post_body_markdown
        assert post.post_slug == "stable-slug"

        book = Book.query.filter_by(book_ol_key="OL1W").one()
        assert {t.tag_name for t in book.tags} == {"tag-a", "tag-b"}


def test_import_fails_on_invalid_post_type(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "bad-type.md",
            slug="bad-type-post",
            post_type="invalid_type",
        )

        result = run_import(app, posts_dir)
        assert result.exit_code != 0
        assert "invalid type" in result.output


def test_import_fails_on_rating_out_of_range(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "bad-rating.md",
            slug="bad-rating-post",
            post_type="review",
            rating=6.0,
        )

        result = run_import(app, posts_dir)
        assert result.exit_code != 0
        assert "rating" in result.output


def test_import_requires_title(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "bad.md").write_text(
            '---\nslug: "no-title"\nauthor: "Aya"\n---\nBody\n',
            encoding="utf-8",
        )

        result = run_import(app, posts_dir)
        assert result.exit_code != 0
        assert "missing frontmatter 'title'" in result.output


def test_import_requires_author(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "bad.md").write_text(
            '---\nslug: "no-author"\ntitle: "A Post"\n---\nBody\n',
            encoding="utf-8",
        )

        result = run_import(app, posts_dir)
        assert result.exit_code != 0
        assert "missing frontmatter 'author'" in result.output


def test_import_requires_slug(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "bad.md").write_text(
            '---\ntitle: "A Post"\nauthor: "Aya"\n---\nBody\n',
            encoding="utf-8",
        )

        result = run_import(app, posts_dir)
        assert result.exit_code != 0
        assert "slug" in result.output


def test_import_warns_when_review_has_no_book_ol_key(app, db, tmp_path):
    with app.app_context():
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        write_post(
            posts_dir,
            "review-no-book.md",
            slug="review-no-book",
            post_type="review",
            book_ol_key=None,
        )

        result = run_import(app, posts_dir)
        assert result.exit_code == 0, result.output
        assert "WARNING" in result.output

        post = Post.query.one()
        assert post.book_id is None
