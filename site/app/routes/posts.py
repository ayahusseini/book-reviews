"""Routes for Markdown-backed posts."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, render_template

from app.backend.markdown import render_markdown_to_safe_html
from app.backend.models import Post

from app.extensions import cache

posts_bp = Blueprint("posts", __name__)

SHOWN_IN_POSTS = {"review", "essay", "standalone", "note", "til"}
NEW_POST_DAYS = 2
HEATMAP_WEEKS = 13

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


def _post_frequency(posts: list[Post]) -> dict[date, int]:
    """Return a {date: count} mapping of posts by publication date."""
    return Counter(
        p.post_created_at.date()
        for p in posts
        if p.post_created_at is not None
    )


def _heatmap_cells(
    frequency: dict[date, int],
) -> list[tuple[date, int, int]]:
    """Return ordered (date, count, level) cells for a HEATMAP_WEEKS-wide grid.

    Starts on the Monday HEATMAP_WEEKS before today, ends today.
    Level encodes intensity for the CSS data-level attribute:
      0 = no posts, 1 = 1 post, 2 = 2 posts, 3 = 3+
    """
    today = date.today()
    start = today - timedelta(weeks=HEATMAP_WEEKS)
    start -= timedelta(days=start.weekday())  # rewind to Monday

    cells = []
    d = start
    while d <= today:
        count = frequency.get(d, 0)
        level = (
            0 if count == 0 else 1 if count == 1 else 2 if count == 2 else 3
        )
        cells.append((d, count, level))
        d += timedelta(days=1)
    return cells


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

    frequency = _post_frequency(posts)
    return render_template(
        "posts.html",
        grouped_posts=_group_posts(posts),
        new_slugs=_new_slugs(posts),
        heatmap_cells=_heatmap_cells(frequency),
    )


@posts_bp.route("/<string:slug>", methods=["GET"])
@cache.cached()
def post_detail(slug: str):
    post = Post.query.filter_by(post_slug=slug).first()
    if not post:
        abort(404)
    post_html = render_markdown_to_safe_html(post.post_body_markdown)
    return render_template("post_detail.html", post=post, post_html=post_html)
