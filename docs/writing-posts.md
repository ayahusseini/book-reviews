# Writing and deploying posts

## Table of contents

1. [Content types](#content-types)
2. [Frontmatter reference](#frontmatter-reference)
3. [Writing a book review](#writing-a-book-review)
4. [Writing a poem](#writing-a-poem)
5. [Inline quotes](#inline-quotes)
6. [Linking to headings](#linking-to-headings)
7. [Images](#images)
8. [Slugs and re-importing](#slugs-and-re-importing)
9. [Deploying](#deploying)

---

## Content types

There are exactly two kinds of writing on the site, dispatched by which subdirectory of `writing/posts/` the file lives in:

| Directory | URL | Needs a book? | Notes |
|---|---|---|---|
| `writing/posts/reviews/` | `/books/<id>` | Yes | One per book — content lives directly on the `Book` row, not a separate table. |
| `writing/posts/poetry/` | `/poems/<slug>` | No | Displayed on the poems page. |

Quotes are not written directly — see [Inline quotes](#inline-quotes).

Drafts that shouldn't be imported yet live in `writing/unpromoted_posts/` (gitignored except for a `.gitkeep`), which `reset-posts` never scans.

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
- **`slug`** defaults to the filename stem (`wuthering-heights.md` → `wuthering-heights`). For poems this is the stable unique identifier. For reviews there's no separate slug — the review is a field on the `Book` row identified by `book_key`.
- **`date`** sets the created-at timestamp. If omitted, it defaults to the time it's first imported. Re-importing does not change this.
- **`book_key`** (reviews only) — the `key` value from the book's entry in `book_seed.json`. The book must already be seeded before the review is imported.

All book metadata (title, authors, rating, tags, description) belongs in `book_seed.json`, not in post frontmatter. Using any of the old fields (`book_ol_key`, `enrich_book`, `rating`, `tags`, `book_title`, etc.) will raise an error on import.

---

## Writing a book review

All book metadata (rating, tags, authors, description) is managed in `book_seed.json`. The review only needs to know which book it belongs to. See the README's [Adding books](../README.md#adding-books) section for the full book-registration flow.

1. Register the book in `writing/book_seed.json` and run `make seed` (skip if it's already seeded).

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

3. Import:

   ```sh
   make reset-posts
   ```

`book_key` must match the `key` field in the seed exactly, and the book must already exist in the database — reviewing an unseeded book raises an error telling you to seed it first.

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

When `reset-posts` runs:

- Each `ad-quote` block is extracted as a `Quote` row linked to the book.
- The block is replaced with standard Markdown blockquote syntax (`>`) in the rendered review body.
- Quote slugs are generated deterministically from the first 100 characters of the quote text. **Editing quote text generates a new slug and therefore a new quote** — the old one is not automatically deleted.

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

Place image files in `site/app/static/img/` and embed them using Obsidian's image syntax:

```markdown
![[my-photo.jpg]]
```

This renders as:

```html
<img src="/static/img/my-photo.jpg" alt="my-photo.jpg">
```

The `alt` text defaults to the filename. Obsidian will display these images locally as long as your vault includes the image file at a path Obsidian can find (the filename just needs to match).

---

## Slugs and re-importing

- For poems, the slug is the unique identifier. If two files produce the same slug, the second import updates the first poem in place.
- **Renaming a poem file** changes its slug (if no explicit `slug` is set in frontmatter) and creates a new poem row. The old one is not deleted.
- **Setting `slug` explicitly** in frontmatter decouples the identifier from the filename, which is useful if you want to rename the file without breaking URLs.
- Reviews have no slug of their own — they're identified by `book_key`, so renaming a review's filename has no effect on identity.
- Re-running `make reset-posts` is always safe. Existing reviews/poems are matched (by `book_key` or slug) and updated only if content has changed; the updated-at timestamp is only touched on real content changes.

---

## Deploying

The recommended workflow keeps everything local — you never need to touch the server's filesystem or run seeds on the server.

### Step 1: write and import locally

```sh
make seed            # upsert books from writing/book_seed.json
make reset-posts      # re-import reviews and poems
```

Or all at once: `make sync`

Tags are managed entirely through `writing/book_seed.json` — edit the relevant entry's `tags` list and run `make seed` again.

### Step 2: push the database

```sh
make deploy-db
```

`DEPLOY_HOST` is read from `.env` (e.g. `DEPLOY_HOST=root@your_server_ip`). You can also pass it inline: `make deploy-db DEPLOY_HOST=root@1.2.3.4`.

This copies `site/instance/site.db` to the server via `scp` and restarts Gunicorn (which clears the in-process cache). Done.

### When you also have code changes

Push code first, then redeploy the database:

```sh
git push
# on the server:
git pull && sudo systemctl restart gunicorn
# back locally:
make deploy-db
```

### Rebuilding the local database from scratch

If the local database gets into a bad state, wipe and rebuild it:

```sh
make reset
```

This deletes `site/instance/site.db`, re-runs all migrations, re-seeds books from `writing/book_seed.json`, and re-imports all reviews and poems.

### When you have schema changes

Generate and commit the migration locally, deploy code, then upgrade the server's database before pushing content:

```sh
make migrate MSG="describe change"
git add site/migrations/versions/
git commit -m "add migration"
git push
# on the server:
git pull
make upgrade
sudo systemctl restart gunicorn
# back locally:
make reset-posts     # re-import with updated schema
make deploy-db
```
