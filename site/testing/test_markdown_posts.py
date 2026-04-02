"""Tests for site/content/markdown_posts.py.

Uses tmp_path (pytest built-in) to create real temporary .md files so the
parser runs exactly as it does in production.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from content.markdown_posts import (
    MarkdownPost,
    _expand_wikilinks,
    parse_markdown_with_frontmatter,
    render_markdown_to_safe_html,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_post(
    tmp_path: Path, content: str, filename: str = "post.md"
) -> Path:
    """Write content to a temp file and return the path."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


MINIMAL_FRONTMATTER = """\
---
title: "My Post"
author: "Aya"
type: standalone
---

Post body here.
"""


# ---------------------------------------------------------------------------
# MarkdownPost validation
# ---------------------------------------------------------------------------


class TestMarkdownPostValidation:
    def test_valid_post_constructs_without_error(self, tmp_path):
        path = write_post(tmp_path, MINIMAL_FRONTMATTER)
        post = parse_markdown_with_frontmatter(path)
        assert post.title == "My Post"

    def test_missing_title_raises(self, tmp_path):
        path = write_post(
            tmp_path, "---\nauthor: Aya\ntype: standalone\n---\nbody"
        )
        with pytest.raises(ValueError, match="title"):
            parse_markdown_with_frontmatter(path)

    def test_missing_author_raises(self, tmp_path):
        path = write_post(
            tmp_path, "---\ntitle: T\ntype: standalone\n---\nbody"
        )
        with pytest.raises(ValueError, match="author"):
            parse_markdown_with_frontmatter(path)

    def test_invalid_type_raises(self, tmp_path):
        path = write_post(
            tmp_path, "---\ntitle: T\nauthor: A\ntype: blogpost\n---\nbody"
        )
        with pytest.raises(ValueError, match="invalid type"):
            parse_markdown_with_frontmatter(path)

    def test_rating_must_be_a_number(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nrating: great\n---\nbody",
        )
        with pytest.raises(TypeError, match="number"):
            post = parse_markdown_with_frontmatter(path)
            _ = post.rating  # property is evaluated lazily

    def test_rating_out_of_range_raises(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nrating: 6\n---\nbody",
        )
        with pytest.raises(ValueError, match="between 0 and 5"):
            post = parse_markdown_with_frontmatter(path)
            _ = post.rating

    def test_invalid_date_format_raises(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: standalone\ndate: 15-01-2026\n---\nbody",
        )
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            post = parse_markdown_with_frontmatter(path)
            _ = post.date


# ---------------------------------------------------------------------------
# MarkdownPost properties
# ---------------------------------------------------------------------------


class TestMarkdownPostProperties:
    def test_slug_from_frontmatter(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: standalone\nslug: my-custom-slug\n---\nbody",
        )
        assert parse_markdown_with_frontmatter(path).slug == "my-custom-slug"

    def test_slug_falls_back_to_filename_stem(self, tmp_path):
        path = write_post(tmp_path, MINIMAL_FRONTMATTER, filename="my-file.md")
        assert parse_markdown_with_frontmatter(path).slug == "my-file"

    def test_date_parsed_from_string(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: standalone\ndate: 2026-03-15\n---\nbody",
        )
        post = parse_markdown_with_frontmatter(path)
        assert post.date == datetime(2026, 3, 15, tzinfo=timezone.utc)

    def test_date_defaults_to_none_when_absent(self, tmp_path):
        path = write_post(tmp_path, MINIMAL_FRONTMATTER)
        assert parse_markdown_with_frontmatter(path).date is None

    def test_tags_normalised_to_lowercase(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: standalone\ntags:\n  - Fiction\n  - NON-FICTION\n---\nbody",
        )
        tags = parse_markdown_with_frontmatter(path).tags
        assert set(tags) == {"fiction", "non-fiction"}

    def test_tags_deduplicated(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: standalone\ntags:\n  - poetry\n  - poetry\n---\nbody",
        )
        assert len(parse_markdown_with_frontmatter(path).tags) == 1

    def test_book_ol_key_absent_returns_none(self, tmp_path):
        path = write_post(tmp_path, MINIMAL_FRONTMATTER)
        assert parse_markdown_with_frontmatter(path).book_ol_key is None

    def test_book_ol_key_present(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nbook_ol_key: OL123W\n---\nbody",
        )
        assert parse_markdown_with_frontmatter(path).book_ol_key == "OL123W"

    def test_valid_rating_returned_as_float(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nrating: 4\n---\nbody",
        )
        assert parse_markdown_with_frontmatter(path).rating == 4.0

    def test_missing_rating_returns_none(self, tmp_path):
        path = write_post(tmp_path, MINIMAL_FRONTMATTER)
        assert parse_markdown_with_frontmatter(path).rating is None


