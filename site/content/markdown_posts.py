"""Markdown post parser and HTML renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bleach
import markdown
import yaml


@dataclass(frozen=True)
class MarkdownPost:
    """A parsed markdown post with frontmatter metadata and body text."""

    source_path: Path
    metadata: dict[str, Any]
    body_markdown: str
    quotes: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        """Return frontmatter slug if set, otherwise the filename stem."""
        slug = self.metadata.get("slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
        return self.source_path.stem


# Matches ```ad-quote ... ``` blocks (non-greedy, dotall)
_AD_QUOTE_RE = re.compile(
    r"```ad-quote\n(.*?)```",
    re.DOTALL,
)


def extract_ad_quotes(body: str) -> list[str]:
    """Return the text content of every ```ad-quote block in body."""
    return [m.group(1).strip() for m in _AD_QUOTE_RE.finditer(body)]


def replace_ad_quotes_with_blockquotes(body: str) -> str:
    """Replace ```ad-quote blocks with Markdown blockquote syntax."""

    def _to_blockquote(m: re.Match) -> str:
        text = m.group(1).strip()
        # Prefix every line with "> " so markdown renders it as a blockquote
        quoted = "\n".join(f"> {line}" for line in text.splitlines())
        return quoted

    return _AD_QUOTE_RE.sub(_to_blockquote, body)


def normalize_tag(tag: str) -> str:
    """Lowercase and collapse internal whitespace in a tag string."""
    return " ".join(tag.strip().split()).lower()


def parse_markdown_with_frontmatter(path: Path) -> MarkdownPost:
    """Parse a markdown file and return its frontmatter metadata and body.

    Any ```ad-quote blocks found in the body are:
    - extracted into the returned ``quotes`` list
    - replaced in the body with standard Markdown blockquote syntax
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


def extract_tags(metadata: dict[str, Any]) -> list[str]:
    """Return a normalised, deduplicated, order-preserving list of tags."""
    tags_val = metadata.get("tags", [])

    if isinstance(tags_val, str):
        tags_val = [tags_val]

    if not isinstance(tags_val, list):
        return []

    seen: set[str] = set()
    out: list[str] = []
    for item in tags_val:
        if not isinstance(item, str):
            continue
        norm = normalize_tag(item)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


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
