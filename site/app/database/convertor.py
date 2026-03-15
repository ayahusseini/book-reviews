"""Script which contains helper functions for converting
BookData and AuthorData
Dataclasses into entries within the SQLAlchemy database
"""

from flask_sqlalchemy import SQLAlchemy
from app.database.models import AuthorData, Author


def is_author_in_db(ol_id: str):
    """Returns True if an author's OL ID is currently in the database"""
    author = Author.query.filter_by(author_openlibrary_id=ol_id).first()
    return bool(author)


def create_author(author_data: AuthorData, db: SQLAlchemy) -> Author:
    """Create a new author, if one doesn't already exist"""
    pass
