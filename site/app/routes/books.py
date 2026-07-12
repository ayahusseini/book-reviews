"""Routes for /books."""

from __future__ import annotations

from flask import Blueprint, render_template

from app.backend.models import Book, Tag
from app.extensions import cache, db
from app.backend.markdown import render_markdown_to_safe_html

from app.routes.helper import recently_reviewed_book_ids

books_bp = Blueprint("books", __name__)


def book_ids_with_reviews() -> set[int]:
    """Return book_ids that have a review."""
    return {
        row.book_id
        for row in Book.query.with_entities(Book.book_id)
        .filter(Book.review_markdown.isnot(None))
        .all()
    }


@books_bp.route("/", methods=["GET"])
@cache.cached()
def book_list():
    tag_2026 = Tag.query.filter_by(tag_name="read-2026").first()
    books_2026 = []
    if tag_2026:
        books_2026 = (
            Book.query.filter(Book.tags.any(Tag.tag_id == tag_2026.tag_id))
            .order_by(
                Book.review_updated_at.desc().nulls_last(),
                Book.book_title.asc(),
            )
            .all()
        )

    books_previous = (
        Book.query.filter(~Book.tags.any(Tag.tag_name == "read-2026"))
        .order_by(
            Book.review_updated_at.desc().nulls_last(), Book.book_title.asc()
        )
        .all()
    )

    return render_template(
        "books.html",
        books_2026=books_2026,
        books_previous=books_previous,
        has_posts=book_ids_with_reviews(),
        new_book_ids=recently_reviewed_book_ids(),
    )


@books_bp.route("/<int:book_id>", methods=["GET"])
@cache.cached()
def book_detail(book_id: int):
    """Render the book detail page with the review rendered to HTML."""
    book = db.get_or_404(Book, book_id)

    review_html = (
        render_markdown_to_safe_html(book.review_markdown)
        if book.review_markdown
        else None
    )

    return render_template(
        "book_detail.html", book=book, review_html=review_html
    )
