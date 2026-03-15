"""Script which contains helper functions for converting
different formats
into entries within the SQLAlchemy database
"""

from flask_sqlalchemy import SQLAlchemy
from app.extensions import db
from app import create_app
from app.database.open_library import fetch_book_data
from app.database.models import Author, Book

SEED = "app/database/book_olid_seed.txt"


def is_author_in_db(ol_id: str):
    """Returns True if an author's OL ID is currently in the database"""
    author = Author.query.filter_by(author_openlibrary_id=ol_id).first()
    return bool(author)


def is_book_in_db(ol_id: str):
    """Returns True if an author's identifier is currently in the database"""
    book = Book.query.filter_by(book_ol_key=ol_id).first()

    return bool(book)


def add_by_ol_id(db: SQLAlchemy, ol_ids: list[str]):
    """
    Batch adds a list of books to the session and commits.
    Books are defined by ol_id
    """
    books = []
    for olid in ol_ids:
        if not is_book_in_db(olid):
            books.append(fetch_book_data(olid))
    db.session.bulk_save_objects(books)
    db.session.commit()


if __name__ == "__main__":
    seeds = []
    with open(SEED, "r") as f:
        for line in f.readlines():
            if line.strip():
                seeds.append(line.strip())

    a = create_app()
    with a.app_context():
        add_by_ol_id(db, seeds)
