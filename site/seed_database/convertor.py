"""Seed the database from book_seed.json using Open Library data."""

import json
from pathlib import Path

from flask_sqlalchemy import SQLAlchemy

from app import create_app
from seed_database.open_library import fetch_book_data
from app.database.models import Author, Book, Tag
from app.extensions import db

SEED = Path(__file__).parent / "book_seed.json"


def is_author_in_db(ol_id: str) -> bool:
    """Return True if an author with the given OL id exists in the database."""
    return bool(Author.query.filter_by(author_openlibrary_id=ol_id).first())


def is_book_in_db(ol_id: str) -> bool:
    """Return True if a book with the given OL key exists in the database."""
    return bool(Book.query.filter_by(book_ol_key=ol_id).first())


def normalize_tag(tag: str) -> str:
    """Lowercase and collapse internal whitespace in a tag string."""
    return " ".join(tag.strip().split()).lower()


def extract_tags(item: dict) -> list[str]:
    """Return a normalised, deduplicated list of tags from a seed item."""
    tags_val = item.get("tags", [])
    if isinstance(tags_val, str):
        tags_val = [tags_val]

    seen: set[str] = set()
    out: list[str] = []
    if isinstance(tags_val, list):
        for t in tags_val:
            if isinstance(t, str):
                norm = normalize_tag(t)
                if norm and norm not in seen:
                    seen.add(norm)
                    out.append(norm)
    return out


def upsert_tag(db: SQLAlchemy, tag_name: str) -> Tag:
    """Return existing tag by name, or create and stage a new one."""
    tag = Tag.query.filter_by(tag_name=tag_name).first()
    if tag:
        return tag
    tag = Tag(tag_name=tag_name)
    db.session.add(tag)
    return tag


def upsert_author(db: SQLAlchemy, author: Author) -> Author:
    """Return existing author by OL id, or stage the new one for insert."""
    if author.author_openlibrary_id:
        existing = Author.query.filter_by(
            author_openlibrary_id=author.author_openlibrary_id
        ).first()
        if existing:
            return existing
    db.session.add(author)
    return author


def attach_tags(db: SQLAlchemy, book: Book, tags: list[str]) -> None:
    """Add any missing tags to the book, creating tags that don't exist yet."""
    existing = {t.tag_name for t in book.tags}
    for tag_name in tags:
        if tag_name not in existing:
            book.tags.append(upsert_tag(db, tag_name))
            existing.add(tag_name)


def add_by_ol_id(db: SQLAlchemy, seed_data: list[dict]) -> None:
    """Upsert books from a list of seed dicts and commit to the database."""
    books_added = 0
    books_updated = 0

    for item in seed_data:
        olid = item["olid"]
        book = Book.query.filter_by(book_ol_key=olid).first()

        is_new = book is None
        if is_new:
            print(f"Fetching data for {olid}")
            book = fetch_book_data(olid)
            book.authors = [upsert_author(db, a) for a in book.authors]
            db.session.add(book)
            books_added += 1
        else:
            books_updated += 1

        if "description" in item:
            book.book_description = item["description"]

        attach_tags(db, book, extract_tags(item))

    db.session.commit()
    print(f"Seeded books: added={books_added} updated={books_updated}")


if __name__ == "__main__":
    with open(SEED, "r") as f:
        seeds = json.load(f)

    app = create_app()
    with app.app_context():
        add_by_ol_id(db, seeds)
