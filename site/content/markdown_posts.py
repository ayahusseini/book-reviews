"""Markdown post parser and HTML renderer."""

from __future__ import annotations

from dataclasses import dataclass
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

    @property
    def slug(self) -> str:
        """Return frontmatter slug if set, otherwise the filename stem."""
        slug = self.metadata.get("slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
        return self.source_path.stem


def normalize_tag(tag: str) -> str:
    """Lowercase and collapse internal whitespace in a tag string."""
    return " ".join(tag.strip().split()).lower()


def parse_markdown_with_frontmatter(path: Path) -> MarkdownPost:
    """Parse a markdown file and return its frontmatter metadata
    and body."""
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

    return MarkdownPost(
        source_path=path, metadata=metadata, body_markdown=body
    )


def extract_tags(metadata: dict[str, Any]) -> list[str]:
    """Return a normalised, deduplicated,
    order-preserving list of tags."""
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
