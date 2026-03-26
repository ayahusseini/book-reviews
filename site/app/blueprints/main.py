from flask import Blueprint, redirect, url_for, render_template, jsonify
import random
from app.database.models import Post
from content.markdown_posts import render_markdown_to_safe_html

main_bp = Blueprint("homepage", __name__)


@main_bp.route("/", methods=["GET"], endpoint="home")
def index():
    return redirect(url_for("books.book_list"))


@main_bp.route("/about", methods=["GET"], endpoint="about")
def about():
    return render_template("about.html")


@main_bp.route("/random-quote", methods=["GET"])
def random_quote():
    quotes = Post.query.filter_by(post_type="quotes").all()
    if not quotes:
        return jsonify({"random_quote": "", "quote_html": ""})

    random_quote = random.choice(quotes)
    quote_html = render_markdown_to_safe_html(random_quote.post_body_markdown)

    return jsonify({"random_quote": random_quote, "quote_html": quote_html})
