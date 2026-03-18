"""
Script which contains helper functions for converting
different formats
into entries within the SQLAlchemy database
"""

import json
from flask_sqlalchemy import SQLAlchemy
from app.extensions import db
from app import create_app
from app.database.open_library import fetch_book_data
from app.database.models import Author, Book, Tag

SEED = "app/database/book_seed.json"


def is_author_in_db(ol_id: str):
    """Returns True if an author's OL ID is currently in the database"""
    author = Author.query.filter_by(author_openlibrary_id=ol_id).first()
    return bool(author)


def is_book_in_db(ol_id: str):
    """Returns True if an author's identifier is currently in the database"""
    book = Book.query.filter_by(book_ol_key=ol_id).first()

    return bool(book)


def _normalize_tag(tag: str) -> str:
    return " ".join(tag.strip().split()).lower()


def _extract_tags(item: dict) -> list[str]:
    tags_val = item.get("tags", [])
    if isinstance(tags_val, str):
        tags_val = [tags_val]
    tags: list[str] = []
    if isinstance(tags_val, list):
        for t in tags_val:
            if isinstance(t, str):
                norm = _normalize_tag(t)
                if norm:
                    tags.append(norm)
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _upsert_tag(db: SQLAlchemy, tag_name: str) -> Tag:
    tag = Tag.query.filter_by(tag_name=tag_name).first()
    if tag:
        return tag
    tag = Tag(tag_name=tag_name)
    db.session.add(tag)
    return tag


def _validate_rating(rating: object, *, key: str, olid: str) -> float:
    if not isinstance(rating, (int, float)):
        raise TypeError(f"{olid}: {key} must be a number, got {type(rating)}")
    rating_f = float(rating)
    if rating_f < 0 or rating_f > 5:
        raise ValueError(f"{olid}: {key} must be between 0 and 5")
    return rating_f


def add_by_ol_id(db: SQLAlchemy, seed_data: list[dict]):
    """
    Batch adds a list of books to the session and commits.
    Books are defined by seed data dicts with 'olid' and optional fields.
    """
    books = []
    for item in seed_data:
        olid = item["olid"]
        book = Book.query.filter_by(book_ol_key=olid).first()

        is_new = book is None
        if is_new:
            print(f"Fetching data for {olid}")
            book = fetch_book_data(olid)

        # Override with seed data if provided
        if "rating" in item:
            book.book_rating = _validate_rating(
                item["rating"], key="rating", olid=olid
            )
        if "description" in item:
            book.book_description = item["description"]

        # Tags: upsert + attach to book
        tags = _extract_tags(item)
        if tags:
            existing = {t.tag_name for t in book.tags}
            for tname in tags:
                if tname in existing:
                    continue
                tag = _upsert_tag(db, tname)
                book.tags.append(tag)
                existing.add(tname)

        if is_new:
            # Merge authors to handle existing ones and avoid duplicates
            merged_authors = []
            for author in book.authors:
                merged_authors.append(db.session.merge(author))
            book.authors = merged_authors
            books.append(book)

    if books:
        db.session.add_all(books)

    db.session.commit()
    print(
        "Seeded books: "
        + f"added={len(books)} "
        + f"updated={len(seed_data) - len(books)}"
    )


if __name__ == "__main__":
    with open(SEED, "r") as f:
        seeds = json.load(f)

    a = create_app()
    with a.app_context():
        add_by_ol_id(db, seeds)
