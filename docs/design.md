# Architecture and data model

## Table of contents

1. [Overview](#overview)
2. [Data model](#data-model)
3. [Where to edit what](#where-to-edit-what)
4. [Data flow: adding a book](#data-flow-adding-a-book)
5. [Data flow: importing a post](#data-flow-importing-a-post)
6. [Configuration environments](#configuration-environments)

---

## Overview

The site is a Flask application backed by a single SQLite database. There is no API layer — all content is loaded from markdown files and a JSON seed file via CLI commands, then stored in the database. Flask serves read-only HTML pages from that database.

```
writing/posts/**/*.md   writing/book_seed.json
      │                       │
      ▼                       ▼
 import-posts CLI         seed-books CLI
      │                       │
      └──────────┬────────────┘
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
┌─────────────────┐                                      └──────────────────────────┘
│      tag        │ ◄────────────────────────────────────────────┘
├─────────────────┤
│ tag_id (PK)     │
│ tag_name        │
└─────────────────┘


┌──────────────────────────┐
│           post           │
├──────────────────────────┤
│ post_id (PK)             │
│ parent_id (FK → post_id) │  ← quote posts point to their parent post
│ book_id (FK → book, NULL)│
│ post_slug (unique)       │
│ post_title               │
│ post_body_markdown       │
│ post_type                │
│ post_author              │
│ post_created_at          │
│ post_updated_at          │  ← only updated when content actually changes
└──────────────────────────┘
```

### Valid post types

| Type | Description |
|---|---|
| `review` | Book review. Must have a `book_ol_key`. Sets the book's rating. One per book. |
| `essay` | Longer piece about a book. Should have a `book_ol_key`. |
| `standalone` | Any post not linked to a book. |
| `note` | Short post not linked to a book. |
| `poem` | Poem. Displayed at `/poems/`. |
| `designdoc` | Site design documentation. Displayed at `/design/`. |
| `quotes` | Auto-generated child post for each `ad-quote` block. Never created manually. |

### Design decisions

- **Books and authors are many-to-many.** A book can have multiple authors; an author can have multiple books. Resolved via `book_author_mapping`.
- **Books and tags are many-to-many.** Resolved via `book_to_tag_map`. Tags are created on the fly from `book_seed.json` and post frontmatter.
- **Posts can exist without a book.** `book_id` is nullable — standalone posts, poems, and design docs have no book link.
- **Quote posts are children of their parent post.** `parent_id` is a self-referential FK. The random quote widget uses `parent.post_slug` to link back to the source.
- **`post_updated_at` only changes on real edits.** Re-running `make posts` without changing content does not touch this field.
- **`book_ol_key` is the stable book identifier** but it is not required to be an Open Library key. Manual books use any unique slug (e.g. `remains-of-the-day`). OL enrichment is opt-in per entry via `enrich: true` (seed) or `enrich_book: true` (post frontmatter).
- **`author_ol_id` is the stable author identifier** and is non-nullable. OL-fetched authors use their OL author ID; manually-supplied authors use a slug derived from their name (e.g. `kazuo-ishiguro`).
- **Open Library is optional.** The seed command and post importer never call the OL API unless explicitly asked. Books can be fully specified inline.

---

## Where to edit what

### I want to add a book to the site

→ Edit `writing/book_seed.json` and run `make seed`.

For an Open Library book: `{ "key": "OL14933414W", "enrich": true, "tags": ["2026"] }` — fetches metadata from OL on first seed.

For a manual book: `{ "key": "my-slug", "title": "Title", "authors": ["Author Name"], ... }` — no API call, insert directly.

### I want to write a review or post

→ Create a `.md` file in `writing/posts/`, run `make posts`. See [writing-posts.md](writing-posts.md) for the full workflow.

### I want to change how books are listed or sorted

→ `site/app/blueprints/books.py` — `book_list()` builds the query and passes data to the template.

### I want to change how a book's detail page looks

→ `site/app/templates/book_detail.html` for layout, `site/app/blueprints/books.py:book_detail()` for the data query.

### I want to change what posts appear on the posts page

→ `site/app/blueprints/posts.py` — `SHOWN_IN_POSTS` controls which post types are shown on `/posts/misc_posts`. `post_list()` controls `/posts/`.

### I want to change how the book list item looks (title, stars, tags)

→ `site/app/templates/_macros.html` — the `book_item` macro.

### I want to add a new post type

→ Add it to `VALID_POST_TYPES` in both `site/app/database/models.py` and `site/content/markdown_posts.py`. Add a blueprint/template if it needs its own page.

### I want to change Open Library fetch behaviour

→ `site/app/open_library.py` — pure HTTP client, no Flask or SQLAlchemy imports. `fetch_book_data()` is the main entry point.

### I want to change how posts are stored or upserted

→ `site/app/database/upserts.py` — all write logic lives here. Functions never call `session.commit()` directly; callers (CLI commands) are responsible.

### I want to change the database schema

→ Edit `site/app/database/models.py`, then run `make migrate MSG="describe change"`.

### I want to change site-wide config

→ `site/app/config.py` — `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`.

---

## Data flow: adding a book

```
1. Edit book_seed.json
        │
        ├─ OL book  { "key": "OL123W", "enrich": true, "tags": ["2026"] }
        │      │
        │      ▼
        │  make seed
        │      │
        │      ├─ Book already in DB? ──Yes──► apply overrides (title/desc/rating/tags) only
        │      │                                                no HTTP request made
        │      └─ Book not in DB? ──────────► fetch_book_data(key)
        │                                           │
        │                                     Open Library API
        │                                     /works/{id}.json
        │                                     /works/{id}/editions.json
        │                                     /authors/{id}.json  (per author)
        │                                           │
        │                                     upsert_books(...)
        │                                           │
        │                                     INSERT book, authors, tags, mappings
        │
        └─ Manual book  { "key": "my-slug", "title": "...", "authors": [...] }
               │
               ▼
           make seed
               │
               ├─ Book already in DB? ──Yes──► apply overrides (title/desc/rating/tags)
               └─ Book not in DB? ──────────► upsert_books(BookData from seed entry)
                                                    │
                                              INSERT book, authors, tags, mappings
                                              (no HTTP request)
```

---

## Data flow: importing a post

```
1. Create writing/posts/reviews/my-review.md
        │
        ▼
2. make posts
        │
        ▼
3. parse_markdown_with_frontmatter(path)
        │
        ├── extract YAML frontmatter (title, author, type, book_ol_key/book_key, ...)
        ├── extract ```ad-quote blocks → Quote objects
        └── replace ad-quote blocks with Markdown blockquotes
        │
        ▼
4. resolve_book(parsed)
        │
        ├── no key (book_ol_key or book_key)? ──► return None
        │
        ├── enrich_book: true?
        │       ├── key starts with OL? ──► fetch from Open Library + upsert
        │       └── key does NOT start with OL? ──► raise error immediately
        │
        └── enrich_book: false/absent?
                ├── book already in DB? ──────────► return existing Book
                ├── book not in DB, book_title set? ► upsert from frontmatter fields
                └── book not in DB, no title? ───────► return None (standalone)
        │
        ▼
5. upsert_post(...)
        │
        ├── new post? ──► INSERT
        └── existing?  ──► UPDATE only if content changed
                           post_updated_at set only on real changes
        │
        ▼
6. attach_tags(book, parsed.tags)
        │
        ▼
7. sync_quotes(parsed.quotes, ...)
        │
        └── upsert_post() for each Quote object (post_type="quotes")
        │
        ▼
8. session.commit()  ← happens once per file in import_posts_command
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
