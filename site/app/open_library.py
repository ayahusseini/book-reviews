"""Open Library API client for fetching book and author metadata.

Pure HTTP client — no Flask, no SQLAlchemy imports.
Returns plain dataclasses only.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://openlibrary.org"
DEFAULT_TIMEOUT = 10


class OpenLibraryError(requests.HTTPError):
    """Raised when Open Library is unreachable or
    returns an unexpected response."""


@dataclass
class AuthorData:
    """Plain data container for an author fetched from Open Library."""

    ol_id: str
    name: str


@dataclass
class BookData:
    """Plain data container for a book fetched from Open Library."""

    ol_key: str
    title: str
    isbn: str | None
    description: str | None
    publication_year: int | None
    page_count: int | None
    authors: list[AuthorData] = field(default_factory=list)


def validate_response(response: requests.Response) -> None:
    """Raise OpenLibraryError if the response status indicates failure."""
    try:
        response.raise_for_status()
    except requests.RequestException as err:
        raise OpenLibraryError(
            f"Open Library returned {response.status_code} "
            f"for parameters {response.json}: {err}"
        )


def build_works_url(ol_works_key: str) -> str:
    """Return the full Open Library works JSON URL for ol_works_key."""
    key = ol_works_key.lstrip("/")
    if not key.startswith("works/"):
        key = f"works/{key}"
    return f"{BASE_URL}/{key}.json"


def fetch_works_data(
    ol_works_key: str, timeout: int = DEFAULT_TIMEOUT
) -> dict:
    """Return the raw works JSON for ol_works_key."""
    url = build_works_url(ol_works_key)
    response = requests.get(url, timeout=timeout)
    validate_response(response)
    return response.json()


def extract_title(works_data: dict) -> str:
    """Extract the book title from a works payload."""
    return works_data["title"]


def extract_description(works_data: dict) -> Optional[str]:
    """Extract a plain-text description from a works payload,
    or None if absent."""
    raw = works_data.get("description")
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("value")
    return str(raw)


def extract_author_keys(works_data: dict) -> list[str]:
    """Return a list of raw author keys from a works payload."""
    entries = works_data.get("authors", [])
    keys: list[str] = []
    for entry in entries:
        author_ref = entry.get("author") or entry
        key = author_ref.get("key")
        if key:
            keys.append(key)
    return keys


def build_editions_url(ol_works_key: str) -> str:
    """Return the editions JSON URL for ol_works_key."""
    key = ol_works_key.lstrip("/")
    if not key.startswith("works/"):
        key = f"works/{key}"
    return f"{BASE_URL}/{key}/editions.json"


def fetch_editions_data(
    ol_works_key: str, timeout: int = DEFAULT_TIMEOUT
) -> dict:
    """Return the raw editions JSON for ol_works_key."""
    url = build_editions_url(ol_works_key)
    response = requests.get(url, timeout=timeout)
    validate_response(response)
    return response.json()


def extract_isbn(editions_data: dict) -> Optional[str]:
    """Return the first available ISBN (preferring ISBN-13)
    across all editions, or None if not found."""
    for edition in editions_data.get("entries", []):
        for isbn in edition.get("isbn_13", []):
            if isbn:
                return isbn
        for isbn in edition.get("isbn_10", []):
            if isbn:
                return isbn
    return None


def extract_publication_year(editions_data: dict) -> Optional[int]:
    """Return the earliest publication year across all editions, or None."""
    years: list[int] = []
    for edition in editions_data.get("entries", []):
        raw = edition.get("publish_date", "")
        match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", str(raw))
        if match:
            years.append(int(match.group(1)))
    return min(years) if years else None


def extract_page_count(editions_data: dict) -> Optional[int]:
    """Return the first non-zero page count across all editions, or None."""
    for edition in editions_data.get("entries", []):
        pages = edition.get("number_of_pages")
        if pages and int(pages) > 0:
            return int(pages)
    return None


def build_author_url(author_key: str) -> str:
    """Return the full author JSON URL for author_key."""
    key = author_key.lstrip("/")
    if not key.startswith("authors/"):
        key = f"authors/{key}"
    return f"{BASE_URL}/{key}.json"


def fetch_author_data(author_key: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Return the raw author JSON for author_key."""
    url = build_author_url(author_key)
    response = requests.get(url, timeout=timeout)
    validate_response(response)
    return response.json()


def extract_author_id(author_key: str) -> str:
    """Parse and return the bare Open Library author ID from author_key."""
    return author_key.rstrip("/").split("/")[-1]


def extract_author_name(author_data: dict) -> str:
    """Extract the author name from an author payload.

    Raises KeyError if neither 'name' nor 'personal_name' is present.
    """
    if "name" in author_data:
        return author_data["name"]
    return author_data["personal_name"]


def parse_author(author_key: str, author_data: dict) -> AuthorData:
    """Build an AuthorData instance from a raw key and author payload."""
    return AuthorData(
        name=extract_author_name(author_data),
        ol_id=extract_author_id(author_key),
    )


def fetch_all_authors(author_keys: list[str]) -> list[AuthorData]:
    """Fetch and parse every author in author_keys, skipping failures."""
    authors: list[AuthorData] = []
    for key in author_keys:
        try:
            data = fetch_author_data(key)
            authors.append(parse_author(key, data))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch author %r: %s", key, exc)
    return authors


def fetch_book_data(ol_works_key: str) -> BookData:
    """Fetch all data for a works key and return a populated BookData."""
    works = fetch_works_data(ol_works_key)
    editions = fetch_editions_data(ol_works_key)
    author_keys = extract_author_keys(works)
    authors = fetch_all_authors(author_keys)

    return BookData(
        ol_key=ol_works_key,
        title=extract_title(works),
        isbn=extract_isbn(editions),
        description=extract_description(works),
        publication_year=extract_publication_year(editions),
        page_count=extract_page_count(editions),
        authors=authors,
    )
