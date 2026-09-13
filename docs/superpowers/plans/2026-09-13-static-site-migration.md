# Static Site Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Flask + SQLite + VPS stack with a static site: a pure-Python build script renders `writing/` content to plain HTML in `site/dist/`, deployed to Cloudflare Pages on every push.

**Architecture:** A new `site/builder/` package holds pure, DB-free content-loading, heatmap, and rendering logic (most of it ported unchanged from the current Flask app's `backend/` layer, which already has no Flask/DB coupling). `site/build.py` orchestrates it: load `writing/` → render templates with a standalone Jinja2 `Environment` → write static HTML + static assets + `quotes.json` to `site/dist/`. The old Flask app, SQLAlchemy models, Alembic migrations, and VPS deploy script are deleted once the new build is verified working.

**Tech Stack:** Python 3.13, Jinja2 (standalone, no Flask), `markdown` + `pymdown-extensions` + `bleach` (unchanged), `pyyaml` (unchanged), pytest.

**Spec:** [docs/superpowers/specs/2026-09-13-static-site-migration-design.md](../specs/2026-09-13-static-site-migration-design.md)

## Global Constraints

- In newly-written modules (`content.py`, `heatmap.py`, `render.py`, `build.py`) and their tests: no leading-underscore "private" function names, every function name starts with a verb. `markdown.py` and `extract_quotes.py` (Task 1) are moved unchanged from the existing, already-reviewed Flask app and keep their existing names (including the pre-existing `_expand_wikilinks`/`_heading_to_anchor` helpers) — this rule governs code we're writing now, not code we're relocating as-is.
- Functions are only extracted into their own name when it aids readability — no over-refactoring.
- Templates in `site/templates/` are moved byte-for-byte from `site/app/templates/` — the only template-adjacent change is registering a `url_for` shim in the Jinja environment, not editing template files.
- Book URLs use the `key` field from `book_seed.json` as the slug (`/books/<key>/`), not a numeric id.
- `book_seed.json` remains the book registry (source of truth for title/authors/rating/tags/etc.); reviews only contribute `body_markdown`, `date`, and extracted quotes.
- Every build starts from scratch (reads `writing/` fresh) — no incremental/upsert logic, no persisted state between builds.

---

### Task 1: `builder` package — move markdown parsing and quote extraction

**Files:**
- Create: `site/builder/__init__.py`
- Create: `site/builder/extract_quotes.py` (moved from `site/app/backend/extract_quotes.py`, unchanged — it has zero Flask/DB imports)
- Create: `site/builder/markdown.py` (moved from `site/app/backend/markdown.py`, one import updated)
- Test: `site/testing/test_extract_quotes.py` (moved from existing test of the same name, import path updated)
- Test: `site/testing/test_markdown_posts.py` (moved from existing test of the same name, import path updated)

**Interfaces:**
- Produces: `ExtractedQuote` (dataclass: `quote_text: str`, property `quote_slug: str`), `extract_ad_quotes(body: str) -> list[ExtractedQuote]`, `replace_ad_quotes_with_blockquotes(body: str) -> str` — from `builder.extract_quotes`.
- Produces: `MarkdownPost` (dataclass: `source_path`, `metadata`, `body_markdown`, `quotes`, properties `title`, `author`, `slug`, `book_key`, `date`), `parse_markdown_with_frontmatter(path: Path) -> MarkdownPost`, `render_markdown_to_safe_html(text: str) -> str` — from `builder.markdown`.

- [ ] **Step 1: Create the builder package and copy the two Flask-free modules**

```bash
mkdir -p site/builder
touch site/builder/__init__.py
cp site/app/backend/extract_quotes.py site/builder/extract_quotes.py
cp site/app/backend/markdown.py site/builder/markdown.py
```

- [ ] **Step 2: Update the one import in the copied `markdown.py`**

In `site/builder/markdown.py`, change:

```python
from app.backend.extract_quotes import (
    ExtractedQuote,
    extract_ad_quotes,
    replace_ad_quotes_with_blockquotes,
)
```

to:

```python
from builder.extract_quotes import (
    ExtractedQuote,
    extract_ad_quotes,
    replace_ad_quotes_with_blockquotes,
)
```

- [ ] **Step 3: Copy the existing tests for these two modules, updating imports**

```bash
cp site/testing/test_extract_quotes.py /tmp/test_extract_quotes_old.py
cp site/testing/test_markdown_posts.py /tmp/test_markdown_posts_old.py
```

Open `site/testing/test_extract_quotes.py` and `site/testing/test_markdown_posts.py` (already in place — these are the files pytest currently collects) and replace every `from app.backend.extract_quotes import ...` / `from app.backend.markdown import ...` with `from builder.extract_quotes import ...` / `from builder.markdown import ...`. No other changes — the functions being tested have identical signatures and behavior.

- [ ] **Step 4: Run the moved tests against the new location**

Run: `uv run pytest site/testing/test_extract_quotes.py site/testing/test_markdown_posts.py -v`
Expected: PASS (same tests, now importing from `builder` instead of `app.backend`)

- [ ] **Step 5: Commit**

```bash
git add site/builder site/testing/test_extract_quotes.py site/testing/test_markdown_posts.py
git commit -m "Move markdown parsing and quote extraction into builder package"
```

---

### Task 2: Content loading — join `book_seed.json` with review/poem files

**Files:**
- Create: `site/builder/content.py`
- Test: `site/testing/test_content.py`

**Interfaces:**
- Consumes: `MarkdownPost`, `parse_markdown_with_frontmatter` from `builder.markdown` (Task 1); `ExtractedQuote` from `builder.extract_quotes` (Task 1).
- Produces: `Author` (dataclass: `author_name: str`), `Tag` (dataclass: `tag_name: str`), `Book` (dataclass: `book_id: str`, `book_title: str`, `book_description: str | None`, `book_publication_year: int | None`, `book_page_count: int | None`, `book_rating: float | None`, `book_date_read: date | None`, `authors: list[Author]`, `tags: list[Tag]`, `review_markdown: str | None`, `review_created_at: datetime | None`, `quotes: list[ExtractedQuote]`), `Poem` (dataclass: `poem_id: str`, `poem_slug: str`, `poem_title: str`, `poem_author: str`, `poem_body_markdown: str`, `poem_created_at: datetime | None`), `parse_date_read(value: object) -> date | None`, `load_books(seed_path: Path, reviews_dir: Path) -> list[Book]`, `load_poems(poems_dir: Path) -> list[Poem]` — from `builder.content`. Later tasks (render.py, build.py) consume `Book`, `Poem`, `load_books`, `load_poems`.

- [ ] **Step 1: Write the failing tests**

Create `site/testing/test_content.py`:

```python
"""Tests for builder.content — joining book_seed.json with post files."""

from datetime import date, datetime, timezone

import pytest

from builder.content import (
    Author,
    Book,
    Tag,
    load_books,
    load_poems,
    parse_date_read,
)


def write_seed(tmp_path, entries):
    import json

    seed_path = tmp_path / "book_seed.json"
    seed_path.write_text(json.dumps(entries), encoding="utf-8")
    return seed_path


def write_review(reviews_dir, filename, frontmatter, body=""):
    reviews_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    (reviews_dir / filename).write_text(
        f"---\n{lines}\n---\n{body}", encoding="utf-8"
    )


def write_poem(poems_dir, filename, frontmatter, body=""):
    poems_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    (poems_dir / filename).write_text(
        f"---\n{lines}\n---\n{body}", encoding="utf-8"
    )


class TestParseDateRead:
    def test_parses_iso_date_string(self):
        assert parse_date_read("2026-03-10") == date(2026, 3, 10)

    def test_returns_none_for_none(self):
        assert parse_date_read(None) is None

    def test_raises_for_non_string(self):
        with pytest.raises(ValueError):
            parse_date_read(123)


class TestLoadBooks:
    def test_builds_book_with_no_review(self, tmp_path):
        seed_path = write_seed(
            tmp_path,
            [
                {
                    "key": "wuthering-heights",
                    "title": "Wuthering Heights",
                    "authors": ["Emily Bronte"],
                    "tags": ["classic"],
                    "rating": 4,
                }
            ],
        )
        reviews_dir = tmp_path / "reviews"

        books = load_books(seed_path, reviews_dir)

        assert books == [
            Book(
                book_id="wuthering-heights",
                book_title="Wuthering Heights",
                book_description=None,
                book_publication_year=None,
                book_page_count=None,
                book_rating=4,
                book_date_read=None,
                authors=[Author(author_name="Emily Bronte")],
                tags=[Tag(tag_name="classic")],
                review_markdown=None,
                review_created_at=None,
                quotes=[],
            )
        ]

    def test_joins_matching_review(self, tmp_path):
        seed_path = write_seed(
            tmp_path, [{"key": "wuthering-heights", "title": "Wuthering Heights"}]
        )
        reviews_dir = tmp_path / "reviews"
        write_review(
            reviews_dir,
            "wh.md",
            {
                "title": "Wuthering Heights",
                "author": "Aya",
                "book_key": "wuthering-heights",
                "date": "2026-03-10",
            },
            body="Opening thoughts...",
        )

        books = load_books(seed_path, reviews_dir)

        assert len(books) == 1
        book = books[0]
        assert book.review_markdown.strip() == "Opening thoughts..."
        assert book.review_created_at == datetime(
            2026, 3, 10, tzinfo=timezone.utc
        )

    def test_raises_for_seed_entry_missing_title(self, tmp_path):
        seed_path = write_seed(tmp_path, [{"key": "no-title"}])
        with pytest.raises(ValueError, match="title"):
            load_books(seed_path, tmp_path / "reviews")

    def test_raises_for_review_with_unknown_book_key(self, tmp_path):
        seed_path = write_seed(
            tmp_path, [{"key": "wuthering-heights", "title": "Wuthering Heights"}]
        )
        reviews_dir = tmp_path / "reviews"
        write_review(
            reviews_dir,
            "orphan.md",
            {
                "title": "Some Review",
                "author": "Aya",
                "book_key": "does-not-exist",
            },
        )
        with pytest.raises(ValueError, match="does-not-exist"):
            load_books(seed_path, reviews_dir)


class TestLoadPoems:
    def test_loads_poem_with_slug_from_frontmatter(self, tmp_path):
        poems_dir = tmp_path / "poetry"
        write_poem(
            poems_dir,
            "fire-and-ice.md",
            {
                "title": "Fire and Ice",
                "author": "Robert Frost",
                "slug": "fire-and-ice",
                "date": "2026-04-10",
            },
            body="Some say the world will end in fire.",
        )

        poems = load_poems(poems_dir)

        assert len(poems) == 1
        assert poems[0].poem_slug == "fire-and-ice"
        assert poems[0].poem_title == "Fire and Ice"

    def test_returns_empty_list_when_poems_dir_missing(self, tmp_path):
        assert load_poems(tmp_path / "does-not-exist") == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest site/testing/test_content.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'builder.content'`

- [ ] **Step 3: Implement `site/builder/content.py`**

```python
"""Load book and poem content from writing/ into plain data objects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from builder.extract_quotes import ExtractedQuote
from builder.markdown import MarkdownPost, parse_markdown_with_frontmatter


@dataclass
class Author:
    """A book author, as listed in book_seed.json."""

    author_name: str


@dataclass
class Tag:
    """A tag attached to a book, as listed in book_seed.json."""

    tag_name: str


@dataclass
class Book:
    """A book, joining its book_seed.json entry with its review file."""

    book_id: str
    book_title: str
    book_description: str | None
    book_publication_year: int | None
    book_page_count: int | None
    book_rating: float | None
    book_date_read: date | None
    authors: list[Author] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    review_markdown: str | None = None
    review_created_at: datetime | None = None
    quotes: list[ExtractedQuote] = field(default_factory=list)


@dataclass
class Poem:
    """A poem, parsed from a single markdown file."""

    poem_id: str
    poem_slug: str
    poem_title: str
    poem_author: str
    poem_body_markdown: str
    poem_created_at: datetime | None = None


def parse_date_read(value: object) -> date | None:
    """Parse an ISO date string from a seed entry, or return None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"date_read must be an ISO date string or null, got {value!r}"
        )
    return date.fromisoformat(value)


def load_book_seed(seed_path: Path) -> list[dict]:
    """Load and return the raw list of book entries from book_seed.json."""
    with open(seed_path) as f:
        return json.load(f)


def load_reviews(reviews_dir: Path) -> dict[str, MarkdownPost]:
    """Return {book_key: MarkdownPost} for every review under reviews_dir."""
    if not reviews_dir.exists():
        return {}
    reviews: dict[str, MarkdownPost] = {}
    for path in sorted(reviews_dir.rglob("*.md")):
        post = parse_markdown_with_frontmatter(path)
        if not post.book_key:
            raise ValueError(f"Review '{path}' has no book_key set.")
        reviews[post.book_key] = post
    return reviews


def build_book(entry: dict, review: MarkdownPost | None) -> Book:
    """Build a Book from one book_seed.json entry and its matching review."""
    key = entry.get("key")
    if not key:
        raise ValueError(f"Seed entry missing 'key': {entry}")
    title = entry.get("title")
    if not title:
        raise ValueError(f"Seed entry {key!r} missing required 'title'")

    return Book(
        book_id=key,
        book_title=title,
        book_description=entry.get("description"),
        book_publication_year=entry.get("publication_year"),
        book_page_count=entry.get("page_count"),
        book_rating=entry.get("rating"),
        book_date_read=parse_date_read(entry.get("date_read")),
        authors=[
            Author(author_name=name) for name in entry.get("authors", [])
        ],
        tags=[Tag(tag_name=name) for name in entry.get("tags", [])],
        review_markdown=review.body_markdown if review else None,
        review_created_at=review.date if review else None,
        quotes=review.quotes if review else [],
    )


def load_books(seed_path: Path, reviews_dir: Path) -> list[Book]:
    """Load all books, joining book_seed.json entries with their reviews."""
    reviews = load_reviews(reviews_dir)
    seed_keys = {entry.get("key") for entry in load_book_seed(seed_path)}

    unmatched = set(reviews) - seed_keys
    if unmatched:
        raise ValueError(
            f"Review(s) reference unknown book_key(s): {sorted(unmatched)}. "
            "Add them to book_seed.json first."
        )

    return [
        build_book(entry, reviews.get(entry.get("key")))
        for entry in load_book_seed(seed_path)
    ]


def build_poem(post: MarkdownPost) -> Poem:
    """Build a Poem from a parsed poem markdown file."""
    return Poem(
        poem_id=post.slug,
        poem_slug=post.slug,
        poem_title=post.title,
        poem_author=post.author,
        poem_body_markdown=post.body_markdown,
        poem_created_at=post.date,
    )


def load_poems(poems_dir: Path) -> list[Poem]:
    """Load all poems from poems_dir, one per markdown file.

    If two files produce the same slug, the one that sorts last by
    filename wins — matching the "last import wins" behavior documented
    in docs/writing-posts.md.
    """
    if not poems_dir.exists():
        return []
    poems_by_slug: dict[str, Poem] = {}
    for path in sorted(poems_dir.rglob("*.md")):
        poem = build_poem(parse_markdown_with_frontmatter(path))
        poems_by_slug[poem.poem_slug] = poem
    return list(poems_by_slug.values())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest site/testing/test_content.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add site/builder/content.py site/testing/test_content.py
git commit -m "Add builder.content: join book_seed.json with review/poem files"
```

---

### Task 3: Heatmap — posting-activity cells for the about page

**Files:**
- Create: `site/builder/heatmap.py`
- Test: `site/testing/test_heatmap.py`

**Interfaces:**
- Consumes: `Book`, `Poem` from `builder.content` (Task 2) — specifically their `review_created_at` / `poem_created_at` fields.
- Produces: `build_activity_heatmap(books: list[Book], poems: list[Poem]) -> list[tuple[date, int, int]]` — consumed by `render.py` (Task 4) and `build.py` (Task 5).

- [ ] **Step 1: Write the failing test**

Create `site/testing/test_heatmap.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest site/testing/test_heatmap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'builder.heatmap'`

- [ ] **Step 3: Implement `site/builder/heatmap.py`**

```python
"""Compute posting-activity heatmap cells for the about page."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from builder.content import Book, Poem

HEATMAP_WEEKS = 26


def collect_creation_dates(books: list[Book], poems: list[Poem]) -> list[datetime]:
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest site/testing/test_heatmap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add site/builder/heatmap.py site/testing/test_heatmap.py
git commit -m "Add builder.heatmap: posting-activity cells for the about page"
```

---

### Task 4: Templates/static move + render module

**Files:**
- Create: `site/templates/` (moved from `site/app/templates/`, byte-for-byte)
- Create: `site/static/` (moved from `site/app/static/`, byte-for-byte)
- Create: `site/builder/render.py`
- Test: `site/testing/test_render.py`

**Interfaces:**
- Consumes: `Book`, `Poem` from `builder.content` (Task 2); `build_activity_heatmap` result shape `list[tuple[date, int, int]]` from `builder.heatmap` (Task 3); `render_markdown_to_safe_html` from `builder.markdown` (Task 1).
- Produces: `resolve_url(endpoint: str, **kwargs: str) -> str`, `create_environment(templates_dir: Path, quotes: list[dict]) -> jinja2.Environment`, `write_page(output_dir: Path, url_path: str, html: str) -> None`, `copy_static_assets(static_dir: Path, output_dir: Path) -> None`, `collect_quotes(books: list[Book]) -> list[dict]`, `find_books_with_reviews(books: list[Book]) -> set[str]`, `find_recently_reviewed_book_ids(books: list[Book]) -> set[str]`, `find_recently_created_poem_ids(poems: list[Poem]) -> set[str]`, `split_books_by_year(books: list[Book], year: int) -> tuple[list[Book], list[Book]]`, `render_book_list_page`, `render_book_detail_page`, `render_poem_list_page`, `render_poem_detail_page`, `render_about_page` (each `(env, ...) -> str`) — consumed by `build.py` (Task 5).

- [ ] **Step 1: Move templates and static assets**

```bash
mkdir -p site/templates site/static
git mv site/app/templates/* site/templates/
git mv site/app/static/* site/static/
```

- [ ] **Step 2: Write the failing tests**

Create `site/testing/test_render.py`:

```python
"""Tests for builder.render."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from builder.content import Author, Book, Poem, Tag
from builder.render import (
    collect_quotes,
    copy_static_assets,
    create_environment,
    find_books_with_reviews,
    find_recently_reviewed_book_ids,
    render_about_page,
    render_book_detail_page,
    render_book_list_page,
    render_poem_detail_page,
    render_poem_list_page,
    resolve_url,
    split_books_by_year,
    write_page,
)

TEMPLATES_DIR = Path(__file__).parents[1] / "templates"
STATIC_DIR = Path(__file__).parents[1] / "static"


def make_book(**overrides) -> Book:
    defaults = dict(
        book_id="k",
        book_title="Title",
        book_description=None,
        book_publication_year=None,
        book_page_count=None,
        book_rating=None,
        book_date_read=None,
    )
    defaults.update(overrides)
    return Book(**defaults)


class TestResolveUrl:
    def test_static_endpoint(self):
        assert resolve_url("static", filename="style/style.css") == (
            "/static/style/style.css"
        )

    def test_book_detail_endpoint(self):
        assert resolve_url("books.book_detail", book_id="orbital") == (
            "/books/orbital/"
        )

    def test_unknown_endpoint_raises(self):
        with pytest.raises(ValueError):
            resolve_url("nonsense.endpoint")


class TestSplitBooksByYear:
    def test_splits_by_date_read_year(self):
        this_year = make_book(book_id="a", book_date_read=date(2026, 1, 1))
        last_year = make_book(book_id="b", book_date_read=date(2025, 1, 1))
        unread = make_book(book_id="c", book_date_read=None)

        current, previous = split_books_by_year(
            [this_year, last_year, unread], year=2026
        )

        assert current == [this_year]
        assert {b.book_id for b in previous} == {"b", "c"}


class TestFindBooksWithReviews:
    def test_only_includes_books_with_review_markdown(self):
        reviewed = make_book(book_id="a", review_markdown="text")
        unreviewed = make_book(book_id="b", review_markdown=None)

        assert find_books_with_reviews([reviewed, unreviewed]) == {"a"}


class TestFindRecentlyReviewedBookIds:
    def test_includes_recent_review(self):
        recent = make_book(
            book_id="a", review_created_at=datetime.now(timezone.utc)
        )
        old = make_book(
            book_id="b",
            review_created_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        )

        assert find_recently_reviewed_book_ids([recent, old]) == {"a"}


class TestCollectQuotes:
    def test_collects_quote_with_book_link(self):
        from builder.extract_quotes import ExtractedQuote

        book = make_book(
            book_id="orbital",
            book_title="Orbital",
            quotes=[ExtractedQuote(quote_text="A striking line.")],
        )

        quotes = collect_quotes([book])

        assert len(quotes) == 1
        assert quotes[0]["book_title"] == "Orbital"
        assert quotes[0]["book_url"] == "/books/orbital/"
        assert "striking line" in quotes[0]["quote_html"]


class TestWritePage:
    def test_writes_index_html_under_url_path(self, tmp_path):
        write_page(tmp_path, "/books/orbital/", "<h1>Orbital</h1>")

        written = tmp_path / "books" / "orbital" / "index.html"
        assert written.read_text() == "<h1>Orbital</h1>"


class TestCopyStaticAssets:
    def test_copies_static_dir_contents(self, tmp_path):
        copy_static_assets(STATIC_DIR, tmp_path)

        assert (tmp_path / "static" / "style" / "style.css").exists()


class TestRenderPages:
    def test_render_book_list_page_includes_reviewed_title(self):
        book = make_book(
            book_id="orbital",
            book_title="Orbital",
            review_markdown="text",
            review_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_book_list_page(env, [book], today=date(2026, 6, 1))

        assert "Orbital" in html
        assert '/books/orbital/"' in html

    def test_render_book_detail_page_renders_review_markdown(self):
        book = make_book(
            book_id="orbital",
            book_title="Orbital",
            authors=[Author(author_name="Samantha Harvey")],
            tags=[Tag(tag_name="fiction")],
            review_markdown="**Loved it.**",
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_book_detail_page(env, book)

        assert "Orbital" in html
        assert "Samantha Harvey" in html
        assert "<strong>Loved it.</strong>" in html

    def test_render_poem_list_page_links_to_poem(self):
        poem = Poem(
            poem_id="fire-and-ice",
            poem_slug="fire-and-ice",
            poem_title="Fire and Ice",
            poem_author="Robert Frost",
            poem_body_markdown="Some say the world will end in fire.",
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_poem_list_page(env, [poem])

        assert '/poems/fire-and-ice/"' in html

    def test_render_poem_detail_page_splits_comments_section(self):
        poem = Poem(
            poem_id="p",
            poem_slug="p",
            poem_title="P",
            poem_author="A",
            poem_body_markdown="The poem.\n\n---\n\nA note about it.",
        )
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_poem_detail_page(env, poem)

        assert "The poem." in html
        assert "A note about it." in html

    def test_render_about_page_includes_heatmap_grid(self):
        env = create_environment(TEMPLATES_DIR, quotes=[])

        html = render_about_page(env, heatmap_cells=[(date.today(), 1, 1)])

        assert "post-heatmap__grid" in html
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest site/testing/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'builder.render'`

- [ ] **Step 4: Implement `site/builder/render.py`**

```python
"""Render book/poem/about pages to static HTML using Jinja2."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from builder.content import Book, Poem
from builder.markdown import render_markdown_to_safe_html

NEW_POST_DAYS = 5


def resolve_url(endpoint: str, **kwargs: str) -> str:
    """Map a Flask-style endpoint name to a static site path.

    Registered under the name 'url_for' in the Jinja environment so the
    templates (written against Flask's url_for) need no changes.
    """
    if endpoint == "static":
        return f"/static/{kwargs['filename']}"
    if endpoint == "books.book_list":
        return "/books/"
    if endpoint == "books.book_detail":
        return f"/books/{kwargs['book_id']}/"
    if endpoint == "homepage.about":
        return "/about/"
    if endpoint == "poems.poem_list":
        return "/poems/"
    if endpoint == "poems.poem_detail":
        return f"/poems/{kwargs['slug']}/"
    raise ValueError(f"Unknown endpoint for static site: {endpoint}")


def collect_quotes(books: list[Book]) -> list[dict]:
    """Return [{quote_html, book_title, book_url}] for every book's quotes."""
    quotes = []
    for book in books:
        for quote in book.quotes:
            quotes.append(
                {
                    "quote_html": render_markdown_to_safe_html(
                        quote.quote_text
                    ),
                    "book_title": book.book_title,
                    "book_url": resolve_url(
                        "books.book_detail", book_id=book.book_id
                    ),
                }
            )
    return quotes


def create_environment(templates_dir: Path, quotes: list[dict]) -> Environment:
    """Create a standalone Jinja2 Environment for rendering templates."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["url_for"] = resolve_url
    env.globals["random_quote"] = bool(quotes)
    env.globals["random_quote_html"] = ""
    env.globals["random_quote_source"] = ""
    return env


def write_page(output_dir: Path, url_path: str, html: str) -> None:
    """Write rendered HTML to output_dir at the given url path.

    '/books/my-book/' is written to output_dir/books/my-book/index.html
    so links without a trailing filename resolve via directory indexes.
    """
    target = output_dir / url_path.strip("/") / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


def copy_static_assets(static_dir: Path, output_dir: Path) -> None:
    """Copy every file under static_dir into output_dir/static."""
    shutil.copytree(static_dir, output_dir / "static", dirs_exist_ok=True)


def find_books_with_reviews(books: list[Book]) -> set[str]:
    """Return book_ids that have a review."""
    return {b.book_id for b in books if b.review_markdown}


def find_recently_reviewed_book_ids(books: list[Book]) -> set[str]:
    """Return book_ids whose review was created within NEW_POST_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return {
        b.book_id
        for b in books
        if b.review_created_at and b.review_created_at >= cutoff
    }


def find_recently_created_poem_ids(poems: list[Poem]) -> set[str]:
    """Return poem_ids created within NEW_POST_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_POST_DAYS)
    return {
        p.poem_id
        for p in poems
        if p.poem_created_at and p.poem_created_at >= cutoff
    }


def sort_books_by_recency(books: list[Book]) -> list[Book]:
    """Sort books: most recently reviewed first, unreviewed last, title tiebreak."""

    def sort_key(book: Book) -> tuple[int, float, str]:
        if book.review_created_at is None:
            return (1, 0.0, book.book_title.lower())
        return (0, -book.review_created_at.timestamp(), book.book_title.lower())

    return sorted(books, key=sort_key)


def split_books_by_year(
    books: list[Book], year: int
) -> tuple[list[Book], list[Book]]:
    """Split books into (read this year, read previously/unread)."""
    this_year = [
        b for b in books if b.book_date_read and b.book_date_read.year == year
    ]
    previous = [
        b
        for b in books
        if not (b.book_date_read and b.book_date_read.year == year)
    ]
    return sort_books_by_recency(this_year), sort_books_by_recency(previous)


def render_book_list_page(
    env: Environment, books: list[Book], today: date
) -> str:
    """Render the /books/ list page."""
    books_this_year, books_previous = split_books_by_year(books, today.year)
    template = env.get_template("books.html")
    return template.render(
        books_2026=books_this_year,
        books_previous=books_previous,
        has_posts=find_books_with_reviews(books),
        new_book_ids=find_recently_reviewed_book_ids(books),
    )


def render_book_detail_page(env: Environment, book: Book) -> str:
    """Render a single /books/<key>/ detail page."""
    review_html = (
        render_markdown_to_safe_html(book.review_markdown)
        if book.review_markdown
        else None
    )
    template = env.get_template("book_detail.html")
    return template.render(book=book, review_html=review_html)


def render_poem_list_page(env: Environment, poems: list[Poem]) -> str:
    """Render the /poems/ list page."""
    ordered = sorted(
        poems,
        key=lambda p: p.poem_created_at or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True,
    )
    template = env.get_template("poems.html")
    return template.render(
        poems=ordered, new_poem_ids=find_recently_created_poem_ids(poems)
    )


def render_poem_detail_page(env: Environment, poem: Poem) -> str:
    """Render a single /poems/<slug>/ detail page."""
    parts = poem.poem_body_markdown.split("\n---\n", 1)
    poem_html = render_markdown_to_safe_html(parts[0])
    comments_html = (
        render_markdown_to_safe_html(parts[1]) if len(parts) > 1 else None
    )
    template = env.get_template("poem_detail.html")
    return template.render(
        poem=poem, poem_html=poem_html, comments_html=comments_html
    )


def render_about_page(
    env: Environment, heatmap_cells: list[tuple[date, int, int]]
) -> str:
    """Render the /about/ page."""
    template = env.get_template("about.html")
    return template.render(heatmap_cells=heatmap_cells)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest site/testing/test_render.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add site/templates site/static site/builder/render.py site/testing/test_render.py
git commit -m "Move templates/static and add builder.render"
```

---

### Task 5: `build.py` entry point

**Files:**
- Create: `site/build.py`
- Test: `site/testing/test_build.py`

**Interfaces:**
- Consumes: `load_books`, `load_poems` from `builder.content` (Task 2); `build_activity_heatmap` from `builder.heatmap` (Task 3); `collect_quotes`, `copy_static_assets`, `create_environment`, `render_about_page`, `render_book_detail_page`, `render_book_list_page`, `render_poem_detail_page`, `render_poem_list_page`, `write_page` from `builder.render` (Task 4).
- Produces: `build_site(seed_path, posts_dir, templates_dir, static_dir, output_dir) -> None` — the full site build, used directly by the `make build` target added in Task 7.

- [ ] **Step 1: Write the failing integration test**

Create `site/testing/test_build.py`:

```python
"""End-to-end test: build a small fixture writing/ dir into a static site."""

import json
from pathlib import Path

from build import build_site

FIXTURE_TEMPLATES_DIR = Path(__file__).parents[1] / "templates"
FIXTURE_STATIC_DIR = Path(__file__).parents[1] / "static"


def write_fixture_content(tmp_path: Path) -> tuple[Path, Path]:
    seed_path = tmp_path / "book_seed.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "key": "orbital",
                    "title": "Orbital",
                    "authors": ["Samantha Harvey"],
                    "rating": 2,
                    "date_read": "2026-04-01",
                },
                {"key": "unread-book", "title": "Unread Book"},
            ]
        ),
        encoding="utf-8",
    )

    posts_dir = tmp_path / "posts"
    reviews_dir = posts_dir / "reviews"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "orbital.md").write_text(
        "---\n"
        'title: "Orbital"\n'
        'author: "Aya"\n'
        'book_key: "orbital"\n'
        "date: 2026-04-02\n"
        "---\n\n"
        "I really did not like this book.\n",
        encoding="utf-8",
    )

    poetry_dir = posts_dir / "poetry"
    poetry_dir.mkdir(parents=True)
    (poetry_dir / "fire-and-ice.md").write_text(
        "---\n"
        "title: Fire and Ice\n"
        "author: Robert Frost\n"
        "slug: fire-and-ice\n"
        "date: 2026-04-10\n"
        "---\n"
        "Some say the world will end in fire.\n",
        encoding="utf-8",
    )

    return seed_path, posts_dir


def test_build_site_writes_expected_pages(tmp_path):
    seed_path, posts_dir = write_fixture_content(tmp_path)
    output_dir = tmp_path / "dist"

    build_site(
        seed_path=seed_path,
        posts_dir=posts_dir,
        templates_dir=FIXTURE_TEMPLATES_DIR,
        static_dir=FIXTURE_STATIC_DIR,
        output_dir=output_dir,
    )

    assert (output_dir / "books" / "index.html").exists()
    assert (output_dir / "books" / "orbital" / "index.html").exists()
    assert (output_dir / "books" / "unread-book" / "index.html").exists()
    assert (output_dir / "poems" / "index.html").exists()
    assert (
        output_dir / "poems" / "fire-and-ice" / "index.html"
    ).exists()
    assert (output_dir / "about" / "index.html").exists()
    assert (output_dir / "static" / "style" / "style.css").exists()
    assert (output_dir / "_redirects").read_text() == "/ /books/ 301\n"

    quotes = json.loads((output_dir / "quotes.json").read_text())
    assert isinstance(quotes, list)

    book_detail_html = (
        output_dir / "books" / "orbital" / "index.html"
    ).read_text()
    assert "did not like this book" in book_detail_html


def test_build_site_clears_previous_output(tmp_path):
    seed_path, posts_dir = write_fixture_content(tmp_path)
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    stale_file = output_dir / "stale.html"
    stale_file.write_text("old", encoding="utf-8")

    build_site(
        seed_path=seed_path,
        posts_dir=posts_dir,
        templates_dir=FIXTURE_TEMPLATES_DIR,
        static_dir=FIXTURE_STATIC_DIR,
        output_dir=output_dir,
    )

    assert not stale_file.exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest site/testing/test_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build'`

- [ ] **Step 3: Implement `site/build.py`**

```python
"""Build the static site: reads writing/ and renders site/dist/."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from builder.content import load_books, load_poems
from builder.heatmap import build_activity_heatmap
from builder.render import (
    collect_quotes,
    copy_static_assets,
    create_environment,
    render_about_page,
    render_book_detail_page,
    render_book_list_page,
    render_poem_detail_page,
    render_poem_list_page,
    write_page,
)

SITE_ROOT = Path(__file__).parent
REPO_ROOT = SITE_ROOT.parent
DEFAULT_SEED_PATH = REPO_ROOT / "writing" / "book_seed.json"
DEFAULT_POSTS_DIR = REPO_ROOT / "writing" / "posts"
DEFAULT_TEMPLATES_DIR = SITE_ROOT / "templates"
DEFAULT_STATIC_DIR = SITE_ROOT / "static"
DEFAULT_OUTPUT_DIR = SITE_ROOT / "dist"


def clear_output_dir(output_dir: Path) -> None:
    """Remove any previous build output and recreate the directory."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)


def write_redirects_file(output_dir: Path) -> None:
    """Write Cloudflare Pages' _redirects file for the / -> /books/ redirect."""
    (output_dir / "_redirects").write_text("/ /books/ 301\n", encoding="utf-8")


def write_quotes_json(output_dir: Path, quotes: list[dict]) -> None:
    """Write every extracted quote to a static JSON file for client-side use."""
    (output_dir / "quotes.json").write_text(
        json.dumps(quotes, indent=2), encoding="utf-8"
    )


def build_site(
    seed_path: Path = DEFAULT_SEED_PATH,
    posts_dir: Path = DEFAULT_POSTS_DIR,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    static_dir: Path = DEFAULT_STATIC_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> None:
    """Render writing/ content into a static site under output_dir."""
    books = load_books(seed_path, posts_dir / "reviews")
    poems = load_poems(posts_dir / "poetry")
    heatmap_cells = build_activity_heatmap(books, poems)
    quotes = collect_quotes(books)

    env = create_environment(templates_dir, quotes)

    clear_output_dir(output_dir)

    write_page(
        output_dir, "/books/", render_book_list_page(env, books, date.today())
    )
    for book in books:
        write_page(
            output_dir,
            f"/books/{book.book_id}/",
            render_book_detail_page(env, book),
        )

    write_page(output_dir, "/poems/", render_poem_list_page(env, poems))
    for poem in poems:
        write_page(
            output_dir,
            f"/poems/{poem.poem_slug}/",
            render_poem_detail_page(env, poem),
        )

    write_page(output_dir, "/about/", render_about_page(env, heatmap_cells))

    copy_static_assets(static_dir, output_dir)
    write_quotes_json(output_dir, quotes)
    write_redirects_file(output_dir)


if __name__ == "__main__":
    build_site()
    print(f"Built site to {DEFAULT_OUTPUT_DIR}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest site/testing/test_build.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add site/build.py site/testing/test_build.py
git commit -m "Add site/build.py entry point"
```

---

### Task 6: Client-side random quote widget

**Files:**
- Modify: `site/static/js/refresh_quote.js`

**Interfaces:**
- Consumes: `site/dist/quotes.json`, written by `write_quotes_json` (Task 5), each entry shaped `{quote_html, book_title, book_url}` (matching `collect_quotes` in `builder/render.py`, Task 4).
- Produces: page behavior only (no Python interface) — populates `#quote-content`/`#quote-source` (desktop) and `#quote-content-mobile`/`#quote-source-mobile` (mobile) on page load and on refresh-button click, replacing the old fetch to the now-removed `/random-quote` Flask endpoint.

There's no JS test runner in this project (YAGNI — not worth adding one for
a single small widget), so this task is verified manually in a browser
after Task 9's full build, not with an automated test here.

