from __future__ import annotations

from pathlib import Path

import pytest

from content.markdown_posts import (
    parse_markdown_with_frontmatter,
    render_markdown_to_safe_html,
    MarkdownPost,
)

from content.extract_quotes import Quote


def test_parse_markdown_with_frontmatter_extracts_metadata_and_body(
    tmp_path: Path,
):
    p = tmp_path / "post.md"
    p.write_text(
        """---
        title: "Hello"
        author: "Aya"
        tags:
        - "One"
        - "Two"
        ---

        ## Body

        Text
        """,
        encoding="utf-8",
    )

    parsed = parse_markdown_with_frontmatter(p)
    assert parsed.metadata["title"] == "Hello"
    assert parsed.metadata["author"] == "Aya"
    assert "## Body" in parsed.body_markdown


def test_parse_markdown_with_frontmatter_without_frontmatter_keeps_body(
    tmp_path: Path,
):
    p = tmp_path / "post.md"
    p.write_text("# Hi\n", encoding="utf-8")
    parsed = parse_markdown_with_frontmatter(p)
    assert parsed.metadata == {}
    assert parsed.body_markdown == "# Hi\n"


def test_slug_defaults_to_filename_stem(tmp_path: Path):
    p = tmp_path / "my-post.md"
    p.write_text("---\n---\nbody\n", encoding="utf-8")
    with pytest.raises(TypeError) as err:
        parse_markdown_with_frontmatter(p)
        assert err.value == "Must supply a string-type slug."


def test_slug_uses_frontmatter_slug_when_present(tmp_path: Path):
    p = tmp_path / "ignored.md"
    p.write_text("---\nslug: custom-slug\n---\nbody\n", encoding="utf-8")
    parsed = parse_markdown_with_frontmatter(p)
    assert parsed.slug == "custom-slug"


@pytest.fixture
def fake_markdown_post():
    return MarkdownPost(
        metadata={"tags": [], "slug": "fake_slug"},
        body_markdown="#fake",
        quotes=[Quote("quote")],
    )


def test_extract_tags_normalizes_dedupes(fake_markdown_post):
    fake_markdown_post.tags = [
        "  Sci  Fi ",
        "sci fi",
        "Non-Fiction",
        "",
        "NON-FICTION",
    ]
    assert set(fake_markdown_post.tags) == set(["sci fi", "non-fiction"])


def test_reassigning_slug_incorrectly_raises_error(fake_markdown_post):
    with pytest.raises(AttributeError):
        fake_markdown_post.slug = None


def test_render_markdown_to_safe_html_sanitizes_script_tags():
    html = render_markdown_to_safe_html(
        'Hello<script>alert("x")</script> <a href="javascript:alert(1)">x</a>'
    )
    assert "<script" not in html.lower()
    assert "javascript:" not in html.lower()
