"""Tests for builder.heatmap."""

from datetime import date, datetime, timedelta, timezone

from builder.content import Book, Poem
from builder.heatmap import build_activity_heatmap


def make_book(review_created_at=None) -> Book:
    return Book(
        book_id="k",
        book_title="Title",
        book_description=None,
        book_publication_year=None,
        book_page_count=None,
        book_rating=None,
        book_date_read=None,
        review_created_at=review_created_at,
    )


def make_poem(poem_created_at=None) -> Poem:
    return Poem(
        poem_id="p",
        poem_slug="p",
        poem_title="Title",
        poem_author="Author",
        poem_body_markdown="body",
        poem_created_at=poem_created_at,
    )


def test_counts_one_post_on_its_creation_day():
    today = datetime.now(timezone.utc)
    books = [make_book(review_created_at=today)]

    cells = build_activity_heatmap(books, poems=[])

    today_cell = next(c for c in cells if c[0] == today.date())
    assert today_cell == (today.date(), 1, 1)


def test_counts_three_or_more_posts_as_level_3():
    today = datetime.now(timezone.utc)
    books = [make_book(review_created_at=today) for _ in range(3)]

    cells = build_activity_heatmap(books, poems=[])

    today_cell = next(c for c in cells if c[0] == today.date())
    assert today_cell == (today.date(), 3, 3)


def test_grid_spans_26_weeks_ending_today():
    cells = build_activity_heatmap(books=[], poems=[])

    assert cells[-1][0] == date.today()
    assert cells[0][0] == date.today() - timedelta(
        weeks=26, days=date.today().weekday()
    )


def test_ignores_books_and_poems_with_no_created_at():
    books = [make_book(review_created_at=None)]
    poems = [make_poem(poem_created_at=None)]

    cells = build_activity_heatmap(books, poems)

    assert all(count == 0 for _, count, _ in cells)