- [ ] **Step 1: Replace the contents of `site/static/js/refresh_quote.js`**

```javascript
/**
 * Random quote widget — fetches all quotes once from /quotes.json and
 * picks one at random, both on page load and on refresh-button click.
 *
 * Each entry in quotes.json is shaped:
 *   { quote_html: "<p>...</p>", book_title: "...", book_url: "/books/.../" }
 */

let cachedQuotes = null;

function updateQuoteWidgets(quoteHtml, sourceHtml) {
    const desktopBody = document.getElementById('quote-content');
    const desktopSource = document.getElementById('quote-source');
    if (desktopBody) desktopBody.innerHTML = quoteHtml;
    if (desktopSource) desktopSource.innerHTML = sourceHtml;

    const mobileBody = document.getElementById('quote-content-mobile');
    const mobileSource = document.getElementById('quote-source-mobile');
    if (mobileBody) mobileBody.innerHTML = quoteHtml;
    if (mobileSource) mobileSource.innerHTML = sourceHtml;
}

function pickRandomQuote(quotes) {
    if (!quotes.length) return null;
    return quotes[Math.floor(Math.random() * quotes.length)];
}

function showRandomQuote(quotes) {
    const quote = pickRandomQuote(quotes);
    if (!quote) return;
    const sourceHtml = `— <a href="${quote.book_url}">${quote.book_title}</a>`;
    updateQuoteWidgets(quote.quote_html, sourceHtml);
}

function loadQuotes() {
    if (cachedQuotes) return Promise.resolve(cachedQuotes);
    return fetch('/quotes.json')
        .then(function (response) {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(function (quotes) {
            cachedQuotes = quotes;
            return quotes;
        });
}

function refreshQuote() {
    loadQuotes()
        .then(showRandomQuote)
        .catch(function (err) {
            console.error('Failed to refresh quote:', err);
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const desktopBtn = document.getElementById('refresh-quote');
    const mobileBtn = document.getElementById('refresh-quote-mobile');

    if (desktopBtn) desktopBtn.addEventListener('click', refreshQuote);
    if (mobileBtn) mobileBtn.addEventListener('click', refreshQuote);

    refreshQuote();
});
```

