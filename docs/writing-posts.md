# Writing and deploying posts

## Table of contents

1. [Content types](#content-types)
2. [Frontmatter reference](#frontmatter-reference)
3. [Writing a book review](#writing-a-book-review)
4. [Writing a poem](#writing-a-poem)
5. [Inline quotes](#inline-quotes)
6. [Linking to headings](#linking-to-headings)
7. [Images](#images)
8. [Slugs and rebuilding](#slugs-and-rebuilding)
9. [Deploying](#deploying)

---

## Content types

There are exactly two kinds of writing on the site, dispatched by which subdirectory of `writing/posts/` the file lives in:

| Directory | URL | Needs a book? | Notes |
|---|---|---|---|
| `writing/posts/reviews/` | `/books/<id>` | Yes | One per book — content is rendered directly onto that book's page. |
| `writing/posts/poetry/` | `/poems/<slug>` | No | Displayed on the poems page. |

Quotes are not written directly — see [Inline quotes](#inline-quotes).

Drafts that shouldn't be published yet live in `writing/unpromoted_posts/` (gitignored except for a `.gitkeep`), which the build never scans.

---

## Frontmatter reference

Every post file starts with a YAML frontmatter block between `---` delimiters:

```yaml
---
title: "My Review of Wuthering Heights"   # required
author: "Aya"                              # required
slug: "wuthering-heights-review"           # optional, defaults to filename stem
date: "2026-01-15"                         # optional creation date (YYYY-MM-DD)
book_key: "OL14933414W"                    # required for reviews — key from book_seed.json
---

Post body in Markdown...
```

### Field notes

- **`title`** and **`author`** are always required.
- **`slug`** defaults to the filename stem (`wuthering-heights.md` → `wuthering-heights`). For poems this is the stable unique identifier. For reviews there's no separate slug — the review is matched to its book via `book_key`.
- **`date`** sets the created-at date shown on the site. If omitted, the post has no date and is never badged as new.
- **`book_key`** (reviews only) — the `key` value from the book's entry in `book_seed.json`. The book must already be registered in `book_seed.json` before its review is built.

All book metadata (title, authors, rating, tags, description) belongs in `book_seed.json`, not in post frontmatter. Old fields from the previous Flask/SQLite version of this site (`book_ol_key`, `enrich_book`, `rating`, `tags`, `book_title`, etc.) are no longer read and have no effect.

---

## Writing a book review

All book metadata (rating, tags, authors, description) is managed in `book_seed.json`. The review only needs to know which book it belongs to. See the README's [Adding books](../README.md#adding-books) section for the full book-registration flow.

1. Register the book in `writing/book_seed.json` (skip if it's already registered).

2. Create a markdown file under `writing/posts/reviews/`:

   ```yaml
   ---
   title: "Wuthering Heights"
   author: "Aya"
   book_key: "OL14933414W"
   date: "2026-03-10"
   ---

   Opening thoughts...
   ```

3. Run `make build` (or `make dev`) to render it locally.

`book_key` must match the `key` field in `book_seed.json` exactly, and the book must already be registered in `book_seed.json` — otherwise the review has nothing to attach to.

---

## Writing a poem

Save the file under `writing/posts/poetry/` — no `book_key` needed:

```yaml
---
title: "Small Hours"
author: "Aya"
date: "2026-02-01"
---

Body here...
```

To add a comments/notes section after the poem itself, separate it with a `\n---\n` line:

```markdown
The poem itself.

---

A note about the poem, rendered separately below it.
```

---

## Inline quotes

Wrap passages you want to extract as quotes with ` ```ad-quote ` fences, **in a review only** — quotes are book-linked and are not extracted from poems:

````markdown
Some introductory text.

```ad-quote
He was still, and suffering seemed to speak
in the severe simplicity of his attitude.
```

More text continues here.
````

When the site is built:

- Each `ad-quote` block is extracted as a quote linked to the book.
- The block is replaced with standard Markdown blockquote syntax (`>`) in the rendered review body.
- Quote slugs are generated deterministically from the first 100 characters of the quote text. Editing quote text generates a new slug for that quote.

The random quote widget in the sidebar pulls from all quotes and links back to the book.

---

## Linking to headings

Cross-document wikilinks (`[[some-slug]]`) are **not supported** — reviews and poems don't share a slug namespace, so there's no single route a bare slug could resolve to.

Same-document heading links still work:

```markdown
Jump to a heading within the current post:
[[#Part Two]]

With custom display text:
[[#Part Two|jump to Part Two]]
```

The heading fragment is converted to an anchor using the same rules as Python-Markdown's table of contents: lowercased, with spaces replaced by hyphens and non-alphanumeric characters removed. So `## Part Two` becomes `#part-two` and `## A Thought (or Two)` becomes `#a-thought-or-two`.

---

## Images

Place image files in `site/static/img/` and embed them using Obsidian's image syntax:

```markdown
![[my-photo.jpg]]
```

This renders as:

```html
<img src="/static/img/my-photo.jpg" alt="my-photo.jpg">
```

The `alt` text defaults to the filename. Obsidian will display these images locally as long as your vault includes the image file at a path Obsidian can find (the filename just needs to match).

---

## Slugs and rebuilding

- For poems, the slug is the unique identifier. If two files produce the same slug, the one processed later wins.
- **Renaming a poem file** changes its slug (if no explicit `slug` is set in frontmatter), which changes its URL.
- **Setting `slug` explicitly** in frontmatter decouples the identifier from the filename, which is useful if you want to rename the file without breaking URLs.
- Reviews have no slug of their own — they're matched to their book by `book_key`, so renaming a review's filename has no effect on which book it belongs to.
- The site is rendered fresh from `writing/` on every build (`make build` / `make dev`), so there's no import state to get out of sync — editing a file and rebuilding always reflects exactly what's on disk.

---

## Deploying

### Step 1: write and check locally

```sh
make build   # or `make dev` to also serve it locally
```

Every build reads `writing/` and `book_seed.json` fresh, so all content always reflects what's currently on disk.

### Step 2: commit, push, deploy

```sh
git push
```

Pushing to `main` triggers Cloudflare Pages, which installs the dependencies from `requirements.txt`, runs `python site/build.py`, and publishes `site/dist/`. There is no database to reset and no server to restart — a deploy is just a build. See the README's [Deploying](../README.md#deploying) section for the Cloudflare Pages build configuration.
