"""Markdown-post importer and renderer utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bleach
import markdown
import yaml


@dataclass(frozen=True)
class MarkdownPost:
    source_path: Path
    metadata: dict[str, Any]
    body_markdown: str

    @property
    def slug(self) -> str:
        slug = self.metadata.get("slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
        return self.source_path.stem


def parse_markdown_with_frontmatter(path: Path) -> MarkdownPost:
    text = path.read_text(encoding="utf-8")

    metadata: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        lines = text.splitlines()
        # Find closing '---'
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


def _normalize_tag(tag: str) -> str:
    return " ".join(tag.strip().split()).lower()


def extract_tags(metadata: dict[str, Any]) -> list[str]:
    tags_val = metadata.get("tags", [])
    tags: list[str] = []

    if isinstance(tags_val, str):
        tags_val = [tags_val]

    if isinstance(tags_val, list):
        for item in tags_val:
            if isinstance(item, str):
                norm = _normalize_tag(item)
                if norm:
                    tags.append(norm)

    # preserve order, de-dupe
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def render_markdown_to_safe_html(text: str) -> str:
    html = markdown.markdown(
        text,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "smarty",
        ],
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
