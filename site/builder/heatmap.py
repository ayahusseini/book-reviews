"""Compute posting-activity heatmap cells for the about page."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from builder.content import Book, Poem

HEATMAP_WEEKS = 26


def collect_creation_dates(
    books: list[Book], poems: list[Poem]
) -> list[datetime]:
    """Return every review/poem creation datetime, skipping unset ones."""
    review_dates = [b.review_created_at for b in books if b.review_created_at]
    poem_dates = [p.poem_created_at for p in poems if p.poem_created_at]
    return review_dates + poem_dates


def count_posts_per_day(created_dates: list[datetime]) -> dict[date, int]:
    """Return a {date: count} mapping of creation dates."""
    return Counter(d.date() for d in created_dates)


def build_heatmap_cells(
    frequency: dict[date, int],
) -> list[tuple[date, int, int]]:
    """Return ordered (date, count, level) cells for a HEATMAP_WEEKS-wide grid.

    Starts on the Monday HEATMAP_WEEKS before today, ends today.
    Level encodes intensity for the CSS data-level attribute:
      0 = no posts, 1 = 1 post, 2 = 2 posts, 3 = 3+
    """
    today = date.today()
    start = today - timedelta(weeks=HEATMAP_WEEKS)
    start -= timedelta(days=start.weekday())

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


def build_activity_heatmap(
    books: list[Book], poems: list[Poem]
) -> list[tuple[date, int, int]]:
    """Return heatmap cells across all books (reviews) and poems."""
    dates = collect_creation_dates(books, poems)
    frequency = count_posts_per_day(dates)
    return build_heatmap_cells(frequency)
