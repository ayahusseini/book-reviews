from flask import Blueprint, redirect, url_for

main_bp = Blueprint("homepage", __name__)


@main_bp.route("/", methods=["GET"])
def index():
    return redirect(url_for("books.book_list"))
