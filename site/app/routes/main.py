"""Routes for / (home, about, random quote)."""

import random

from flask import Blueprint, redirect, url_for, render_template, jsonify

from app.backend.models import Quote
from app.backend.markdown import render_markdown_to_safe_html
from app.extensions import cache
from app.routes.helper import all_heatmap_cells

main_bp = Blueprint("homepage", __name__)


@main_bp.route("/", methods=["GET"], endpoint="home")
def index():
    return redirect(url_for("books.book_list"))


@main_bp.route("/about", methods=["GET"], endpoint="about")
def about():
    return render_template("about.html", heatmap_cells=all_heatmap_cells())


@cache.memoize()
def _get_all_rendered_quotes() -> list[tuple[str, str]]:
    """Fetch and render all quotes, returning (quote_html, source_html) pairs.

    Result is cached; cache is cleared on content import.
    """
    quotes = Quote.query.all()
    result = []
    for quote in quotes:
        quote_html = render_markdown_to_safe_html(quote.quote_text)
        book_url = url_for("books.book_detail", book_id=quote.book.book_id)
        source_html = f'— <a href="{book_url}">{quote.book.book_title}</a>'
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
