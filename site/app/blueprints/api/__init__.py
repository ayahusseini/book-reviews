"""API blueprint — all routes are prefixed /api"""

from .authors import authors_bp
from .books import books_bp
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")
api_bp.register_blueprint(books_bp)
api_bp.register_blueprint(authors_bp)
