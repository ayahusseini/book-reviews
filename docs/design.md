# Architecture and data model

## Table of contents

1. [Overview](#overview)
2. [Data model](#data-model)
3. [Where to edit what](#where-to-edit-what)
4. [Data flow: adding a book](#data-flow-adding-a-book)
5. [Data flow: importing a review or poem](#data-flow-importing-a-review-or-poem)
6. [Configuration environments](#configuration-environments)

---

## Overview

The site is a Flask application backed by a single SQLite database. There is no API layer — all content is loaded from markdown files and a JSON seed file via CLI commands, then stored in the database. Flask serves read-only HTML pages from that database.

```
writing/posts/{reviews,poetry}/*.md   writing/book_seed.json
      │                                       │
      ▼                                       ▼
   reset-posts CLI                       seed-books CLI
      │                                       │
      └──────────────────┬────────────────────┘
                         ▼
                   SQLite database
                         │
                         ▼
                 Flask blueprints
                         │
                         ▼
                   HTML responses
```

---

## Data model

### Schema

```
┌────────────────────┐        book_author_mapping        ┌──────────────────────────┐
│       author       │ ◄──────────────────────────────── │          book            │
├────────────────────┤                                   ├──────────────────────────┤
│ author_id (PK)     │                                   │ book_id (PK)             │
│ author_name        │                                   │ book_ol_key (unique)     │
│ author_ol_id       │                                   │ book_title               │
└────────────────────┘                                   │ book_description         │
                                                          │ book_publication_year    │
                                                          │ book_rating              │
         book_to_tag_map                                 │ book_page_count          │
┌─────────────────┐                                      │ review_markdown          │
│      tag        │ ◄─────────────────────────────────── │ review_created_at        │
├─────────────────┤                                      │ review_updated_at        │
│ tag_id (PK)     │                                       └──────────┬───────────────┘
│ tag_name        │                                                  │
└─────────────────┘                                                  │
                                                                      │ quote.book_id (FK)
┌──────────────────────────┐                              ┌──────────▼───────────────┐
│           poem           │                              │          quote           │
├──────────────────────────┤                              ├──────────────────────────┤
│ poem_id (PK)             │                               │ quote_id (PK)            │
│ poem_slug (unique)       │                               │ quote_slug (unique)      │
│ poem_title               │                               │ quote_text               │
│ poem_body_markdown       │                               │ book_id (FK → book)      │
│ poem_author              │                               └──────────────────────────┘
│ poem_created_at          │
│ poem_updated_at          │  ← only updated when content actually changes
└──────────────────────────┘
```

There is no polymorphic "post" table. A book's review lives directly on the `book` row (it's always exactly one review per book), poems get their own table, and quotes always belong to a book — never a poem.

### Design decisions

- **Books and authors are many-to-many.** A book can have multiple authors; an author can have multiple books. Resolved via `book_author_mapping`.
- **Books and tags are many-to-many.** Resolved via `book_to_tag_map`. Tags are created on the fly from `book_seed.json`.
- **Review content is columns on `Book`, not a separate table.** Since a book can have at most one review, there's no upside to a join — `upsert_review` just sets `review_markdown`/`review_created_at`/`review_updated_at` in place, so "one review per book" is structurally guaranteed rather than enforced by a uniqueness check.
- **Poems are independent of books.** No book link at all.
- **Quotes always belong to a book.** `quote.book_id` is non-nullable. Quotes are only ever extracted from `ad-quote` blocks inside a review body, never from poems.
- **`poem_updated_at`/`review_updated_at` only change on real edits.** Re-running `reset-posts` without changing content does not touch these fields.
- **`book_ol_key` is the stable book identifier.** The name is a holdover — it's just any unique slug (e.g. `remains-of-the-day`) supplied in `book_seed.json`; there is no Open Library integration anymore.
- **`author_ol_id` is the stable author identifier** and is non-nullable. It's a slug derived from the author's name (e.g. `kazuo-ishiguro`), assigned when the author is first seeded.
- **All book metadata belongs in `book_seed.json`.** Review/poem frontmatter only carries `book_key` (reviews) to reference a book. Rating, tags, title, authors, and description are all seeded directly, not fetched or inferred from posts.
- **Cross-document wikilinks are not supported.** Reviews and poems don't share a slug namespace, so `[[some-slug]]` has no single route to resolve to. Only `[[#heading]]` same-document anchors work.

---

## Where to edit what

### I want to add a book to the site

→ Edit `writing/book_seed.json` and run `make seed`. See the README's [Adding books](../README.md#adding-books) section for the full flow.

### I want to write a review or poem

→ Create a `.md` file in `writing/posts/reviews/` or `writing/posts/poetry/`, run `make reset-posts`. See [writing-posts.md](writing-posts.md) for the full workflow.

### I want to change how books are listed or sorted

→ `site/app/routes/books.py` — `book_list()` builds the query and passes data to the template.

### I want to change how a book's detail page looks

→ `site/app/templates/book_detail.html` for layout, `site/app/routes/books.py:book_detail()` for the data query.

### I want to change how the book list item looks (title, stars, tags)

→ `site/app/templates/_macros.html` — the `book_item` macro.

### I want to change how poems are listed or displayed

→ `site/app/routes/poems.py` and `site/app/templates/poems.html` / `poem_detail.html`.

### I want to change how reviews, poems, or quotes are stored or upserted

→ `site/app/backend/upserts.py` — all write logic lives here. Functions never call `session.commit()` directly; callers (CLI commands) are responsible.

### I want to change the database schema

→ Edit `site/app/backend/models.py`, then run `make migrate MSG="describe change"`.

### I want to change site-wide config

→ `site/app/config.py` — `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`.

---

## Data flow: adding a book

```
1. Edit book_seed.json
   { "key": "my-slug", "title": "...", "authors": [...], "tags": ["2026"] }
        │
        ▼
   make seed
        │
        ├─ Book already in DB? ──Yes──► apply overrides (title/desc/rating/tags)
        └─ Book not in DB? ──────────► upsert_books(BookData from seed entry)
                                             │
                                       INSERT book, authors, tags, mappings
```

Note: on updates to an already-seeded book, only `title`, `description`, `rating`, and `tags` are refreshed. `authors`, `publication_year`, and `page_count` are set once at creation and not re-synced afterward — to change those on an existing book, edit the database directly or `make reset`.

---

## Data flow: importing a review or poem

```
1. Create writing/posts/reviews/my-review.md or writing/posts/poetry/my-poem.md
        │
        ▼
2. make reset-posts  (always run make seed first, or use make sync)
        │
        ▼
3. reset_posts_command dispatches by directory:
        │
        ├── writing/posts/reviews/*.md  ──► import_review_file(path)
        └── writing/posts/poetry/*.md   ──► import_poem_file(path)
        │
        ▼
4. parse_markdown_with_frontmatter(path)
        │
        ├── extract YAML frontmatter (title, author, book_key, ...)
        ├── extract ```ad-quote blocks → ExtractedQuote objects
        └── replace ad-quote blocks with Markdown blockquotes
        │
        ▼
5a. Review path:                          5b. Poem path:
        │                                         │
   resolve_book(parsed)                      upsert_poem(...)
        │                                         │
   ├── no book_key? ──► raise error           ├── new? ──► INSERT
   ├── book in DB? ───► use it                └── existing? ──► UPDATE only if content changed
   └── not in DB? ────► raise error
        │
   upsert_review(book, body, ...)
        │
   ├── new? ──► set review_markdown/review_created_at
   └── existing? ──► overwrite review_markdown,
                      bump review_updated_at only if content changed
        │
        ▼
6. sync_quotes_for_book(book, parsed.quotes)   ← reviews only, poems never sync quotes
        │
        └── upsert Quote rows by quote_slug, linked to book
        │
        ▼
7. session.commit()  ← happens once per file in reset_posts_command
```

---

## Configuration environments

Set `FLASK_ENV` before running to select a config:

| Value | Class | Database | Notes |
|---|---|---|---|
| `development` (default) | `DevelopmentConfig` | `site/instance/site.db` | Debug on, verbose logs |
| `testing` | `TestingConfig` | In-memory SQLite | Isolated per test, no caching |
| `production` | `ProductionConfig` | `site/instance/site.db` | Debug off, `SECRET_KEY` from `.env`, ProxyFix enabled |

```sh
FLASK_ENV=production make dev
```
