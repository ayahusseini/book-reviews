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
    ├── dist/                      ← build output; gitignored, deployed by Cloudflare Workers
    └── testing/                   ← pytest test suite
```

---

## Adding books

Adding a book to the site is two independent steps: **register the book**, then **write the review**. A book can exist with no review (it shows up unlinked in the book list); a review always requires the book to be registered first.

### Step 1: register the book

Books are registered in `writing/book_seed.json`. Each entry requires a `title`; its id is generated automatically from the title and `authors` (so no separate key to keep in sync):

```json
{
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
| `title`            | Yes      | Book title                     |
| `authors`          | No       | List of author name strings — included in the generated id if present |
| `description`      | No       | Book description               |
| `publication_year` | No       | Publication year               |
| `page_count`       | No       | Page count                     |
| `rating`           | No       | Displayed rating (0–5)         |
| `tags`             | No       | List of tag names to attach    |


Run `make build` (or `make dev`) after editing the file to see the change locally — every build reads `book_seed.json` fresh, so all fields always reflect what's currently in the file.

### Step 2: write the review (optional)

See [Writing posts](#writing-posts) below — a review's frontmatter references the book via `book_key`, which must match the book's generated id (title + authors, slugified).

---

## Writing posts

1. Create a `.md` file under `writing/posts/reviews/` (needs `book_key` in frontmatter, matching an already-registered book's generated id) or `writing/posts/poetry/` (no book needed — the poem's id is generated automatically from its `title` and `author`).
2. Every post needs `title` and `author` in frontmatter; reviews also need `book_key`.
3. Run `make build` (or `make dev`) to check it locally.
4. Commit and push. Workers Builds rebuilds and deploys automatically.

To show the "New" seedling badge, set `date:` in the frontmatter to today's date. Reviews/poems without a `date:` field are never badged as new.

Inline quotes in a review are wrapped in ` ```ad-quote ` fences and are extracted and linked to the book at build time; quotes aren't supported in poems.

---

## Managing tags

Tags are managed entirely through `writing/book_seed.json`. Edit the relevant entry and run `make build` (or `make dev`) — tags are read exactly as listed, so removals take effect too. There is no ad-hoc tag command.

---

## Deploying

The site is served by a static-assets-only Cloudflare Worker (no Worker script), configured in `wrangler.jsonc`. It serves `site/dist/` and attaches the `husseinireads.com` custom domain. The `_redirects` file written by the build is honoured by Workers static assets.

Pushing to `main` triggers Workers Builds, which installs dependencies, builds the site, then runs `wrangler deploy`. There is no database to reset and no server to restart. A deploy is just a build.

The Worker's build settings (Settings → Builds in the Cloudflare dashboard) should be:

- Build command: `pip install -r requirements.txt && python site/build.py`
- Deploy command: `npx wrangler deploy`

`requirements.txt` (not `pyproject.toml`/`uv.lock`) is what the build image's `pip` reads, so it must list the site's runtime dependencies directly.

To deploy by hand from a local checkout:

```sh
make build && npx wrangler deploy
```

Otherwise:

```sh
git push   # Workers Builds builds and deploys automatically
```