# ---------------------------------------------------------------------------
# parse_markdown_with_frontmatter
# ---------------------------------------------------------------------------


class TestParseMarkdownWithFrontmatter:
    def test_body_is_content_after_frontmatter(self, tmp_path):
        path = write_post(tmp_path, MINIMAL_FRONTMATTER)
        post = parse_markdown_with_frontmatter(path)
        assert "Post body here." in post.body_markdown

    def test_file_without_frontmatter_raises(self, tmp_path):
        path = write_post(tmp_path, "Just plain text, no frontmatter.")
        # No frontmatter means no title/author/type — should raise
        with pytest.raises(ValueError):
            parse_markdown_with_frontmatter(path)

    def test_ad_quotes_extracted_from_body(self, tmp_path):
        content = """\
---
title: T
author: A
type: standalone
---

Some text.

```ad-quote
A memorable passage.
```

More text.
"""
        path = write_post(tmp_path, content)
        post = parse_markdown_with_frontmatter(path)
        assert len(post.quotes) == 1
        assert "A memorable passage." in post.quotes[0].quote_text

    def test_ad_quotes_replaced_with_blockquotes_in_body(self, tmp_path):
        content = """\
---
title: T
author: A
type: standalone
---

```ad-quote
Quoted text here.
```
"""
        path = write_post(tmp_path, content)
        post = parse_markdown_with_frontmatter(path)
        assert "```ad-quote" not in post.body_markdown
        assert "> Quoted text here." in post.body_markdown

    def test_multiple_ad_quotes_all_extracted(self, tmp_path):
        content = """\
---
title: T
author: A
type: standalone
---

```ad-quote
First quote.
```

```ad-quote
Second quote.
```
"""
        path = write_post(tmp_path, content)
        post = parse_markdown_with_frontmatter(path)
        assert len(post.quotes) == 2


# ---------------------------------------------------------------------------
# _expand_wikilinks
# ---------------------------------------------------------------------------


class TestExpandWikilinks:
    def test_plain_wikilink_becomes_link(self):
        result = _expand_wikilinks("See [[my-other-post]] for more.")
        assert "[my-other-post](/posts/my-other-post)" in result

    def test_wikilink_with_display_text(self):
        result = _expand_wikilinks("Read [[my-post|this post]] here.")
        assert "[this post](/posts/my-post)" in result

    def test_no_wikilinks_text_unchanged(self):
        text = "No links in this paragraph."
        assert _expand_wikilinks(text) == text

    def test_multiple_wikilinks_all_expanded(self):
        text = "See [[post-a]] and [[post-b|Post B]]."
        result = _expand_wikilinks(text)
        assert "/posts/post-a" in result
        assert "/posts/post-b" in result
        assert "Post B" in result


# ---------------------------------------------------------------------------
# render_markdown_to_safe_html
# ---------------------------------------------------------------------------


class TestRenderMarkdownToSafeHtml:
    def test_renders_bold(self):
        assert "<strong>" in render_markdown_to_safe_html("**bold**")

    def test_renders_heading(self):
        assert "<h2>" in render_markdown_to_safe_html("## Heading")

    def test_script_tags_stripped(self):
        html = render_markdown_to_safe_html("<script>alert('xss')</script>")
        assert "<script>" not in html

    def test_wikilinks_expanded_before_rendering(self):
        html = render_markdown_to_safe_html("See [[some-post|this post]].")
        assert 'href="/posts/some-post"' in html
        assert "this post" in html

    def test_blockquote_rendered(self):
        assert "<blockquote>" in render_markdown_to_safe_html("> A quote.")
