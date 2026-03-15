"""Script which contains helper functions for converting
BookData and AuthorData
Dataclasses into entries within the SQLAlchemy database
"""

from flask_sqlalchemy import SQLAlchemy
from app.database.models import AuthorData, Author


def is_author_in_db(db: SQLAlchemy, author_openlibrary_id: str):
    """Returns True if an author_id is currently in the database"""


def create_author(author_data: AuthorData, db: SQLAlchemy) -> Author:
    """Create a new author, if one doesn't already exist"""
    pass