- [ ] **Step 2: Commit**

```bash
git add site/static/js/refresh_quote.js
git commit -m "Fetch quotes.json client-side instead of the removed /random-quote endpoint"
```

(Manual verification of this widget happens in Task 9, once a full build exists to serve.)

---

### Task 7: Update `pyproject.toml`, `makefile`, and `README.md`

**Files:**
- Modify: `pyproject.toml`
- Modify: `makefile`
- Modify: `README.md`

**Interfaces:** None — this task only updates project metadata and docs to describe the new build/deploy workflow. No code depends on it.

- [ ] **Step 1: Update `pyproject.toml` dependencies**

Replace the `dependencies` list in `pyproject.toml` with:

```toml
dependencies = [
    "bleach>=6.2.0",
    "jinja2>=3.1.6",
    "markdown>=3.8.2",
    "pytest>=9.0.2",
    "pytest-cov>=7.0.0",
    "pyyaml>=6.0.2",
    "ruff>=0.15.4",
    "pygments>=2.19.2",
    "pymdown-extensions>=10.21",
]
```

(Dropped: `duckdb`, `flask`, `flask-migrate`, `flask-sqlalchemy`,
`flask-caching`, `sqlalchemy`, `gunicorn`, `python-dotenv`, `werkzeug` — all
Flask/DB/VPS-specific, unused once Task 8 removes the Flask app.)

Run: `uv sync`
Expected: dependency set updates; `uv.lock` changes.

- [ ] **Step 2: Replace `makefile`**

```makefile
.PHONY: build dev test

build:
	uv run python site/build.py

dev: build
	uv run python -m http.server -d site/dist 8000

test:
	uv run pytest -v
```

- [ ] **Step 3: Update `README.md`**

Replace the "Quick start", "Project structure", "Adding books" intro,
"Writing posts" short version step 3, and "Deploying" sections to match the
new workflow. Key changes:

- Quick start: `make build` renders `site/dist/`; `make dev` builds then
  serves it locally at `http://localhost:8000`.
- Project structure: replace the `site/app/...` tree with the `site/builder/`,
  `site/build.py`, `site/templates/`, `site/static/`, `site/dist/` tree from
  the spec's Architecture section.
- "Writing posts" step 3: replace "Commit and push, then run
  `./site/scripts/deploy.sh` to deploy." with "Commit and push — Cloudflare
  Pages rebuilds and deploys automatically."
- Deploying section: replace the whole SSH/`deploy.sh`/`--reset-database`
  description with: pushing to `main` triggers Cloudflare Pages to run
  `python site/build.py` and publish `site/dist/`; there is no database to
  reset and no server to restart.
- Remove the "Database migrations" section entirely (no schema, no
  migrations).
