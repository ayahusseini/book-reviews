# Static site migration — design

## Goal

Replace the Flask + SQLite + VPS/Gunicorn/nginx stack with a static site: a
Python build script renders `writing/` content to plain HTML, hosted on
Cloudflare Pages. No server process, no database, no migrations.

Priorities (from the user):
- Adding a book review stays easy — same authoring workflow as today.
- Adding future blog posts or one-off pages shouldn't require conforming to
  the reviews/poetry data model. (Deferred to a follow-up — not built now.)
- No database; a build-time JSON file (`book_seed.json`) is enough of a
  "database" for book metadata and stats.

## Non-goals (explicitly deferred)

- The stats/aggregation page (books-per-year charts, etc.) — future feature.
- A generic `writing/pages/` mechanism for freeform blog posts/pages —
  future feature. This migration only ports the existing reviews + poetry
  content types.
- Decommissioning the Vultr VPS — a follow-up once the static site is live
  and verified. The domain is already owned and currently points at Vultr.

## Architecture

```
writing/                          (unchanged — the authoring surface)
├── book_seed.json                ← book registry, unchanged
├── posts/{reviews,poetry}/       ← unchanged
└── unpromoted_posts/             ← unchanged, still skipped by the build

site/
├── builder/                      ← NEW: pure-Python build logic, no Flask/DB
│   ├── content.py                ← loads book_seed.json + posts, joins reviews to books
│   ├── markdown.py                ← moved as-is from app/backend/ (already Flask-free)
│   ├── extract_quotes.py          ← moved as-is (already Flask-free)
│   ├── heatmap.py                 ← ported from routes/helper.py, cache decorator dropped
│   └── render.py                  ← standalone Jinja2 Environment, renders each page to disk
├── build.py                      ← entry point: `python site/build.py` → writes site/dist/
├── templates/                    ← moved from app/templates/, url_for(...) replaced
├── static/                       ← moved from app/static/ (css/js/fonts/img)
├── testing/                      ← rewritten to test builder/ functions directly
└── dist/                         ← gitignored build output
    ├── index.html                 (redirect stub → /books/)
    ├── books/index.html
    ├── books/<key>/index.html
    ├── poems/index.html
    ├── poems/<slug>/index.html
    ├── about/index.html
    ├── quotes.json                 ← for client-side random-quote JS
    └── static/...
```

### Book URLs

`/books/<id>` (SQLite autoincrement id) becomes `/books/<key>/`, using the
existing `key` field from `book_seed.json` — matches how poems already use
slugs. Old numeric URLs are not preserved (full migration, no redirect
shim).

### Book registry stays in `book_seed.json`

Not merged into review frontmatter. A book can exist with no review yet and
still show up (unlinked) in the book list — that only works if there's a
book record independent of any review file. Structured fields (`rating`,
`tags`, `authors`, `page_count`) also belong in one place, not duplicated
into every review's frontmatter, so tag sync ("edit the list, removals take
effect") keeps working exactly as documented in the README today.

`content.py` reads `book_seed.json` and the matching review file (if any)
and joins them into an in-memory book record — same shape as today's
`upsert_books` logic, minus anything DB-specific (no upsert semantics
needed; every build starts fresh from the source files).

### Heatmap

Computed once per build from review/poem creation dates (reusing the
`heatmap_cells`/`_frequency` logic in `routes/helper.py` today, trimmed of
its `@cache.cached()` decorators). A static build baked into HTML *is* the
cache — there's no per-request recomputation to avoid, so no separate
caching layer is needed.

### Random quote widget

`/random-quote` is a live Flask endpoint today; there's no server for a
static site to ask. The build writes every quote to a static
`site/dist/quotes.json` (text + book title + book URL), and a small
inline JS snippet on page load fetches it and picks one at random client-side
— same "different quote per view" behavior as today, no server involved.

### Templates

Jinja2 is used standalone (`jinja2.Environment(FileSystemLoader(...))`)
instead of via Flask. The only real adaptation needed: `url_for(...)` calls
in templates are replaced with plain path-building helpers in `render.py`
(e.g. `book_url(key)` → `/books/<key>/`), since there's no Flask
url-routing to defer to. Everything else in the templates (Jinja
conditionals, loops, macros) is unchanged.

## What's deleted (dead code once the build script replaces it)

- `site/app/` in full: Flask factory (`__init__.py`), `routes/` (`main.py`,
  `books.py`, `poems.py`, `helper.py`), `extensions.py` (db/cache/migrate),
  `config.py`, `cli.py`, `backend/models.py`, `backend/upserts.py`.
  `upserts.py` in particular is entirely upsert-into-SQLite logic (insert
  vs. update branching, flush-for-ids, conflict handling) that only exists
  because the DB persists state across runs — a build script that starts
  fresh from `writing/` each time doesn't need any of it.
- `site/migrations/` (Alembic) — no schema, no migrations.
- `site/scripts/deploy.sh` and `site/scripts/create_db.py`.
- `.env`-based VPS credentials (`VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`).
- `pyproject.toml` dependencies: `flask`, `flask-migrate`,
  `flask-sqlalchemy`, `flask-caching`, `sqlalchemy`, `gunicorn`,
  `python-dotenv`, `werkzeug`, `duckdb` (unused already — grep to confirm
  before removing). Kept: `markdown`, `pyyaml`, `bleach`, `pygments`,
  `pymdown-extensions`, `pytest`, `pytest-cov`, `ruff`.
- `makefile` targets tied to Flask/DB: `dev`, `migrate`, `upgrade`,
  `stamp`, `shell`, `setup`, `reset`, `restart`. Replaced with `build`
  (`python site/build.py`) and a local-preview target
  (`python -m http.server -d site/dist`). `seed`/`reset-posts`/`sync` are
  replaced by the single build step (it reads `writing/` fresh every time,
  there's no separate "seed then import posts" ordering to preserve).

## Build & deploy workflow

Local loop when writing a post — unchanged up through editing files:

```sh
python site/build.py                  # rebuilds site/dist/ from writing/
python -m http.server -d site/dist    # preview locally
```

Then `git push`. Cloudflare Pages is configured (one-time) with build
command `python site/build.py` and output directory `site/dist`; it runs
that automatically on every push to `main` and publishes the result to its
CDN. No SSH, no `--reset-database` flag, no server-side state to
reconcile — every deploy is a from-scratch render of `writing/` at that
commit.

**One-time infra setup (outside this codebase, done by the user):**
1. Connect the GitHub repo to a new Cloudflare Pages project.
2. Point `husseinireads.com` DNS at Cloudflare Pages (the domain is already
   owned; this is a DNS change away from the current Vultr A-record, not a
   domain purchase).
3. Leave the Vultr VPS running for now — decommissioning is a follow-up
   task after the static site is verified live.

## Testing

The current pytest suite (`site/testing/`) tests Flask routes, DB models,
and CLI commands via app-context fixtures. It's rewritten to test
`builder/` functions directly as plain Python: given these `book_seed.json`
entries and these post files, does `content.py` produce the expected book
records; does `render.py` produce the expected HTML/paths; does
`heatmap.py` produce the expected cells for a given set of dates. No app
context, no test database — simpler than today's fixtures.

## Code style for `builder/`

Per user preference: public functions are verb-led (`load_books`, not
`_load_books` or `books`), no leading-underscore "private" functions, and
functions are only extracted into their own name when it genuinely helps
readability — not as a default refactor.
