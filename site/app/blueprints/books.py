"""Blueprint for /books"""

from flask import Blueprint

books_bp = Blueprint("books", __name__)


@books_bp.route("/books", methods=["GET"])
def mainbooks():
    return "hello world"


if __name__ == "__main__":
    pass
