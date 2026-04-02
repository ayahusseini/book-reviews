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


def get_random_quote_data():
    quotes = Post.query.filter_by(post_type="quotes").all()
    if not quotes:
        return None, None, None

    random_quote = random.choice(quotes)
    quote_html = render_markdown_to_safe_html(random_quote.post_body_markdown)

    source_html = ""

    if random_quote.book:
        book_url = url_for(
            "books.book_detail", book_id=random_quote.book.book_id
        )
        source_html = (
            f'— <a href="{book_url}">{random_quote.book.book_title}</a>'
        )
    elif random_quote.parent:
        parent_url = url_for(
            "posts.post_detail", slug=random_quote.parent.post_slug
        )
        source_html = (
            f'— <a href="{parent_url}">{random_quote.parent.post_title}</a>'
        )

    return random_quote, quote_html, source_html


@main_bp.route("/random-quote", methods=["GET"])
def random_quote():
    _, quote_html, source_html = get_random_quote_data()
    return jsonify(
        {"quote_html": quote_html or "", "source": source_html or ""}
    )
