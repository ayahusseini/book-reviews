"""Tests for builder.content — joining book_seed.json with post files."""

from datetime import date, datetime, timezone

import pytest

from builder.content import (
    Author,
    Book,
    Tag,
    load_books,
    load_poems,
    parse_date_read,
)


def write_seed(tmp_path, entries):
    import json

    seed_path = tmp_path / "book_seed.json"
    seed_path.write_text(json.dumps(entries), encoding="utf-8")
    return seed_path


def write_review(reviews_dir, filename, frontmatter, body=""):
    reviews_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    (reviews_dir / filename).write_text(
        f"---\n{lines}\n---\n{body}", encoding="utf-8"
    )


def write_poem(poems_dir, filename, frontmatter, body=""):
    poems_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    (poems_dir / filename).write_text(
        f"---\n{lines}\n---\n{body}", encoding="utf-8"
    )


class TestParseDateRead:
    def test_parses_iso_date_string(self):
        assert parse_date_read("2026-03-10") == date(2026, 3, 10)

    def test_returns_none_for_none(self):
        assert parse_date_read(None) is None

    def test_raises_for_non_string(self):
        with pytest.raises(ValueError):
            parse_date_read(123)


class TestLoadBooks:
    def test_builds_book_with_no_review(self, tmp_path):
        seed_path = write_seed(
            tmp_path,
            [
                {
                    "key": "wuthering-heights",
                    "title": "Wuthering Heights",
                    "authors": ["Emily Bronte"],
                    "tags": ["classic"],
                    "rating": 4,
                }
            ],
        )
        reviews_dir = tmp_path / "reviews"

        books = load_books(seed_path, reviews_dir)

        assert books == [
            Book(
                book_id="wuthering-heights",
                book_title="Wuthering Heights",
                book_description=None,
                book_publication_year=None,
                book_page_count=None,
                book_rating=4,
                book_date_read=None,
                authors=[Author(author_name="Emily Bronte")],
                tags=[Tag(tag_name="classic")],
                review_markdown=None,
                review_created_at=None,
                quotes=[],
            )
        ]

    def test_joins_matching_review(self, tmp_path):
        seed_path = write_seed(
            tmp_path,
            [{"key": "wuthering-heights", "title": "Wuthering Heights"}],
        )
        reviews_dir = tmp_path / "reviews"
        write_review(
            reviews_dir,
            "wh.md",
            {
                "title": "Wuthering Heights",
                "author": "Aya",
                "book_key": "wuthering-heights",
                "date": "2026-03-10",
            },
            body="Opening thoughts...",
        )

        books = load_books(seed_path, reviews_dir)

        assert len(books) == 1
        book = books[0]
        assert book.review_markdown.strip() == "Opening thoughts..."
        assert book.review_created_at == datetime(
            2026, 3, 10, tzinfo=timezone.utc
        )

    def test_raises_for_seed_entry_missing_title(self, tmp_path):
        seed_path = write_seed(tmp_path, [{"key": "no-title"}])
        with pytest.raises(ValueError, match="title"):
            load_books(seed_path, tmp_path / "reviews")

    def test_raises_for_review_with_unknown_book_key(self, tmp_path):
        seed_path = write_seed(
            tmp_path,
            [{"key": "wuthering-heights", "title": "Wuthering Heights"}],
        )
        reviews_dir = tmp_path / "reviews"
        write_review(
            reviews_dir,
            "orphan.md",
            {
                "title": "Some Review",
                "author": "Aya",
                "book_key": "does-not-exist",
            },
        )
        with pytest.raises(ValueError, match="does-not-exist"):
            load_books(seed_path, reviews_dir)


class TestLoadPoems:
    def test_loads_poem_with_slug_from_frontmatter(self, tmp_path):
        poems_dir = tmp_path / "poetry"
        write_poem(
            poems_dir,
            "fire-and-ice.md",
            {
                "title": "Fire and Ice",
                "author": "Robert Frost",
                "slug": "fire-and-ice",
                "date": "2026-04-10",
            },
            body="Some say the world will end in fire.",
        )

        poems = load_poems(poems_dir)

        assert len(poems) == 1
        assert poems[0].poem_slug == "fire-and-ice"
        assert poems[0].poem_title == "Fire and Ice"

    def test_returns_empty_list_when_poems_dir_missing(self, tmp_path):
        assert load_poems(tmp_path / "does-not-exist") == []
