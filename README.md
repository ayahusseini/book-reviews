# Book Review Website

A Flask application for displaying book reviews and personal writing, backed by SQLite and Open Library.

## Setup

Recommended setup is through [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sh
uv sync
```

Install [pre-commit hooks](https://pre-commit.com/) if you plan to commit changes:

```sh
uv run pre-commit install
```

## Development workflow

All common tasks are available from the repo root via `make`:

```sh
make dev      # start the development server
make seed     # seed books from seed_database/book_seed.json
make posts    # import markdown posts from content/posts/
make sync     # seed books then import posts (seed + posts)
make test     # run the test suite
make migrate  # apply pending database migrations
make shell    # open a Flask shell with DB access
```

## Project structure

```
book_reviews/
├── Makefile
├── content/
│   └── posts/          ← markdown post files live here
├── docs/
└── site/
    ├── app/
    │   ├── blueprints/ ← books, posts, main route handlers
    │   ├── content/
    │   │   └── markdown_posts.py  ← parser and HTML renderer
    │   ├── database/
    │   │   ├── models.py          ← SQLAlchemy models
    │   │   └── open_library.py    ← Open Library API client
    │   ├── templates/
    │   ├── static/
    │   ├── cli.py      ← import-posts command
    │   └── config.py
    ├── migrations/
    ├── seed_database/
    │   ├── convertor.py    ← seeds books from book_seed.json
    │   └── book_seed.json
    └── testing/
```

## Adding posts

Posts are markdown files with YAML frontmatter. Add them to `content/posts/` and run `make posts` to import into the database.

### Frontmatter reference

```yaml
---
title: "My Review"           # required
author: "Aya"                # required
type: "review"               # required: review | essay | standalone | note | quotes
book_ol_key: "OL42549900W"   # required for review and essay posts
rating: 4.5                  # only used when type is review, must be 0–5
slug: "my-review"            # optional, defaults to the filename stem
tags:
  - "non-fiction"
  - "2026"
---

Post body in Markdown...
```

- `review` and `essay` posts must reference a book via `book_ol_key`. If the book is not already in the database it will be fetched automatically from Open Library.
- `standalone` and `note` posts have no book link — omit `book_ol_key`.
- `rating` is only meaningful on `review` posts and is ignored on all other types.
- Tags are normalised to lowercase and attached to the referenced book. New tags are created automatically.
- Re-running `make posts` is safe — existing posts are updated by source path.

### Book ratings

A book's rating is computed as the average `rating` across all of its `review`-type posts. There is no manually set rating on books. To rate a book, write a review post with a `rating` field.

## Adding books manually

Books are seeded from `site/seed_database/book_seed.json`:

```json
[
  {
    "olid": "OL42549900W",
    "comment": "Flesh",
    "tags": ["2026"]
  }
]
```

Run `make seed` to fetch metadata from Open Library and write to the database. Re-running is safe — existing books are updated.

## Configs

| Environment | Behaviour |
|---|---|
| `development` (default) | Debug on, auto-reload, verbose logs |
| `testing` | In-memory SQLite, isolated per test |
| `production` | Debug off, reads `SECRET_KEY` from `.env` |

Switch config by setting `FLASK_ENV` before running:

```sh
FLASK_ENV=production make dev
```

## Database migrations

When you change `site/app/database/models.py`, generate and apply a migration:

```sh
cd site
uv run flask --app app db migrate -m "describe change"
make migrate
```

## Generating a production secret key

```sh
chmod +x site/scripts/generate_secret_key.sh
./site/scripts/generate_secret_key.sh
```

This appends `SECRET_KEY=...` to `.env`.

## Running tests

```sh
make test
```

## Further reading

- [Design notes](/docs/design.md)
- [Flask notes](/docs/flask.md)
- [SQLAlchemy notes](/docs/sqlalchemy.md)