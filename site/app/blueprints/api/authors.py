"""
API blueprint: /api/authors

Routes
------
GET  /api/authors/<author_id>    Return a single author as JSON.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Author

authors_bp = Blueprint("authors", __name__, url_prefix="/authors")


@authors_bp.route("/<int:author_id>", methods=["GET"])
def get_author(author_id: int):
    """
    Return a single author by ID.

    Responses
    ---------
    200  Author found.
    404  No author found with author_id.
    """
    author = db.session.get(Author, author_id)
    if author is None:
        return jsonify({"error": f"No author found with id {author_id}."}), 404

    return jsonify(author.to_dict()), 200
