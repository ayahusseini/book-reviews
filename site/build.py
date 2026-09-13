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
    """Write _redirects file for the / -> /books/ redirect."""
    (output_dir / "_redirects").write_text("/ /books/ 301\n", encoding="utf-8")


def write_quotes_json(output_dir: Path, quotes: list[dict]) -> None:
    """Write quotes to quotes.json for client-side use."""
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
