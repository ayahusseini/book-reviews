"""Tests for site/app/cli.py helper functions.

Covers _slugify, resolve_book, import_review_file, and import_poem_file.
The reset-posts and seed-books CLI commands themselves are exercised
through manual/integration use; these tests focus on the pure logic and
DB-touching helpers.
"""

from pathlib import Path

import pytest

from app.cli import (
    _slugify,
    import_poem_file,
    import_review_file,
    resolve_book,
)
from app.backend.models import Book, Poem, Quote
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
        path = write_post(tmp_path, "---\ntitle: T\nauthor: A\n---\nbody")
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
book_key: my-manual-book
---
Body.
"""
        path = write_post(tmp_path, content)
        parsed = parse_markdown_with_frontmatter(path)
        result = resolve_book(parsed)
        assert result.book_ol_key == "my-manual-book"


# ---------------------------------------------------------------------------
# import_review_file
# ---------------------------------------------------------------------------


class TestImportReviewFile:
    def test_raises_when_no_book_key(self, tmp_path, session):
        content = "---\ntitle: A Review\nauthor: Aya\n---\nBody."
        path = write_post(tmp_path, content)
        with pytest.raises(ValueError, match="book_key"):
            import_review_file(path)

    def test_sets_review_on_book(self, tmp_path, session):
        book = Book(book_ol_key="OL1W", book_title="A Book")
        session.add(book)
        session.flush()

        content = """\
---
title: A Review
author: Aya
book_key: OL1W
---
This book was great.
"""
        path = write_post(tmp_path, content)
        is_new = import_review_file(path)

        assert is_new is True
        assert "great" in book.review_markdown

    def test_extracts_quotes_onto_book(self, tmp_path, session):
        book = Book(book_ol_key="OL1W", book_title="A Book")
        session.add(book)
        session.flush()

        content = """\
---
title: A Review
author: Aya
book_key: OL1W
---
```ad-quote
A memorable line.
```
"""
        path = write_post(tmp_path, content)
        import_review_file(path)
        session.flush()

        quote = session.query(Quote).first()
        assert quote is not None
        assert quote.book_id == book.book_id
        assert quote.quote_text == "A memorable line."


# ---------------------------------------------------------------------------
# import_poem_file
# ---------------------------------------------------------------------------


class TestImportPoemFile:
    def test_creates_poem(self, tmp_path, session):
        content = """\
---
title: My Poem
author: Aya
---
Roses are red.
"""
        path = write_post(tmp_path, content, filename="my-poem.md")
        is_new = import_poem_file(path)

        assert is_new is True
        poem = session.query(Poem).filter_by(poem_slug="my-poem").first()
        assert poem is not None
        assert poem.poem_title == "My Poem"