- Remove the `make` targets table rows for `migrate`/`upgrade`/`stamp`/
  `shell`/`reset`/`reset-posts`/`sync`/`seed`/`restart`; replace with `build`
  and `dev` as described above.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock makefile README.md
git commit -m "Update dependencies, makefile, and README for the static build"
```

---

### Task 8: Delete the Flask/DB stack

**Files:**
- Delete: `site/app/` (entire directory)
- Delete: `site/migrations/` (entire directory)
- Delete: `site/scripts/deploy.sh`, `site/scripts/create_db.py`, `site/scripts/generate_secret_key.sh`
- Delete: `site/testing/conftest.py`, `site/testing/test_app_init.py`, `site/testing/test_cli.py`, `site/testing/test_models.py`, `site/testing/test_routes.py`, `site/testing/test_upsert.py`
- Delete: `.env` references — confirm none remain (the file itself is gitignored, nothing to remove from git)

**Interfaces:** None — this removes code nothing in `builder/`, `build.py`, or the new tests depends on (verified by Task 5's passing test suite, which never imports from `app`).

- [ ] **Step 1: Confirm nothing outside `site/app/` still imports it**

Run: `grep -rn "from app\.\|import app\b" site/builder site/build.py site/testing --include="*.py"`
Expected: no output (empty). If anything is found, fix that import before deleting — it means a Task above missed porting something.

- [ ] **Step 2: Delete the old Flask app, migrations, and VPS scripts**

```bash
git rm -r site/app site/migrations
git rm site/scripts/deploy.sh site/scripts/create_db.py site/scripts/generate_secret_key.sh
git rm site/testing/conftest.py site/testing/test_app_init.py site/testing/test_cli.py site/testing/test_models.py site/testing/test_routes.py site/testing/test_upsert.py
```

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS — only the builder tests from Tasks 1-5 remain and all pass.

- [ ] **Step 4: Run a full build to confirm nothing else broke**

Run: `uv run python site/build.py`
Expected: prints `Built site to .../site/dist`, no errors.

- [ ] **Step 5: Commit**

```bash
git commit -m "Remove the Flask app, Alembic migrations, and VPS deploy scripts"
```

---

### Task 9: Full build verification and manual browser check

**Files:** None modified — verification only.

**Interfaces:** None.

- [ ] **Step 1: Run a clean full build from the real `writing/` content**

Run: `uv run python site/build.py`
Expected: no errors; `site/dist/` contains `books/`, `poems/`, `about/`,
one directory per real book in `writing/book_seed.json`, one per real poem
in `writing/posts/poetry/`, `static/`, `quotes.json`, `_redirects`.

- [ ] **Step 2: Serve the build locally**

Run: `uv run python -m http.server -d site/dist 8000` (leave running)

- [ ] **Step 3: Manually verify in a browser**

Visit `http://localhost:8000/` and check:
- Redirects to `/books/` (the `_redirects` file only takes effect on
  Cloudflare Pages, not Python's `http.server` — if this step shows a
  directory listing instead of the book list, that's expected locally;
  visit `http://localhost:8000/books/` directly to continue verifying).
- `/books/` shows books grouped into this-year vs. previously-read, with
  star ratings, tags, and the "New" seedling badge on recently-reviewed
  books.
- Click into a reviewed book — review renders with markdown formatting,
  quote blocks show as blockquotes, back link works.
- Click into an unreviewed book (if any exist in `book_seed.json`) — shows
  the "under construction" placeholder.
- `/poems/` lists poems; click into one — poem body and any comments
  section both render.
- `/about/` shows the posting-activity heatmap grid.
- The random-quote widget (sidebar on desktop, top slot on mobile-width)
  shows a quote on initial load, and clicking "randomise" swaps it for a
  different one — confirming Task 6's client-side JS works end to end.

- [ ] **Step 4: Stop the local server**

Press `Ctrl+C` in the terminal running `http.server`.

No commit for this task — it's verification of the already-committed work
from Tasks 1-8.
