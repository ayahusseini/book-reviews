# HusseiniReads

A Flask application for book reviews and poetry, backed by SQLite.

Live at: https://husseinireads.com/books/

![main-page](docs/img/main_page_sh.png)

---

## Table of contents
1. [Quick start](#quick-start)
2. [Make targets](#make-targets)
3. [Project structure](#project-structure)
4. [Adding books](#adding-books)
5. [Writing posts](#writing-posts)
6. [Managing tags](#managing-tags)
7. [Database migrations](#database-migrations)
8. [Deploying](#deploying)
9. [Further reading](#further-reading)

---

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you do not have it, then:

```sh
make setup
```

This installs dependencies, applies migrations, seeds books, and imports reviews and poems.

To start the development server:

```sh
make dev
```

---

## Make targets

| Target | What it does |
|---|---|
| `make dev` | Start Flask development server with auto-reload |
| `make setup` | Install deps, apply migrations, seed books, reset posts |
| `make reset` | **Destructive.** Wipe the database and rebuild from scratch |
| `make seed` | Seed/update books from `writing/book_seed.json`. Never deletes books — run `make reset` to remove a book |
| `make sync` | `seed` + `reset-posts` — full content refresh |
| `make reset-posts` | Clear reviews, poems, and quotes from the DB and re-import from `writing/posts/{reviews,poetry}/` |
| `make test` | Run the test suite |
| `make migrate MSG="..."` | Generate a new Alembic migration and apply it |
| `make upgrade` | Apply pending migrations without generating a new one |
| `make stamp` | Mark the DB as at the current migration head (no changes applied) |
| `make shell` | Open a Flask shell with database access |
| `make deploy-db` | Copy the local SQLite database to the production server |

---

## Project structure

```
book_reviews/
├── makefile
├── pyproject.toml
├── docs/                          ← architecture and workflow docs
├── writing/                       ← all user content
│   ├── book_seed.json             ← book registry (source of truth for book metadata)
│   ├── posts/
│   │   ├── reviews/                ← imported into Book.review_markdown
│   │   └── poetry/                 ← imported into the Poem table
│   └── unpromoted_posts/          ← drafts; gitignored, never imported
└── site/
    ├── app/
    │   ├── __init__.py            ← Flask app factory (create_app)
    │   ├── config.py              ← DevelopmentConfig / TestingConfig / ProductionConfig
    │   ├── extensions.py          ← db, cache, migrate instances
    │   ├── cli.py                 ← seed-books, reset-posts CLI commands
    │   ├── backend/               ← data layer (no Flask dependencies)
    │   │   ├── models.py          ← SQLAlchemy models (Book, Poem, Quote, Tag, Author)
    │   │   ├── upserts.py         ← DB write helpers (never commit internally)
    │   │   ├── book_data.py       ← plain AuthorData/BookData containers
    │   │   ├── markdown.py        ← frontmatter parser + HTML renderer
    │   │   └── extract_quotes.py  ← ad-quote block extraction
    │   ├── routes/                ← web layer (Flask route handlers)
    │   │   ├── main.py            ← /, /about, /random-quote
    │   │   ├── books.py           ← /books
    │   │   └── poems.py           ← /poems
    │   ├── templates/
    │   └── static/
    ├── migrations/                ← Alembic migration history
    └── testing/                   ← pytest test suite
```

---

## Adding books

Adding a book to the site is two independent steps: **register the book**, then **write the review**. A book can exist with no review (it shows up unlinked in the book list); a review always requires the book to be registered first.

### Step 1: register the book

Books are registered in `writing/book_seed.json`. Each entry requires a `key` (any unique slug — it doesn't need to mean anything external) and a `title`:

```json
{
  "key": "my-custom-key",
  "title": "The Book Title",
  "authors": ["Author Name"],
  "publication_year": 1997,
  "page_count": 320,
  "description": "A short description.",
  "tags": ["fiction"],
  "rating": 4
}
```

| Field | Required | Description |
|---|---|---|
| `key` | Yes | Unique identifier for the book |
| `title` | Yes | Book title |
| `authors` | No | List of author name strings |
| `description` | No | Book description |
| `publication_year` | No | Publication year |
| `page_count` | No | Page count |
| `rating` | No | Displayed rating (0–5) |
| `tags` | No | List of tag names to attach |

Run `make seed` (or `make sync`) after editing the file. On every run, **existing books only get `title`, `description`, `rating`, and `tags` refreshed** from the seed entry — `authors`, `publication_year`, and `page_count` are set once at creation and never updated afterward (edit the database directly, or `make reset`, to change those on an existing book).

### Step 2: write the review (optional)

See [Writing posts](#writing-posts) below — a review's frontmatter references the book via `book_key`, which must match the `key` from step 1.

---

## Writing posts

See **[docs/writing-posts.md](docs/writing-posts.md)** for a full guide, including frontmatter reference, inline quotes, and the deployment workflow.

Short version:

1. Create a `.md` file under `writing/posts/reviews/` (needs `book_key` in frontmatter, matching an already-seeded book) or `writing/posts/poetry/` (no book needed).
2. Run `make reset-posts` (or `make sync`, which also reseeds books first) to import it.
3. Run `make deploy-db` to push the updated database to production.

To show the "New" seedling badge, set `date:` in the frontmatter to today's date. Reviews/poems without a `date:` field are never badged as new.

---

## Managing tags

Tags are managed entirely through `writing/book_seed.json`. Edit the relevant entry and run `make sync` — tags are synced exactly, so removals take effect too. There is no ad-hoc tag command.

---

## Database migrations

When you change `site/app/backend/models.py`, generate and apply a migration:

```sh
make migrate MSG="Describe what changed"
```

This runs `flask db migrate` (auto-detects schema changes) then `flask db upgrade`. The generated file is committed to `site/migrations/versions/` so production can be upgraded with `make upgrade` after a `git pull`.

If the schema is already correct but Alembic's version table is out of sync:

```sh
make stamp
```

---

## Deploying

See **[docs/deployment.md](docs/deployment.md)** for full server setup instructions.

### Routine content updates (recommended)

Write and import posts locally, then push the database file directly:

```sh
make deploy-db DEPLOY_HOST=root@your_server_ip
```

This copies `site/instance/site.db` to the server via `scp` and restarts Gunicorn to clear the in-process cache. No need to `scp` markdown files or run seeds on the server.

### Code changes

```sh
git push
# on the server:
git pull && sudo systemctl restart gunicorn
```

### Schema changes

Generate and commit the migration locally, then on the server:

```sh
git pull
make upgrade
sudo systemctl restart gunicorn
```

### Full reset on the server

```sh
make reset   # wipes site/instance/site.db and rebuilds from scratch
```

---

## Further reading

- [Architecture and data model](docs/design.md) — how the pieces fit together, where to edit what
- [Writing and deploying posts](docs/writing-posts.md) — post types, frontmatter, quotes, deployment workflow
- [Testing](docs/testing.md) — test structure, fixtures, and how to add tests
- [Deployment setup](docs/deployment.md) — provisioning a VPS, Nginx, Gunicorn, systemd
- [Flask notes](docs/flask.md) — application factory, blueprints, extensions
- [SQLAlchemy notes](docs/sqlalchemy.md) — ORM patterns used in this project
