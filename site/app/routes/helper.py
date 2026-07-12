"""Contains helper queries on the SQLAlchemy database"""

from collections import Counter
from datetime import date, datetime, timezone, timedelta

from app.extensions import db, cache
from app.backend.models import Book, Poem

NEW_POST_DAYS = 5
HEATMAP_WEEKS = 26


@cache.cached()
def recently_reviewed_book_ids() -> set[int]:
    """Return book_ids whose review was created within NEW_POST_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return {
        row.book_id
        for row in db.session.query(Book.book_id)
        .filter(Book.review_created_at >= cutoff)
        .all()
    }


@cache.cached()
def recently_created_poem_ids() -> set[int]:
    """Return poem_ids of poems created within NEW_POST_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return {
        row.poem_id
        for row in db.session.query(Poem.poem_id)
        .filter(Poem.poem_created_at >= cutoff)
        .all()
    }


def _frequency(created_dates: list[datetime]) -> dict[date, int]:
    """Return a {date: count} mapping of creation dates."""
    return Counter(d.date() for d in created_dates if d is not None)


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
    """Return heatmap cells across books (reviews) and poems."""
    review_dates = [
        row.review_created_at
        for row in db.session.query(Book.review_created_at)
        .filter(Book.review_created_at.isnot(None))
        .all()
    ]
    poem_dates = [
        row.poem_created_at
        for row in db.session.query(Poem.poem_created_at)
        .filter(Poem.poem_created_at.isnot(None))
        .all()
    ]
    return heatmap_cells(_frequency(review_dates + poem_dates))
