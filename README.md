# HusseiniReads

A static site generator for book reviews and poetry, built from Markdown content in `writing/`.

Live at: [https://husseinireads.com/books/](https://husseinireads.com/books/)

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you do not have it, then:

```sh
make build
```

This renders the site into `site/dist/`.

To build and serve it locally:

```sh
make dev
```

This builds the site, then serves `site/dist/` at [http://localhost:8000](http://localhost:8000).

---

## Make targets

| Target       | What it does                                                        |
| ------------ | --------------------------------------------------------------------|
| `make build` | Render the site from `writing/` into `site/dist/`                   |
| `make dev`   | Build the site, then serve `site/dist/` at `http://localhost:8000`  |
| `make test`  | Run the test suite                                                  |

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
│   │   ├── reviews/                ← rendered as book review pages
│   │   └── poetry/                 ← rendered as poem pages
│   └── unpromoted_posts/          ← drafts; gitignored, never imported
└── site/
    ├── build.py                   ← entry point: reads writing/, writes site/dist/
    ├── builder/                   ← build logic (no Flask/DB dependencies)
    │   ├── content.py             ← loads books/poems into plain data objects
    │   ├── markdown.py            ← frontmatter parser + HTML renderer
    │   ├── extract_quotes.py      ← ad-quote block extraction
    │   ├── heatmap.py             ← posting-activity heatmap for the about page
    │   └── render.py              ← renders pages with Jinja2, copies static assets
    ├── templates/                 ← Jinja2 page templates
    ├── static/                    ← CSS, JS, fonts, images (copied into dist as-is)
    ├── dist/                      ← build output; gitignored, deployed by Cloudflare Pages
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


| Field              | Required | Description                    |
| ------------------ | -------- | ------------------------------ |
| `key`              | Yes      | Unique identifier for the book |
| `title`            | Yes      | Book title                     |
| `authors`          | No       | List of author name strings    |
| `description`      | No       | Book description               |
| `publication_year` | No       | Publication year               |
| `page_count`       | No       | Page count                     |
| `rating`           | No       | Displayed rating (0–5)         |
| `tags`             | No       | List of tag names to attach    |


Run `make build` (or `make dev`) after editing the file to see the change locally — every build reads `book_seed.json` fresh, so all fields always reflect what's currently in the file.

### Step 2: write the review (optional)

See [Writing posts](#writing-posts) below — a review's frontmatter references the book via `book_key`, which must match the `key` from step 1.

---

## Writing posts

See **[docs/writing-posts.md](docs/writing-posts.md)** for a full guide, including frontmatter reference, inline quotes, and the deployment workflow.

Short version:

1. Create a `.md` file under `writing/posts/reviews/` (needs `book_key` in frontmatter, matching an already-registered book) or `writing/posts/poetry/` (no book needed).
2. Run `make build` (or `make dev`) to check it locally.
3. Commit and push — Cloudflare Pages rebuilds and deploys automatically.

To show the "New" seedling badge, set `date:` in the frontmatter to today's date. Reviews/poems without a `date:` field are never badged as new.

---

## Managing tags

Tags are managed entirely through `writing/book_seed.json`. Edit the relevant entry and run `make build` (or `make dev`) — tags are read exactly as listed, so removals take effect too. There is no ad-hoc tag command.

---

## Deploying

Pushing to `main` triggers Cloudflare Pages, which runs `python site/build.py` and publishes `site/dist/`. There is no database to reset and no server to restart — a deploy is just a build.

```sh
git push   # Cloudflare Pages builds and deploys automatically
```

---

## Further reading

- [Architecture and data model](docs/design.md) — how the pieces fit together, where to edit what
- [Writing and deploying posts](docs/writing-posts.md) — post types, frontmatter, quotes, deployment workflow
- [Testing](docs/testing.md) — test structure, fixtures, and how to add tests

