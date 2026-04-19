"""Tests for site/content/markdown_posts.py.

Uses tmp_path (pytest built-in) to create real temporary .md files so the
parser runs exactly as it does in production.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.backend.markdown import (
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

    def test_disallowed_fields_raise(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nrating: 4\n---\nbody",
        )
        with pytest.raises(ValueError, match="disallowed frontmatter fields"):
            parse_markdown_with_frontmatter(path)

    def test_book_ol_key_disallowed(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nbook_ol_key: OL1W\n---\nbody",
        )
        with pytest.raises(ValueError, match="disallowed frontmatter fields"):
            parse_markdown_with_frontmatter(path)

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

    def test_book_key_absent_returns_none(self, tmp_path):
        path = write_post(tmp_path, MINIMAL_FRONTMATTER)
        assert parse_markdown_with_frontmatter(path).book_key is None

    def test_book_key_present(self, tmp_path):
        path = write_post(
            tmp_path,
            "---\ntitle: T\nauthor: A\ntype: review\nbook_key: my-book\n---\nbody",
        )
        assert parse_markdown_with_frontmatter(path).book_key == "my-book"


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

    def test_image_embed_becomes_img_tag(self):
        result = _expand_wikilinks("![[my-photo.jpg]]")
        assert "![my-photo.jpg](/static/img/my-photo.jpg)" in result

    def test_image_embed_not_treated_as_wikilink(self):
        result = _expand_wikilinks("![[my-photo.jpg]]")
        assert "/posts/" not in result

    def test_within_post_heading_link(self):
        result = _expand_wikilinks("See [[#Part Two]] for details.")
        assert "[Part Two](#part-two)" in result

    def test_within_post_heading_link_with_label(self):
        result = _expand_wikilinks("[[#Part Two|jump here]]")
        assert "[jump here](#part-two)" in result

    def test_heading_anchor_lowercased_with_hyphens(self):
        result = _expand_wikilinks("[[#My Big Section]]")
        assert "#my-big-section" in result

    def test_cross_post_heading_link(self):
        result = _expand_wikilinks("[[other-post#Section One]]")
        assert (
            "[other-post#Section One](/posts/other-post#section-one)" in result
        )

    def test_cross_post_heading_link_with_label(self):
        result = _expand_wikilinks("[[other-post#Section One|read this]]")
        assert "[read this](/posts/other-post#section-one)" in result

    def test_nested_heading_path_uses_leaf_anchor(self):
        # Obsidian uses [[#Parent#Child]] syntax; the HTML anchor is just the leaf
        result = _expand_wikilinks(
            "[[#Query trees#The separation of what and how in SQL|The separation of what and how in SQL]]"
        )
        assert "href" not in result  # this is markdown, not HTML
        assert "(#the-separation-of-what-and-how-in-sql)" in result

    def test_nested_heading_path_no_label_uses_leaf_as_display(self):
        result = _expand_wikilinks("[[#Parent Section#Child Section]]")
        assert "[Child Section](#child-section)" in result


# ---------------------------------------------------------------------------
# render_markdown_to_safe_html
# ---------------------------------------------------------------------------


class TestRenderMarkdownToSafeHtml:
    def test_renders_bold(self):
        assert "<strong>" in render_markdown_to_safe_html("**bold**")

    def test_renders_heading(self):
        assert "<h2" in render_markdown_to_safe_html("## Heading")

    def test_script_tags_stripped(self):
        html = render_markdown_to_safe_html("<script>alert('xss')</script>")
        assert "<script>" not in html

    def test_wikilinks_expanded_before_rendering(self):
        html = render_markdown_to_safe_html("See [[some-post|this post]].")
        assert 'href="/posts/some-post"' in html
        assert "this post" in html

    def test_blockquote_rendered(self):
        assert "<blockquote>" in render_markdown_to_safe_html("> A quote.")

    def test_image_embed_rendered(self):
        html = render_markdown_to_safe_html("![[diagram.png]]")
        assert "<img" in html
        assert 'src="/static/img/diagram.png"' in html

    def test_within_post_heading_link_rendered(self):
        html = render_markdown_to_safe_html("See [[#My Section]] here.")
        assert 'href="#my-section"' in html

    def test_cross_post_heading_link_rendered(self):
        html = render_markdown_to_safe_html(
            "See [[other-post#My Section|this]]."
        )
        assert 'href="/posts/other-post#my-section"' in html
