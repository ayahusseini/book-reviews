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
from app.database.models import Author, Book

SEED = "app/database/book_seed.json"


def is_author_in_db(ol_id: str):
    """Returns True if an author's OL ID is currently in the database"""
    author = Author.query.filter_by(author_openlibrary_id=ol_id).first()
    return bool(author)


def is_book_in_db(ol_id: str):
    """Returns True if an author's identifier is currently in the database"""
    book = Book.query.filter_by(book_ol_key=ol_id).first()

    return bool(book)


def add_by_ol_id(db: SQLAlchemy, seed_data: list[dict]):
    """
    Batch adds a list of books to the session and commits.
    Books are defined by seed data dicts with 'olid' and optional fields.
    """
    books = []
    for item in seed_data:
        olid = item["olid"]
        if not is_book_in_db(olid):
            print(f"Fetching data for {olid}")
            book = fetch_book_data(olid)
            # Override with seed data if provided
            if "rating" in item:
                book.book_rating = item["rating"]
            if "description" in item:
                book.book_description = item["description"]
            # Merge authors to handle existing ones and avoid duplicates
            merged_authors = []
            for author in book.authors:
                merged_authors.append(db.session.merge(author))
            book.authors = merged_authors
            books.append(book)
    if books:
        db.session.add_all(books)
        db.session.commit()
        print(f"Added {len(books)} new books")


if __name__ == "__main__":
    with open(SEED, "r") as f:
        seeds = json.load(f)

    a = create_app()
    with a.app_context():
        add_by_ol_id(db, seeds)
