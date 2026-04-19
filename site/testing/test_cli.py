"""Tests for site/app/cli.py helper functions.

Covers _slugify, _manual_book_data, and resolve_book. The CLI commands
themselves (import-posts, seed-books) are exercised through integration;
these tests focus on the pure logic and DB-touching helpers.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.cli import _slugify, resolve_book
from app.backend.models import Book
from app.backend.markdown import parse_markdown_with_frontmatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_post(
    tmp_path: Path, content: str, filename: str = "post.md"
) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_lowercase_with_hyphens(self):
        assert _slugify("Kazuo Ishiguro") == "kazuo-ishiguro"

    def test_special_chars_removed(self):
        assert _slugify("J.R.R. Tolkien") == "jrr-tolkien"

    def test_already_a_slug(self):
        assert _slugify("already-slug") == "already-slug"

    def test_multiple_spaces_collapse_to_single_hyphen(self):
        assert _slugify("  lots   of   spaces  ") == "lots-of-spaces"

    def test_underscores_become_hyphens(self):
        assert _slugify("some_author_name") == "some-author-name"


# ---------------------------------------------------------------------------
# resolve_book
# ---------------------------------------------------------------------------


class TestResolveBook:
    def test_returns_none_when_no_key(self, tmp_path, session):
        path = write_post(
            tmp_path, "---\ntitle: T\nauthor: A\ntype: standalone\n---\nbody"
        )
        parsed = parse_markdown_with_frontmatter(path)
        assert resolve_book(parsed) is None

    def test_returns_existing_db_book(self, tmp_path, session):
        book = Book(book_ol_key="OL999W", book_title="Existing Book")
        session.add(book)
        session.flush()

        content = """\
---
title: My Review
author: Aya
type: review
book_key: OL999W
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        result = resolve_book(parsed)
        assert result is not None
        assert result.book_ol_key == "OL999W"

    def test_raises_when_book_not_in_db(self, tmp_path, session):
        content = """\
---
title: My Review
author: Aya
type: review
book_key: missing-book
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        with pytest.raises(ValueError, match="not in database"):
            resolve_book(parsed)

    def test_works_with_non_ol_key(self, tmp_path, session):
        book = Book(book_ol_key="my-manual-book", book_title="Manual Book")
        session.add(book)
        session.flush()

        content = """\
---
title: My Review
author: Aya
type: review
book_key: my-manual-book
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        result = resolve_book(parsed)
        assert result.book_ol_key == "my-manual-book"
