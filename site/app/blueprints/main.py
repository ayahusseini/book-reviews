from flask import Blueprint, redirect, url_for, render_template, jsonify
import random
from app.database.models import Post
from app.extensions import cache
from content.markdown_posts import render_markdown_to_safe_html

main_bp = Blueprint("homepage", __name__)


@main_bp.route("/", methods=["GET"], endpoint="home")
def index():
    return redirect(url_for("books.book_list"))


@main_bp.route("/about", methods=["GET"], endpoint="about")
def about():
    return render_template("about.html")


@cache.memoize()
def _get_all_rendered_quotes() -> list[tuple[str, str]]:
    """Fetch and render all quote posts,
    returning (quote_html, source_html) pairs.

    Result is cached; cache is cleared on content import.
    """
    quotes = Post.query.filter_by(post_type="quotes").all()
    result = []
    for quote in quotes:
        quote_html = render_markdown_to_safe_html(quote.post_body_markdown)
        source_html = ""
        if quote.book:
            book_url = url_for("books.book_detail", book_id=quote.book.book_id)
            source_html = f'— <a href="{book_url}">{quote.book.book_title}</a>'
        elif quote.parent:
            parent_url = url_for(
                "posts.post_detail", slug=quote.parent.post_slug
            )
            source_html = (
                f'— <a href="{parent_url}">{quote.parent.post_title}</a>'
            )
        result.append((quote_html, source_html))
    return result


def get_random_quote_data():
    all_quotes = _get_all_rendered_quotes()
    if not all_quotes:
        return None, None, None
    quote_html, source_html = random.choice(all_quotes)
    return True, quote_html, source_html


@main_bp.route("/random-quote", methods=["GET"])
def random_quote():
    _, quote_html, source_html = get_random_quote_data()
    return jsonify(
        {"quote_html": quote_html or "", "source": source_html or ""}
    )
