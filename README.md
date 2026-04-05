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

This installs dependencies, applies migrations, seeds books, and imports posts. Books already in the database are not re-fetched from Open Library.

To start the development server:

```sh
make dev
```

---

## Make targets

| Target | What it does |
|---|---|
| `make dev` | Start Flask development server with auto-reload |
| `make setup` | Install deps, apply migrations, seed books, import posts |
| `make reset` | **Destructive.** Wipe the database and rebuild from scratch |
| `make seed` | Seed/update books from `writing/book_seed.json` (skips OL fetch for existing books) |
| `make seed-refresh` | Re-fetch all book metadata from Open Library |
| `make posts` | Import/update all markdown posts from `writing/posts/` |
| `make sync` | `seed` + `posts` |
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
│   ├── book_seed.json             ← book registry with OL keys and overrides
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
    │   ├── cli.py                 ← seed-books and import-posts CLI commands
    │   ├── open_library.py        ← Open Library HTTP client (pure, no Flask deps)
    │   ├── blueprints/
    │   │   ├── main.py            ← home redirect, about, random-quote endpoint
    │   │   ├── books.py           ← /books routes
    │   │   ├── posts.py           ← /posts routes
    │   │   ├── poems.py           ← /poems routes
    │   │   └── design.py          ← /design routes
    │   ├── database/
    │   │   ├── models.py          ← SQLAlchemy models
    │   │   └── upserts.py         ← batch upsert helpers (never commit internally)
    │   ├── templates/
    │   └── static/
    ├── content/
    │   ├── markdown_posts.py      ← frontmatter parser + HTML renderer
    │   └── extract_quotes.py      ← ad-quote block extraction
    ├── migrations/                ← Alembic migration history
    └── testing/                   ← pytest test suite
```

---

## Adding books

Books are registered in `writing/book_seed.json`. Each entry requires an Open Library works key (`olid`). All other fields are optional overrides.

```json
[
  {
    "olid": "OL42549900W",
    "tags": ["2026", "fiction"]
  },
  {
    "olid": "OL166482W",
    "title": "My preferred title",
    "description": "A custom description that overrides what Open Library returns.",
    "rating": 4.5,
    "tags": ["2025"]
  }
]
```

| Field | Required | Description |
|---|---|---|
| `olid` | Yes | Open Library works key |
| `tags` | No | List of tag names to attach to the book |
| `title` | No | Overrides the title fetched from Open Library |
| `description` | No | Overrides the description fetched from Open Library |
| `rating` | No | Sets the book's displayed rating (0–5) |

Run `make seed` after editing the file. The `comment` field is not used — omit it. Books already in the database are not re-fetched from Open Library — only the overrides are applied. Use `make seed-refresh` to force a full re-fetch of all books.

---

## Writing posts

See **[docs/writing-posts.md](docs/writing-posts.md)** for a full guide, including frontmatter reference, inline quotes, and the deployment workflow.

Short version:

1. Create a `.md` file under `writing/posts/`.
2. Run `make posts` to import it into the database.
3. Run `make deploy-db` to push the updated database to production.

---

## Managing tags

Tags are attached to books automatically during `make seed` and `make posts`.

For ad-hoc changes without re-importing, use `flask manage-tags` directly:

```sh
PYTHONPATH=site uv run flask --app site/app manage-tags --book OL42549900W --add "fiction" --remove "2025"
```

Or via the Makefile shorthand (avoid tag names with spaces or hyphens — make strips quoting):

```sh
make tags ARGS="--book OL42549900W --add fiction"
```

---

## Database migrations

When you change `site/app/database/models.py`, generate and apply a migration:

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
