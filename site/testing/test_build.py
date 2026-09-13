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
    assert (output_dir / "poems" / "fire-and-ice" / "index.html").exists()
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
