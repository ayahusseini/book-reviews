"""Script for handling OpenLibrary API calls"""

import logging
import requests
from dataclasses import dataclass, field
import re

from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://openlibrary.org"
COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
DEFAULT_TIMEOUT = 10  # seconds


@dataclass
class AuthorData:
    author_name: str
    author_openlibrary_id: str  # e.g. "OL123A"


@dataclass
class BookData:
    book_title: str
    book_isbn: str
    book_description: Optional[str]
    book_publication_year: Optional[int]
    book_cover_url: Optional[str]
    book_page_count: Optional[int]
    authors: list[AuthorData] = field(default_factory=list)
    # book_rating is not available from the Open Library data endpoints;
    # leave as None — callers can populate from a separate source.
    book_rating: Optional[int] = None


class OpenLibraryError(requests.HTTPError):
    """
    Raised when Open Library is unreachable
    or returns an unexpected response.
    """


def validate_response(response: requests.Response) -> None:
    """
    Raises an OpenLibrary error if the response object raises an error
    """
    try:
        response.raise_for_status()
    except requests.RequestException as err:
        raise OpenLibraryError(
            "Open Library returned"
            + f"{response.status_code}"
            + f"for parameters {response.json}: {err}"
        )


def build_works_url(ol_works_key: str) -> str:
    """
    Return the full Open Library works JSON URL for *ol_works_key*.

    Accepts both bare keys ("OL12345W") and path-prefixed keys
    ("/works/OL12345W").
    """
    key = ol_works_key.lstrip("/")
    if not key.startswith("works/"):
        key = f"works/{key}"
    return f"{BASE_URL}/{key}.json"


def fetch_works_data(
    ol_works_key: str, timeout: int = DEFAULT_TIMEOUT
) -> dict:
    """Return the raw works JSON for *ol_works_key*."""
    url = build_works_url(ol_works_key)
    response = requests.get(url, timeout=timeout)
    validate_response(response)
    return response.json()


def extract_title(works_data: dict) -> str:
    """
    Extract the book title from a works payload.
    """
    return works_data["title"]


def extract_description(works_data: dict) -> Optional[str]:
    """
    Extract a plain-text description from a works payload.

    Open Library stores descriptions either as a bare string or as
    ``{"type": "/type/text", "value": "..."}``.  Returns ``None`` when
    the field is absent.
    """
    raw = works_data.get("description")
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("value")
    return str(raw)


def extract_cover_url(works_data: dict) -> Optional[str]:
    """
    Return a large-size cover URL derived from the first cover ID in
    *works_data*, or ``None`` if no covers are listed.
    """
    covers = works_data.get("covers", [])
    if not covers:
        return None
    cover_id = covers[0]
    if cover_id == -1:
        return None
    return COVER_URL.format(cover_id=cover_id)


def extract_author_keys(works_data: dict) -> list[str]:
    """
    Return a list of raw author keys (e.g. ``["/authors/OL123A"]``)
    from a works payload.
    """
    entries = works_data.get("authors", [])
    keys: list[str] = []
    for entry in entries:
        # Two possible shapes:
        #   {"author": {"key": "/authors/OL123A"}, "type": {...}}
        #   {"key": "/authors/OL123A"}
        author_ref = entry.get("author") or entry
        key = author_ref.get("key")
        if key:
            keys.append(key)
    return keys


def build_editions_url(ol_works_key: str) -> str:
    """
    Return the editions JSON URL for *ol_works_key*.

    >>> build_editions_url("OL12345W")
    'https://openlibrary.org/works/OL12345W/editions.json'
    """
    key = ol_works_key.lstrip("/")
    if not key.startswith("works/"):
        key = f"works/{key}"
    return f"{BASE_URL}/{key}/editions.json"


def fetch_editions_data(ol_works_key: str, timeout=DEFAULT_TIMEOUT) -> dict:
    """Return the raw editions JSON for *ol_works_key*."""
    url = build_editions_url(ol_works_key)
    response = requests.get(url, timeout=timeout)
    validate_response(response)
    return response.json()


