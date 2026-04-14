"""Tests for site/app/cli.py helper functions.

Covers _slugify, _manual_book_data, and resolve_book. The CLI commands
themselves (import-posts, seed-books) are exercised through integration;
these tests focus on the pure logic and DB-touching helpers.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.cli import _manual_book_data, _slugify, resolve_book
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
# _manual_book_data
# ---------------------------------------------------------------------------


class TestManualBookData:
    def test_returns_none_when_no_key(self, tmp_path):
        path = write_post(
            tmp_path, "---\ntitle: T\nauthor: A\ntype: standalone\n---\nbody"
        )
        parsed = parse_markdown_with_frontmatter(path)
        assert _manual_book_data(parsed) is None

    def test_returns_none_when_no_book_title(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nbook_key: my-book\n---\nbody",
        )
        parsed = parse_markdown_with_frontmatter(path)
        assert _manual_book_data(parsed) is None

    def test_returns_book_data_with_correct_fields(self, tmp_path):
        content = """\
---
title: My Review
author: Aya
type: review
book_key: remains-of-the-day
book_title: The Remains of the Day
book_publication_year: 1989
book_page_count: 258
book_description: A quiet novel.
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        data = _manual_book_data(parsed)
        assert data is not None
        assert data.ol_key == "remains-of-the-day"
        assert data.title == "The Remains of the Day"
        assert data.publication_year == 1989
        assert data.page_count == 258
        assert data.description == "A quiet novel."

    def test_authors_get_slugified_keys(self, tmp_path):
        content = """\
---
title: My Review
author: Aya
type: review
book_key: my-book
book_title: My Book
book_authors:
  - Kazuo Ishiguro
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        data = _manual_book_data(parsed)
        assert data.authors[0].ol_id == "kazuo-ishiguro"
        assert data.authors[0].name == "Kazuo Ishiguro"

    def test_book_ol_key_used_when_book_key_absent(self, tmp_path):
        content = """\
---
title: My Review
author: Aya
type: review
book_ol_key: OL123W
book_title: My Book
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        data = _manual_book_data(parsed)
        assert data.ol_key == "OL123W"

    def test_no_authors_gives_empty_list(self, tmp_path):
        content = """\
---
title: My Review
author: Aya
type: review
book_key: my-book
book_title: My Book
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        data = _manual_book_data(parsed)
        assert data.authors == []


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

    def test_enrich_true_with_non_ol_key_raises(self, tmp_path, session):
        content = """\
---
title: My Review
author: Aya
type: review
book_key: my-manual-book
book_title: My Book
enrich_book: true
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        with pytest.raises(ValueError, match="does not start with 'OL'"):
            resolve_book(parsed)

    def test_enrich_true_with_ol_key_calls_upsert_single_book(
        self, tmp_path, session
    ):
        content = """\
---
title: My Review
author: Aya
type: review
book_ol_key: OL123W
enrich_book: true
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        mock_book = MagicMock()
        with patch(
            "app.cli.upsert_single_book", return_value=mock_book
        ) as mock:
            result = resolve_book(parsed)
            mock.assert_called_once_with("OL123W")
            assert result is mock_book

    def test_returns_existing_db_book_without_enrich(self, tmp_path, session):
        book = Book(book_ol_key="OL999W", book_title="Existing Book")
        session.add(book)
        session.flush()

        content = """\
---
title: My Review
author: Aya
type: review
book_ol_key: OL999W
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        result = resolve_book(parsed)
        assert result is not None
        assert result.book_ol_key == "OL999W"

    def test_creates_manual_book_when_not_in_db(self, tmp_path, session):
        content = """\
---
title: My Review
author: Aya
type: review
book_key: my-new-book
book_title: A New Book
book_authors:
  - Some Author
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        result = resolve_book(parsed)
        assert result is not None
        assert result.book_ol_key == "my-new-book"
        assert result.book_title == "A New Book"

    def test_raises_when_key_set_but_no_title_and_not_in_db(
        self, tmp_path, session
    ):
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
        with pytest.raises(ValueError, match="not in the database"):
            resolve_book(parsed)
