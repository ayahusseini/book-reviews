from flask import Blueprint, redirect, url_for, render_template

main_bp = Blueprint("homepage", __name__)


@main_bp.route("/", methods=["GET"], endpoint="home")
def index():
    return redirect(url_for("books.book_list"))


@main_bp.route("/about", methods=["GET"], endpoint="about")
def about():
    return render_template("about.html")
