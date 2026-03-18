"""Blueprint for /books."""

from __future__ import annotations

from flask import Blueprint, Response, abort, render_template, request
import requests

from app.database.models import Book, Post, Tag
from content.markdown_posts import render_markdown_to_safe_html

books_bp = Blueprint("books", __name__)


@books_bp.route("/", methods=["GET"])
def book_list():
    """Render the full book list,
    split into current year and previous reads."""
    tag_2026 = Tag.query.filter_by(tag_name="2026").first()
    books_2026 = []
    if tag_2026:
        books_2026 = (
            Book.query.filter(Book.tags.any(Tag.tag_id == tag_2026.tag_id))
            .order_by(Book.book_title.asc())
            .all()
        )

    books_previous = (
        Book.query.filter(~Book.tags.any(Tag.tag_name == "2026"))
        .order_by(Book.book_title.asc())
        .all()
    )

    return render_template(
        "books.html", books_2026=books_2026, books_previous=books_previous
    )


@books_bp.route("/<int:book_id>", methods=["GET"])
def book_detail(book_id: int):
    """Render the book detail page with all posts rendered to HTML."""
    book = Book.query.get_or_404(book_id)
    posts = (
        Post.query.filter_by(book_id=book.book_id)
        .order_by(Post.post_created_at.desc())
        .all()
    )
    rendered_posts = [
        (post, render_markdown_to_safe_html(post.post_body_markdown))
        for post in posts
    ]
    return render_template(
        "book_detail.html", book=book, rendered_posts=rendered_posts
    )


@books_bp.route("/cover/<int:cover_id>", methods=["GET"])
def cover_proxy(cover_id: int):
    """Proxy a book cover image from Open Library, caching for 24 hours."""
    size = (request.args.get("size") or "M").upper()
    if size not in {"S", "M", "L"}:
        size = "M"

    url = f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"
    try:
        upstream = requests.get(url, timeout=10)
    except requests.RequestException:
        abort(404)

    if upstream.status_code != 200 or not upstream.content:
        abort(404)

    content_type = upstream.headers.get("Content-Type", "image/jpeg")
    resp = Response(upstream.content, content_type=content_type)
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp
