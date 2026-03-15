"""Tests app/open_library.py

Run with:
    pytest test_openlibrary.py -v
"""

from __future__ import annotations


import pytest
import requests

from app.database.open_library import (
    AuthorData,
    build_author_url,
    build_editions_url,
    build_works_url,
    extract_author_id,
    extract_author_keys,
    extract_author_name,
    extract_cover_url,
    extract_description,
    extract_isbn,
    extract_page_count,
    extract_publication_year,
    extract_title,
    parse_author,
    validate_response,
    OpenLibraryError,
)


@pytest.fixture()
def works_payload():
    return {
        "title": "Fantastic Mr Fox",
        "description": {
            "type": "/type/text",
            "value": "A fox outwits three farmers.",
        },
        "covers": [8739161],
        "authors": [
            {
                "author": {"key": "/authors/OL34184A"},
                "type": {"key": "/type/author_role"},
            }
        ],
    }


@pytest.fixture()
def editions_payload():
    return {
        "entries": [
            {
                "isbn_13": ["9780142410349"],
                "publish_date": "September 2007",
                "number_of_pages": 96,
            },
            {
                "isbn_10": ["0140328726"],
                "publish_date": "1996",
                "number_of_pages": 80,
            },
        ]
    }


@pytest.fixture()
def author_payload():
    return {"name": "Roald Dahl", "key": "/authors/OL34184A"}


def test_validate_reponse_success():
    real_response = requests.Response()
    real_response.status_code = 200
    validate_response(real_response)


def test_validate_reponse_errors():
    real_response = requests.Response()
    real_response.status_code = 404
    with pytest.raises(OpenLibraryError):
        validate_response(real_response)


class TestBuildWorksUrl:
    def test_bare_key(self):
        assert (
            build_works_url("OL12345W")
            == "https://openlibrary.org/works/OL12345W.json"
        )

    def test_path_prefixed_key(self):
        assert (
            build_works_url("/works/OL12345W")
            == "https://openlibrary.org/works/OL12345W.json"
        )

    def test_already_has_works_prefix(self):
        assert (
            build_works_url("works/OL12345W")
            == "https://openlibrary.org/works/OL12345W.json"
        )


class TestBuildEditionsUrl:
    def test_bare_key(self):
        assert (
            build_editions_url("OL12345W")
            == "https://openlibrary.org/works/OL12345W/editions.json"
        )

    def test_path_prefixed_key(self):
        assert (
            build_editions_url("/works/OL12345W")
            == "https://openlibrary.org/works/OL12345W/editions.json"
        )


class TestBuildAuthorUrl:
    def test_path_prefixed_key(self):
        assert (
            build_author_url("/authors/OL123A")
            == "https://openlibrary.org/authors/OL123A.json"
        )

    def test_bare_key(self):
        assert (
            build_author_url("OL123A")
            == "https://openlibrary.org/authors/OL123A.json"
        )

    def test_already_has_authors_prefix(self):
        assert (
            build_author_url("authors/OL123A")
            == "https://openlibrary.org/authors/OL123A.json"
        )


class TestExtractTitle:
    def test_normal(self, works_payload):
        assert extract_title(works_payload) == "Fantastic Mr Fox"

    def test_missing_raises(self):
        with pytest.raises(KeyError):
            extract_title({})


class TestExtractDescription:
    def test_dict_form(self, works_payload):
        assert (
            extract_description(works_payload)
            == "A fox outwits three farmers."
        )

    def test_string_form(self):
        assert (
            extract_description({"description": "Plain text."})
            == "Plain text."
        )

    def test_absent_returns_none(self):
        assert extract_description({}) is None

    def test_dict_missing_value_key(self):
        # dict without "value" → returns None
        assert (
            extract_description({"description": {"type": "/type/text"}})
            is None
        )


class TestExtractCoverUrl:
    def test_returns_url(self, works_payload):
        url = extract_cover_url(works_payload)
        assert url == "https://covers.openlibrary.org/b/id/8739161-L.jpg"

    def test_no_covers_returns_none(self):
        assert extract_cover_url({}) is None
        assert extract_cover_url({"covers": []}) is None

    def test_sentinel_minus_one_returns_none(self):
        assert extract_cover_url({"covers": [-1]}) is None

    def test_multiple_covers_uses_first(self):
        url = extract_cover_url({"covers": [111, 222]})
        assert "111" in url


class TestExtractAuthorKeys:
    def test_standard_shape(self, works_payload):
        keys = extract_author_keys(works_payload)
        assert keys == ["/authors/OL34184A"]

    def test_flat_shape(self):
        data = {"authors": [{"key": "/authors/OL99Z"}]}
        assert extract_author_keys(data) == ["/authors/OL99Z"]

    def test_empty_authors_field(self):
        assert extract_author_keys({"authors": []}) == []

    def test_absent_authors_field(self):
        assert extract_author_keys({}) == []

    def test_multiple_authors(self):
        data = {
            "authors": [
                {"author": {"key": "/authors/OL1A"}},
                {"author": {"key": "/authors/OL2A"}},
            ]
        }
        assert extract_author_keys(data) == ["/authors/OL1A", "/authors/OL2A"]


# ---------------------------------------------------------------------------
# extract_isbn
# ---------------------------------------------------------------------------


class TestExtractIsbn:
    def test_prefers_isbn13(self, editions_payload):
        assert extract_isbn(editions_payload) == "9780142410349"

    def test_falls_back_to_isbn10(self):
        data = {"entries": [{"isbn_10": ["0140328726"]}]}
        assert extract_isbn(data) == "0140328726"

    def test_no_isbn_raises(self):
        with pytest.raises(ValueError, match="No ISBN"):
            extract_isbn({"entries": []})

    def test_skips_empty_entries(self):
        data = {"entries": [{}, {"isbn_13": ["9781234567890"]}]}
        assert extract_isbn(data) == "9781234567890"

    def test_absent_entries_raises(self):
        with pytest.raises(ValueError):
            extract_isbn({})


# ---------------------------------------------------------------------------
# extract_publication_year
# ---------------------------------------------------------------------------


class TestExtractPublicationYear:
    def test_returns_earliest(self, editions_payload):
        # 2007 and 1996 present; expects 1996
        assert extract_publication_year(editions_payload) == 1996

    def test_four_digit_year_only(self):
        data = {"entries": [{"publish_date": "2001"}]}
        assert extract_publication_year(data) == 2001

    def test_month_year_string(self):
        data = {"entries": [{"publish_date": "March 1999"}]}
        assert extract_publication_year(data) == 1999

    def test_no_date_returns_none(self):
        assert extract_publication_year({"entries": [{}]}) is None

    def test_empty_entries(self):
        assert extract_publication_year({"entries": []}) is None

    def test_unparsable_date_returns_none(self):
        data = {"entries": [{"publish_date": "unknown"}]}
        assert extract_publication_year(data) is None


# ---------------------------------------------------------------------------
# extract_page_count
# ---------------------------------------------------------------------------


class TestExtractPageCount:
    def test_returns_first_nonzero(self, editions_payload):
        assert extract_page_count(editions_payload) == 96

    def test_skips_zero(self):
        data = {"entries": [{"number_of_pages": 0}, {"number_of_pages": 200}]}
        assert extract_page_count(data) == 200

    def test_absent_returns_none(self):
        assert extract_page_count({"entries": [{}]}) is None

    def test_string_pages_coerced(self):
        data = {"entries": [{"number_of_pages": "320"}]}
        assert extract_page_count(data) == 320


# ---------------------------------------------------------------------------
# extract_author_id
# ---------------------------------------------------------------------------


class TestExtractAuthorId:
    def test_path_prefixed(self):
        assert extract_author_id("/authors/OL123A") == "OL123A"

    def test_bare(self):
        assert extract_author_id("OL123A") == "OL123A"


class TestExtractAuthorName:
    def test_name_field(self, author_payload):
        assert extract_author_name(author_payload) == "Roald Dahl"

    def test_personal_name_fallback(self):
        assert (
            extract_author_name({"personal_name": "J.R.R. Tolkien"})
            == "J.R.R. Tolkien"
        )

    def test_neither_raises(self):
        with pytest.raises(KeyError):
            extract_author_name({})


class TestParseAuthor:
    def test_returns_author_data(self, author_payload):
        result = parse_author("/authors/OL34184A", author_payload)
        assert isinstance(result, AuthorData)
        assert result.author_name == "Roald Dahl"
        assert result.author_openlibrary_id == "OL34184A"
