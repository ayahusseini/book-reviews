"""Blueprint for Markdown-backed posts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, render_template

from content.markdown_posts import render_markdown_to_safe_html
from app.database.models import Post

from app.extensions import cache

posts_bp = Blueprint("posts", __name__)

SHOWN_IN_POSTS = {"review", "essay", "standalone", "note", "til"}
NEW_POST_DAYS = 2

# Display order and labels for post type groups.
# Sections with no posts are omitted automatically.
TYPE_GROUPS: list[tuple[str, str]] = [
    ("til", "TODAY I LEARNED"),
    ("essay", "ESSAYS"),
    ("standalone", "POSTS"),
    ("note", "NOTES"),
    ("review", "REVIEWS"),
]


def _new_slugs(posts: list[Post]) -> set[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return {
        p.post_slug
        for p in posts
        if p.post_created_at is not None
        and p.post_created_at.replace(tzinfo=timezone.utc) >= cutoff
    }


def _group_posts(posts: list[Post]) -> list[tuple[str, list[Post]]]:
    """Return [(label, posts), ...] in TYPE_GROUPS order,
    skipping empty groups."""
    by_type: dict[str, list[Post]] = {}
    for post in posts:
        by_type.setdefault(post.post_type, []).append(post)

    return [
        (label, by_type[post_type])
        for post_type, label in TYPE_GROUPS
        if post_type in by_type
    ]


@posts_bp.route("/", methods=["GET"])
@cache.cached()
def post_list():
    posts = (
        Post.query.filter(Post.post_type.notin_({"code", "quotes"}))
        .order_by(Post.post_updated_at.desc())
        .all()
    )
    return render_template(
        "posts.html",
        grouped_posts=_group_posts(posts),
        new_slugs=_new_slugs(posts),
    )


@posts_bp.route("/misc_posts", methods=["GET"])
@cache.cached()
def misc_post_list():
    posts = (
        Post.query.filter(
            Post.book_id.is_(None),
            Post.post_type.in_(SHOWN_IN_POSTS),
        )
        .order_by(Post.post_updated_at.desc())
        .all()
    )
    return render_template(
        "posts.html",
        grouped_posts=_group_posts(posts),
        new_slugs=_new_slugs(posts),
    )


@posts_bp.route("/<string:slug>", methods=["GET"])
@cache.cached()
def post_detail(slug: str):
    post = Post.query.filter_by(post_slug=slug).first()
    if not post:
        abort(404)
    post_html = render_markdown_to_safe_html(post.post_body_markdown)
    return render_template("post_detail.html", post=post, post_html=post_html)
