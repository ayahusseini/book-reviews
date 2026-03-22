"""Markdown post parser and HTML renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bleach
import markdown
import yaml

from content.extract_quotes import (
    Quote,
    extract_ad_quotes,
    replace_ad_quotes_with_blockquotes,
)

VALID_POST_TYPES = {"review", "essay", "standalone", "note", "quotes", "poem"}


@dataclass
class MarkdownPost:
    """A parsed markdown post with frontmatter metadata and body text."""

    source_path: Path
    metadata: dict[str, Any]
    body_markdown: str
    quotes: list[Quote] = field(default_factory=list)

    def __post_init__(self):
        self._err = f"MarkdownPost for {self.source_path}: "
        if "title" not in self.metadata:
            raise ValueError(self._err + "missing frontmatter 'title'")
        if "author" not in self.metadata:
            raise ValueError(self._err + "missing frontmatter 'author'")
        if self.metadata.get("type") not in VALID_POST_TYPES:
            raise ValueError(
                self._err
                + f"invalid type {self.metadata.get('type')!r}, "
                + f"must be one of {sorted(VALID_POST_TYPES)}"
            )

    @property
    def title(self) -> str:
        return self.metadata["title"].strip()

    @property
    def author(self) -> str:
        return self.metadata["author"].strip()

    @property
    def post_type(self) -> str:
        return self.metadata["type"]

    @property
    def slug(self) -> str:
        """Return frontmatter slug if set, otherwise fall back to
        the filename stem."""
        slug = self.metadata.get("slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
        return self.source_path.stem

    @property
    def rating(self) -> float | None:
        """Return validated rating, or None.

        Rating is only meaningful on review posts — callers are responsible
        for ignoring it on other post types.
        """
        r = self.metadata.get("rating")
        if r is None:
            return None
        if not isinstance(r, (int, float)):
            raise TypeError(
                self._err + f"'rating' must be a number, got {type(r)}"
            )
        if not 0 <= r <= 5:
            raise ValueError(
                self._err + f"'rating' must be between 0 and 5, got {r}"
            )
        return float(r)

    @property
    def tags(self) -> list[str]:
        """Return normalised, deduplicated tags from frontmatter."""
        tag_vals = self.metadata.get("tags", [])
        if isinstance(tag_vals, str):
            tag_vals = [tag_vals]
        if not isinstance(tag_vals, list):
            raise TypeError(self._err + "tags must be a list")
        return list(
            {
                self._normalize_tag(t)
                for t in tag_vals
                if isinstance(t, str) and t.strip()
            }
        )

    @property
    def book_ol_key(self) -> str | None:
        return self.metadata.get("book_ol_key")

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        return " ".join(tag.strip().split()).lower()


def parse_markdown_with_frontmatter(path: Path) -> MarkdownPost:
    """Parse a markdown file and return a MarkdownPost.

    Any ```ad-quote blocks found in the body are:
    - extracted into the returned ``quotes`` list
    - replaced in the body with standard Markdown blockquote syntax

    Raises ValueError if required frontmatter fields are missing or invalid.
    """
    text = path.read_text(encoding="utf-8")

    metadata: dict[str, Any] = {}
    body = text

    if text.startswith("---"):
        lines = text.splitlines()
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx is not None:
            raw = "\n".join(lines[1:end_idx]).strip()
            if raw:
                loaded = yaml.safe_load(raw)
                if isinstance(loaded, dict):
                    metadata = loaded
            body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")

    quotes = extract_ad_quotes(body)
    print(f"for post {metadata.get('title')}, the quotes are \n{quotes}")
    clean_body = replace_ad_quotes_with_blockquotes(body)

    return MarkdownPost(
        source_path=path,
        metadata=metadata,
        body_markdown=clean_body,
        quotes=quotes,
    )


def render_markdown_to_safe_html(text: str) -> str:
    """Render markdown to sanitised HTML,
    stripping unsafe tags and attributes."""
    html = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "toc", "smarty"],
        output_format="html5",
    )

    allowed_tags = sorted(
        set(bleach.sanitizer.ALLOWED_TAGS).union(
            {
                "p",
                "pre",
                "code",
                "blockquote",
                "hr",
                "br",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "table",
                "thead",
                "tbody",
                "tr",
                "th",
                "td",
                "span",
                "div",
            }
        )
    )
    allowed_attrs = {
        **bleach.sanitizer.ALLOWED_ATTRIBUTES,
        "a": ["href", "title", "rel"],
        "span": ["class"],
        "div": ["class"],
        "code": ["class"],
        "pre": ["class"],
    }
    cleaned = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    return bleach.linkify(cleaned)
