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


# Import the helper function - you can put this in a shared location
# For now, let's assume it's in the same blueprint file or imported


def get_random_quote_data():
    from flask import url_for

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
        book_title = random_quote.book.book_title
        source_html = f'— From book: <a href="{book_url}">{book_title}</a>'

    elif random_quote.post_type == "poem":
        poem_url = url_for("poems.poem_detail", slug=random_quote.post_slug)
        poem_title = random_quote.post_title or "Untitled"
        source_html = f'— From post: <a href="{poem_url}">{poem_title}</a>'

    else:
        post_url = url_for("posts.post_detail", slug=random_quote.post_slug)
        post_title = random_quote.post_title or "Untitled"
        source_html = f'— From post: <a href="{post_url}">{post_title}</a>'

    return random_quote, quote_html, source_html


# Your blueprint route (now simplified)
@main_bp.route("/random-quote", methods=["GET"])
def random_quote():
    _, quote_html, source_html = get_random_quote_data()
    return jsonify(
        {"quote_html": quote_html or "", "source": source_html or ""}
    )
