"""Blueprint for /books."""

from __future__ import annotations

from flask import Blueprint, abort, render_template
from sqlalchemy import distinct, func, desc

from app.database.models import Book, Post, Tag
from app.extensions import db, cache
from content.markdown_posts import render_markdown_to_safe_html

books_bp = Blueprint("books", __name__)


def _book_ids_with_posts() -> set[int]:
    """Return the set of book_ids that have at least one non-quote post."""
    rows = (
        db.session.query(distinct(Post.book_id))
        .filter(
            Post.book_id.isnot(None),
            Post.post_type != "quotes",
        )
        .all()
    )
    return {row[0] for row in rows}


@books_bp.route("/", methods=["GET"])
@cache.cached()
def book_list():
    # Subquery: most recent non-quote post date per book
    latest_post = (
        db.session.query(
            Post.book_id, func.max(Post.post_updated_at).label("latest")
        )
        .filter(Post.post_type != "quotes")
        .group_by(Post.book_id)
        .subquery()
    )

    tag_2026 = Tag.query.filter_by(tag_name="2026").first()
    books_2026 = []
    if tag_2026:
        books_2026 = (
            Book.query.filter(Book.tags.any(Tag.tag_id == tag_2026.tag_id))
            .outerjoin(latest_post, Book.book_id == latest_post.c.book_id)
            .order_by(
                desc(latest_post.c.latest).nulls_last(), Book.book_title.asc()
            )
            .all()
        )

    books_previous = (
        Book.query.filter(~Book.tags.any(Tag.tag_name == "2026"))
        .outerjoin(latest_post, Book.book_id == latest_post.c.book_id)
        .order_by(
            desc(latest_post.c.latest).nulls_last(), Book.book_title.asc()
        )
        .all()
    )

    has_posts = _book_ids_with_posts()

    return render_template(
        "books.html",
        books_2026=books_2026,
        books_previous=books_previous,
        has_posts=has_posts,
    )


@books_bp.route("/<int:book_id>", methods=["GET"])
@cache.cached()
def book_detail(book_id: int):
    """Render the book detail page with all non-quote posts rendered to HTML.

    Returns 404 if the book exists but has no non-quote posts — there is
    nothing to show and the list page does not link here in that case.
    """
    book = Book.query.get_or_404(book_id)

    posts = (
        Post.query.filter_by(book_id=book.book_id)
        .filter(Post.post_type != "quotes")
        .order_by(Post.post_updated_at.desc())
        .all()
    )

    if not posts:
        abort(404)

    rendered_posts = [
        (post, render_markdown_to_safe_html(post.post_body_markdown))
        for post in posts
    ]
    return render_template(
        "book_detail.html", book=book, rendered_posts=rendered_posts
    )
