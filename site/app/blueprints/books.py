"""Blueprint for /books"""

from flask import Blueprint

books_bp = Blueprint("books", __name__)


@books_bp.route("/", methods=["GET"])
def book_list():
    return "hello world"


if __name__ == "__main__":
    pass