def extract_isbn(editions_data: dict) -> str:
    """
    Return the first available ISBN (preferring ISBN-13) found across
    all editions in *editions_data*.

    Raises:
        ValueError – no ISBN found in any edition
    """
    for edition in editions_data.get("entries", []):
        for isbn in edition.get("isbn_13", []):
            if isbn:
                return isbn
        for isbn in edition.get("isbn_10", []):
            if isbn:
                return isbn
    raise ValueError("No ISBN found in any edition.")


def extract_publication_year(editions_data: dict) -> Optional[int]:
    """
    Return the earliest publication year found across all editions, or
    ``None`` if no parsable year is present.
    """
    years: list[int] = []
    for edition in editions_data.get("entries", []):
        raw = edition.get("publish_date", "")
        match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", str(raw))
        if match:
            years.append(int(match.group(1)))
    return min(years) if years else None


def extract_page_count(editions_data: dict) -> Optional[int]:
    """
    Return the first non-zero page count found across all editions, or
    ``None`` if unavailable.
    """
    for edition in editions_data.get("entries", []):
        pages = edition.get("number_of_pages")
        if pages and int(pages) > 0:
            return int(pages)
    return None


# ---------------------------------------------------------------------------
# Author endpoint helpers
# ---------------------------------------------------------------------------


def build_author_url(author_key: str) -> str:
    """
    Return the full author JSON URL for *author_key*.

    Accepts both ``"/authors/OL123A"`` and bare ``"OL123A"``.

    >>> build_author_url("/authors/OL123A")
    'https://openlibrary.org/authors/OL123A.json'
    """
    key = author_key.lstrip("/")
    if not key.startswith("authors/"):
        key = f"authors/{key}"
    return f"{BASE_URL}/{key}.json"


def fetch_author_data(author_key: str, timeout=DEFAULT_TIMEOUT) -> dict:
    """Return the raw author JSON for *author_key*."""
    url = build_author_url(author_key)
    response = requests.get(url, timeout=timeout)
    validate_response(response)
    return response.json()


def extract_author_id(author_key: str) -> str:
    """
    Parse and return the bare Open Library author ID from *author_key*.

    >>> extract_author_id("/authors/OL123A")
    'OL123A'
    >>> extract_author_id("OL123A")
    'OL123A'
    """
    return author_key.rstrip("/").split("/")[-1]


def extract_author_name(author_data: dict) -> str:
    """
    Extract the author name from an author payload.

    Raises:
        KeyError – neither 'name' nor 'personal_name' is present
    """
    if "name" in author_data:
        return author_data["name"]
    return author_data["personal_name"]


def parse_author(author_key: str, author_data: dict) -> AuthorData:
    """
    Build an :class:`AuthorData` from a raw key and author payload.
    """
    return AuthorData(
        author_name=extract_author_name(author_data),
        author_openlibrary_id=extract_author_id(author_key),
    )


def fetch_all_authors(author_keys: list[str]) -> list[AuthorData]:
    """
    Fetch and parse every author in *author_keys*.

    Authors whose network request or parsing fails are skipped with a
    printed warning so one bad author doesn't abort the whole import.
    """
    authors: list[AuthorData] = []
    for key in author_keys:
        try:
            data = fetch_author_data(key)
            authors.append(parse_author(key, data))
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: could not fetch author {key!r}: {exc}")
    return authors


def fetch_book_data(ol_works_key: str) -> BookData:
    """
    Main entry point.

    Given an Open Library works key (e.g. ``"OL45804W"`` or
    ``"/works/OL45804W"``), fetch all data required to populate
    :class:`Book`, :class:`Author`, and :class:`BookAuthorMapping`.

    Returns a fully populated :class:`BookData` instance.
    """
    works = fetch_works_data(ol_works_key)
    editions = fetch_editions_data(ol_works_key)
    author_keys = extract_author_keys(works)
    authors = fetch_all_authors(author_keys)

    return BookData(
        book_title=extract_title(works),
        book_isbn=extract_isbn(editions),
        book_description=extract_description(works),
        book_publication_year=extract_publication_year(editions),
        book_cover_url=extract_cover_url(works),
        book_page_count=extract_page_count(editions),
        authors=authors,
    )


if __name__ == "__main__":
    print(fetch_book_data("OL2743111W"))
