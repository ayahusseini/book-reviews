# HusseiniReads

A Flask application for displaying book reviews and personal writing, backed by SQLite and Open Library.

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

This installs dependencies, applies migrations, seeds books, and resets posts. Books already in the database are not re-fetched from Open Library — only new entries trigger an OL fetch.

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
| `make reset` | **Destructive.** Wipe the database and rebuild from scratch (re-fetches all OL books) |
| `make seed` | Seed/update books from `writing/book_seed.json`. Only fetches from OL for books not yet in the database. Never deletes books — run `make reset` to remove a book |
| `make sync` | `seed` + `reset-posts` + `code` — full content refresh |
| `make reset-posts` | Delete all posts from the DB and re-import from `writing/posts/` |
| `make test` | Run the test suite |
| `make migrate MSG="..."` | Generate a new Alembic migration and apply it |
| `make upgrade` | Apply pending migrations without generating a new one |
| `make stamp` | Mark the DB as at the current migration head (no changes applied) |
| `make shell` | Open a Flask shell with database access |
| `make tags ARGS="..."` | Shorthand for `flask manage-tags` |
| `make deploy-db` | Copy the local SQLite database to the production server |

---

## Project structure

```
book_reviews/
├── makefile
├── pyproject.toml
├── docs/                          ← architecture and workflow docs
├── writing/                       ← all user content (gitignored posts)
│   ├── book_seed.json             ← book registry
│   └── posts/
│       ├── reviews/
│       ├── poetry/
│       ├── TILs/
│       └── design_docs/
└── site/
    ├── app/
    │   ├── __init__.py            ← Flask app factory (create_app)
    │   ├── config.py              ← DevelopmentConfig / TestingConfig / ProductionConfig
    │   ├── extensions.py          ← db, cache, migrate instances
    │   ├── cli.py                 ← seed-books, reset-posts, import-code CLI commands
    │   ├── backend/               ← data layer (no Flask dependencies)
    │   │   ├── models.py          ← SQLAlchemy models
    │   │   ├── upserts.py         ← DB write helpers (never commit internally)
    │   │   ├── open_library.py    ← Open Library HTTP client
    │   │   ├── markdown.py        ← frontmatter parser + HTML renderer
    │   │   └── extract_quotes.py  ← ad-quote block extraction
    │   ├── routes/                ← web layer (Flask route handlers)
    │   │   ├── main.py            ← /, /about, /random-quote
    │   │   ├── books.py           ← /books
    │   │   ├── posts.py           ← /posts
    │   │   ├── poems.py           ← /poems
    │   │   └── design.py          ← /design
    │   ├── templates/
    │   └── static/
    ├── migrations/                ← Alembic migration history
    └── testing/                   ← pytest test suite
```

---

## Adding books

Books are registered in `writing/book_seed.json`. Each entry requires a `key` field.

### With Open Library enrichment

Set `"enrich": true` to fetch metadata automatically. The key must be an OL works key. The OL fetch only happens once — subsequent `make seed` runs skip it if the book is already in the database.

```json
{
  "key": "OL42549900W",
  "enrich": true,
  "tags": ["read-2026", "fiction"],
  "rating": 4.5
}
```

### Without Open Library

Omit `enrich` (or set it to `false`) and supply the metadata directly. Only `key` and `title` are required.

```json
{
  "key": "my-custom-key",
  "title": "The Book Title",
  "authors": ["Author Name"],
  "publication_year": 1997,
  "tags": ["fiction"],
  "rating": 4
}
```

| Field | Required | Description |
|---|---|---|
| `key` | Yes | Unique identifier. Must be an OL works key if `enrich: true` |
| `enrich` | No | If `true`, fetch metadata from Open Library on first add |
| `title` | Yes (manual) / No (enrich) | Title. Overrides OL title when used with `enrich: true` |
| `authors` | No | List of author name strings (manual books only) |
| `description` | No | Overrides the description |
| `publication_year` | No | Publication year (manual books only) |
| `page_count` | No | Page count (manual books only) |
| `rating` | No | Displayed rating (0–5) |
| `tags` | No | List of tag names to attach |

Run `make seed` (or `make sync`) after editing the file.

---

## Writing posts

See **[docs/writing-posts.md](docs/writing-posts.md)** for a full guide, including frontmatter reference, inline quotes, and the deployment workflow.

Short version:

1. Create a `.md` file under `writing/posts/`.
2. Run `make sync` to seed any new books and import posts.
3. Run `make deploy-db` to push the updated database to production.

To show the "New" seedling badge on a book, set `date:` in the review's frontmatter to today's date. Posts without a `date:` field are never badged as new.

---

## Managing tags

Tags are managed entirely through `writing/book_seed.json` and post frontmatter. Edit the relevant file and run `make sync` — seed tags are synced exactly (removals take effect), and post tags are added on top. There is no ad-hoc tag command.

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
