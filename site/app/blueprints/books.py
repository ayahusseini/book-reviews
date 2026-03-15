"""Blueprint for /books"""

from flask import Blueprint, render_template
from app.database.models import Book

books_bp = Blueprint("books", __name__)


@books_bp.route("/", methods=["GET"])
def book_list():
    books = Book.query.all()
    print(books)
    return render_template("books.html", books=books)


@books_bp.route("/<int:book_id>", methods=["GET"])
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book)
