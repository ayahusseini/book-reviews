"""
API blueprint: /api/books

Routes
------
POST  /api/books/import       Import a book from Open Library into the DB.
PATCH /api/books/<book_id>    Overwrite an existing book's fields
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from requests import HTTPError, Timeout
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Author, Book, BookAuthorMapping
from app.open_library import BookData, fetch_book_data

books_bp = Blueprint("books", __name__, url_prefix="/books")


def get_or_create_author(author_data) -> Author:
    """
    Return an existing Author row matching author_openlibrary_id,
    or insert and return a new one.
    """
    author = Author.query.filter_by(
        author_openlibrary_id=author_data.author_openlibrary_id
    ).first()
    if author is None:
        author = Author(
            author_name=author_data.author_name,
            author_openlibrary_id=author_data.author_openlibrary_id,
        )
        db.session.add(author)
    return author


def apply_book_fields(book: Book, data: BookData) -> None:
    """Write all scalar fields from data onto book (in-place)."""
    book.book_title = data.book_title
    book.book_isbn = data.book_isbn
    book.book_description = data.book_description
    book.book_publication_year = data.book_publication_year
    book.book_cover_url = data.book_cover_url
    book.book_page_count = data.book_page_count


def sync_authors(book: Book, data: BookData) -> None:
    """
    Replace book's author associations with those in data.

    Existing Author rows are reused; only the junction rows are replaced.
    """
    BookAuthorMapping.query.filter_by(book_id=book.book_id).delete()

    for author_data in data.authors:
        author = get_or_create_author(author_data)
        db.session.flush()  # ensure author.author_id is populated
        mapping = BookAuthorMapping(
            book_id=book.book_id, author_id=author.author_id
        )
        db.session.add(mapping)


def fetch_or_error(ol_works_key: str):
    """
    Call fetch_book_data and return (BookData, None) on success,
    or (None, (response, status_code)) on failure.
    """
    try:
        return fetch_book_data(ol_works_key), None
    except Timeout:
        return None, (
            jsonify({"error": "Open Library request timed out."}),
            504,
        )
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        return None, (
            jsonify({"error": f"Open Library returned HTTP {status}."}),
            status,
        )
    except ValueError as exc:
        return None, (jsonify({"error": str(exc)}), 422)


@books_bp.route("/import", methods=["POST"])
def import_book():
    """
    Import a book from Open Library.

    Request body (JSON)
    -------------------
    { "ol_works_key": "OL45804W" }

    """
    body = request.get_json(silent=True) or {}
    ol_works_key = body.get("ol_works_key", "").strip()

    if not ol_works_key:
        return jsonify({"error": "'ol_works_key' is required."}), 400

    book_data, err = fetch_or_error(ol_works_key)
    if err:
        return err

    if Book.query.filter_by(book_isbn=book_data.book_isbn).first():
        return jsonify(
            {
                "error": "Book with ISBN"
                + "{book_data.book_isbn!r} already exists."
            }
        ), 409

    try:
        book = Book()
        apply_book_fields(book, book_data)
        db.session.add(book)
        db.session.flush()  # populate book.book_id before sync_authors

        sync_authors(book, book_data)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(
            {
                "error": "Database integrity error"
                + " — possible duplicate ISBN."
            }
        ), 409

    return jsonify(book.to_dict()), 201


@books_bp.route("/<int:book_id>", methods=["PATCH"])
def patch_book(book_id: int):
    """
    Re-fetch a book from Open Library and overwrite all its fields.

    Request body (JSON)
    -------------------
    { "ol_works_key": "OL45804W" }
    """

    book = db.session.get(Book, book_id)

    if book is None:
        return jsonify({"error": f"No book found with id {book_id}."}), 404

    body = request.get_json(silent=True) or {}
    ol_works_key = body.get("ol_works_key", "").strip()

    if not ol_works_key:
        return jsonify({"error": "'ol_works_key' is required."}), 400

    book_data, err = fetch_or_error(ol_works_key)
    if err:
        return err
    try:
        apply_book_fields(book, book_data)
        sync_authors(book, book_data)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(
            {
                "error": "Database integrity error"
                + "— ISBN may conflict with another book."
            }
        ), 409

    return jsonify(book.to_dict()), 200
