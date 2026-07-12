"""Plain data containers for book/author metadata used by the seed importer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuthorData:
    """Plain data container for an author."""

    ol_id: str
    name: str


@dataclass
class BookData:
    """Plain data container for a book."""

    ol_key: str
    title: str
    description: str | None
    publication_year: int | None
    page_count: int | None
    authors: list[AuthorData] = field(default_factory=list)
