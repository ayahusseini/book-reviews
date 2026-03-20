"""Blueprint for Markdown-backed posts."""

from __future__ import annotations

from flask import Blueprint, abort, render_template

from content.markdown_posts import render_markdown_to_safe_html
from app.database.models import Post

from app.extensions import cache

posts_bp = Blueprint("posts", __name__)

SHOWN_IN_POSTS = {"review", "essay", "standalone", "note"}


@posts_bp.route("/", methods=["GET"])
@cache.cached()
def post_list():
    posts = Post.query.order_by(Post.post_created_at.desc()).all()
    return render_template("posts.html", posts=posts)


@posts_bp.route("/misc_posts", methods=["GET"])
@cache.cached()
def misc_post_list():
    posts = (
        Post.query.filter(
            Post.book_id.is_(None),
            Post.post_type.in_(SHOWN_IN_POSTS),
        )
        .order_by(Post.post_created_at.desc())
        .all()
    )
    return render_template("posts.html", posts=posts)


@posts_bp.route("/<string:slug>", methods=["GET"])
@cache.cached()
def post_detail(slug: str):
    post = Post.query.filter_by(post_slug=slug).first()
    if not post:
        abort(404)
    post_html = render_markdown_to_safe_html(post.post_body_markdown)
    return render_template("post_detail.html", post=post, post_html=post_html)
