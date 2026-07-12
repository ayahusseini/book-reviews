"""Markdown post parser and HTML renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pathlib import Path
from typing import Any

import bleach
import markdown
import yaml

from app.backend.extract_quotes import (
    ExtractedQuote,
    extract_ad_quotes,
    replace_ad_quotes_with_blockquotes,
)

# Matches ![[filename]] — Obsidian-style image embeds
_IMAGE_WIKILINK_RE = re.compile(r"!\[\[([^\]]+?)\]\]")

# Matches [[target]] and [[target|label]] — not preceded by !
_WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")


@dataclass
class MarkdownPost:
    """A parsed markdown post with frontmatter metadata and body text."""

    source_path: Path
    metadata: dict[str, Any]
    body_markdown: str
    quotes: list[ExtractedQuote] = field(default_factory=list)

    _REMOVED_FIELDS = {
        "book_ol_key",
        "enrich_book",
        "book_title",
        "book_authors",
        "book_publication_year",
        "book_page_count",
        "book_description",
        "rating",
    }

    def __post_init__(self):
        self._err = f"MarkdownPost for {self.source_path}: "
        if "title" not in self.metadata:
            raise ValueError(self._err + "missing frontmatter 'title'")
        if "author" not in self.metadata:
            raise ValueError(self._err + "missing frontmatter 'author'")
        bad = self._REMOVED_FIELDS & self.metadata.keys()
        if bad:
            raise ValueError(
                self._err
                + f"disallowed frontmatter fields: {sorted(bad)}. "
                + "Book metadata belongs in book_seed.json."
            )

    @property
    def title(self) -> str:
        return self.metadata["title"].strip()

    @property
    def author(self) -> str:
        return self.metadata["author"].strip()

    @property
    def slug(self) -> str:
        """Return frontmatter slug if set, otherwise fall back to
        the filename stem."""
        slug = self.metadata.get("slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
        return self.source_path.stem

    @property
    def book_key(self) -> str | None:
        """Key referencing the book's entry in book_seed.json."""
        return self.metadata.get("book_key")

    @property
    def date(self) -> datetime | None:
        raw = self.metadata.get("date")
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return (
                raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw
            )
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            raise ValueError(
                self._err + f"'date' must be in YYYY-MM-DD format, got {raw!r}"
            )


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
    clean_body = replace_ad_quotes_with_blockquotes(body)

    return MarkdownPost(
        source_path=path,
        metadata=metadata,
        body_markdown=clean_body,
        quotes=quotes,
    )


def _heading_to_anchor(heading: str) -> str:
    """Convert heading text to an HTML anchor id,
    matching the toc extension's slugify."""
    heading = heading.lower()
    heading = re.sub(r"[^\w\s-]", "", heading)
    return re.sub(r"\s+", "-", heading.strip())


def _expand_wikilinks(text: str) -> str:
    """Expand Obsidian-style wikilinks and image embeds.

    ![[image.png]]           → ![image.png](/static/img/image.png)
    [[#heading]]              → [heading](#anchor)
    [[#heading|label]]        → [label](#anchor)

    Cross-document wikilinks (e.g. [[some-slug]]) are not supported:
    reviews and poems each have their own slug namespace, so there is no
    single route a bare slug could resolve to.
    """

    def replace_image(m: re.Match) -> str:
        filename = m.group(1).strip()
        return f"![{filename}](/static/img/{filename})"

    text = _IMAGE_WIKILINK_RE.sub(replace_image, text)

    def replace(m: re.Match) -> str:
        target = m.group(1).strip()
        label = (m.group(2) or "").strip()

        if target.startswith("#"):
            heading_path = target[1:].strip()
            leaf_heading = heading_path.rsplit("#", 1)[-1].strip()
            anchor = _heading_to_anchor(leaf_heading)
            display = label or leaf_heading
            return f"[{display}](#{anchor})"

        raise ValueError(
            f"Cross-document wikilink [[{target}]] is not supported; "
            "only [[#heading]] same-document anchors are."
        )

    return _WIKILINK_RE.sub(replace, text)


def render_markdown_to_safe_html(text: str) -> str:
    """Render markdown to sanitised HTML,
    stripping unsafe tags and attributes."""
    text = _expand_wikilinks(text)
    html = markdown.markdown(
        text,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "smarty",
            "pymdownx.highlight",
            "pymdownx.superfences",
        ],
        extension_configs={
            "pymdownx.highlight": {
                "linenums": False,
                "guess_lang": True,
                "use_pygments": True,
                "pygments_style": "dracula",
                "noclasses": False,
            }
        },
        output_format="html5",
    )

    allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS).union(
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
            "ul",
            "ol",
            "li",
            "img",
        }
    )
    allowed_attrs = {
        "*": ["class", "id"],
        "a": ["href", "title", "rel"],
        "span": ["class"],
        "div": ["class"],
        "code": ["class"],
        "pre": ["class"],
        "table": ["class"],
        "td": ["class"],
        "th": ["class"],
        "img": ["src", "alt", "title"],
    }
    cleaned = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    return bleach.linkify(cleaned)
