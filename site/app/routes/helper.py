"""Contains helper queries on the SQLAlchemy database"""

from collections import Counter
from datetime import date, datetime, timezone, timedelta

from app.extensions import db, cache
from app.backend.models import Post

NEW_POST_DAYS = 5
HEATMAP_WEEKS = 13


@cache.cached()
def recently_created() -> list:
    """Return (book_id, post_id, post_type) rows for recent posts."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return (
        db.session.query(Post.book_id, Post.post_id, Post.post_type)
        .filter(Post.post_created_at >= cutoff)
        .distinct()
        .all()
    )


def recently_reviewed_book_ids() -> set[int]:
    """Return book_ids whose review post was created within NEW_POST_DAYS."""
    return {
        row.book_id
        for row in recently_created()
        if row.post_type == "review" and row.book_id is not None
    }


def recently_created_poem_ids() -> set[int]:
    """Return post_ids of poem posts created within NEW_POST_DAYS."""
    return {
        row.post_id for row in recently_created() if row.post_type == "poem"
    }


def post_frequency(posts: list[Post]) -> dict[date, int]:
    """Return a {date: count} mapping of posts by publication date."""
    return Counter(
        p.post_created_at.date()
        for p in posts
        if p.post_created_at is not None
    )


def heatmap_cells(
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


@cache.cached()
def all_heatmap_cells() -> list[tuple[date, int, int]]:
    """Return heatmap cells across all post types."""
    posts = Post.query.filter(Post.post_created_at.isnot(None)).all()
    return heatmap_cells(post_frequency(posts))
