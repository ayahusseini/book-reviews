# Writing and deploying posts

## Table of contents

1. [Post types](#post-types)
2. [Frontmatter reference](#frontmatter-reference)
3. [Writing a book review](#writing-a-book-review)
4. [Writing a standalone post, note, or poem](#writing-a-standalone-post-note-or-poem)
5. [Adding a code demo file](#adding-a-code-demo-file)
6. [Inline quotes](#inline-quotes)
7. [Linking between posts](#linking-between-posts)
8. [Images](#images)
9. [Slugs and re-importing](#slugs-and-re-importing)
10. [Deploying](#deploying)

---

## Post types

| Type | URL | Needs a book? | Notes |
|---|---|---|---|
| `review` | `/books/<id>` | Yes | One per book. Sets the book's rating. |
| `essay` | `/books/<id>` | Yes (recommended) | Longer piece about a book. |
| `standalone` | `/posts/<slug>` | No | General post with no book link. |
| `note` | `/posts/<slug>` | No | Short post with no book link. |
| `til` | `/posts/<slug>` | No | Short "Today I Learned" entry. Shown in the posts listing under TODAY I LEARNED. |
| `poem` | `/poems/<slug>` | No | Displayed on the poems page. |
| `designdoc` | `/design/all` | No | Site design notes. |
| `code` | `/posts/<filename>` | No | Code demo file (`.sql`, `.py`, etc.). Not shown in the posts listing. |
| `quotes` | — | — | Auto-generated from `ad-quote` blocks. Never create manually. |

---

## Frontmatter reference

Every post file starts with a YAML frontmatter block between `---` delimiters:

```yaml
---
title: "My Review of Wuthering Heights"   # required
author: "Aya"                              # required
type: "review"                             # required — see post types above
slug: "wuthering-heights-review"           # optional, defaults to filename stem
date: "2026-01-15"                         # optional creation date (YYYY-MM-DD)
book_ol_key: "OL14933414W"                 # book identifier — use this for Open Library books
enrich_book: true                          # fetch book metadata from Open Library (key must start with OL)
rating: 4.5                                # review only, 0–5
tags:
  - "classics"
  - "2026"
---

Post body in Markdown...
```

For books not on Open Library, supply metadata directly instead of using `book_ol_key` + `enrich_book`:

```yaml
---
title: "My Review"
author: "Aya"
type: "review"
book_key: "remains-of-the-day"             # stable identifier for the book (any unique slug)
book_title: "The Remains of the Day"       # required when using book_key
book_authors:                              # optional list of author names
  - "Kazuo Ishiguro"
book_publication_year: 1989               # optional
book_page_count: 258                       # optional
book_description: "..."                    # optional
rating: 4.5
---
```

### Field notes

- **`title`** and **`author`** are always required.
- **`type`** must be one of the valid post types above.
- **`slug`** defaults to the filename stem (`wuthering-heights.md` → `wuthering-heights`). The slug is the stable unique identifier — changing it creates a new post and orphans the old one.
- **`date`** sets `post_created_at`. If omitted, it defaults to the time `make posts` is first run. Re-importing does not change this.
- **`book_ol_key`** is the Open Library works key (e.g. `OL14933414W`). The book must either already be in the database or have `enrich_book: true` set.
- **`enrich_book`** — set to `true` to fetch book metadata from Open Library on import. The key must start with `OL`. If the book is already in the database the fetch is skipped.
- **`book_key`** — use instead of `book_ol_key` for books not on Open Library. Any unique slug (e.g. `remains-of-the-day`). Must be paired with `book_title`.
- **`book_title`** — required when using `book_key`. The book's display title.
- **`book_authors`** — list of author name strings. Used when creating the book from frontmatter.
- **`book_publication_year`**, **`book_page_count`**, **`book_description`** — optional metadata for manually-supplied books.
- **`rating`** is only valid on `review` posts and is ignored on all other types. Must be between 0 and 5.
- **`tags`** are normalised to lowercase, deduplicated, and attached to the referenced book. New tags are created automatically.

---

## Writing a book review

### For a book on Open Library

1. Find the book's Open Library works key. Go to [openlibrary.org](https://openlibrary.org), search for the book, open the Works page, and copy the key from the URL (e.g. `OL14933414W`).

2. Add the book to `writing/book_seed.json` if you want it to appear in the book list before the review is written:

   ```json
   { "key": "OL14933414W", "enrich": true, "tags": ["2026"] }
   ```

   Run `make seed` to fetch its metadata from Open Library and insert it into the database.

3. Create a markdown file under `writing/posts/reviews/`:

   ```yaml
   ---
   title: "Wuthering Heights"
   author: "Aya"
   type: "review"
   book_ol_key: "OL14933414W"
   rating: 4.5
   date: "2026-03-10"
   tags:
     - "classics"
     - "2026"
   ---

   Opening thoughts...
   ```

4. Import:

   ```sh
   make posts
   ```

   If the book was seeded first the import is instant. If not, add `enrich_book: true` to the frontmatter to have it fetched from Open Library on import.

### For a book not on Open Library

Supply all metadata directly in the frontmatter — no seed file entry or API call needed:

```yaml
---
title: "My Review"
author: "Aya"
type: "review"
book_key: "remains-of-the-day"
book_title: "The Remains of the Day"
book_authors:
  - "Kazuo Ishiguro"
book_publication_year: 1989
book_page_count: 258
rating: 4.5
date: "2026-03-10"
tags:
  - "fiction"
---

Opening thoughts...
```

`book_key` is the stable identifier stored in the database — choose a slug that won't change (e.g. a slugified title). `book_title` is required; all other book fields are optional.

You can also seed a manual book before writing the review:

```json
{
  "key": "remains-of-the-day",
  "title": "The Remains of the Day",
  "authors": ["Kazuo Ishiguro"],
  "publication_year": 1989,
  "tags": ["fiction"]
}
```

---

## Writing a standalone post, note, or poem

No book required — just omit `book_ol_key` and `rating`:

```yaml
---
title: "Some thoughts on reading"
author: "Aya"
type: "standalone"
date: "2026-02-01"
---

Body here...
```

For poems, use `type: "poem"` and save the file anywhere under `writing/posts/` (a `poetry/` subfolder keeps things tidy):

```
writing/posts/poetry/small-hours.md
```

---

## Adding a code demo file

Code posts are created directly from source files (`.sql`, `.py`, `.js`, etc.) — no frontmatter needed. Drop the file in `writing/posts/other/` and run:

```sh
make code
```

The file is imported as a `code`-type post with:
- **slug** = the full filename (e.g. `demo.sql`)
- **URL** = `/posts/demo.sql`
- **author** = `aya` (override with `make code AUTHOR="someone"`)

The post renders as a syntax-highlighted code block with a copy button. It does not appear in the posts listing.

To link to a code post from a regular post, use the full filename as the wikilink target:

```markdown
Here is [[demo.sql|the SQL demo]] for this query.
```

Supported file extensions: `.sql`, `.py`, `.js`, `.ts`, `.sh`, `.json`, `.yaml`, `.yml`, `.html`, `.css`, `.r`, `.rb`, `.go`, `.rs`, `.c`, `.cpp`, `.java`.

---

## Inline quotes

Wrap passages you want to extract as quotes with ` ```ad-quote ` fences:

````markdown
Some introductory text.

```ad-quote
He was still, and suffering seemed to speak
in the severe simplicity of his attitude.
```

More text continues here.
````

When `make posts` runs:

- Each `ad-quote` block is extracted as a separate `quotes`-type post, linked to the parent post via `parent_id`.
- The block is replaced with standard Markdown blockquote syntax (`>`) in the rendered post body.
- Quote slugs are generated deterministically from the first 100 characters of the quote text. **Editing quote text generates a new slug and therefore a new post** — the old quote post is not automatically deleted.

The random quote widget in the sidebar pulls from all `quotes`-type posts and links back to the parent post.

---

## Linking between posts

Use Obsidian-style wikilinks to link from one post to another:

```markdown
I wrote more about this in [[wuthering-heights-review]].

Or with custom display text: [[wuthering-heights-review|my Wuthering Heights review]].
```

These are expanded to standard HTML links pointing to `/posts/<slug>` before rendering. All post types are reachable via `/posts/<slug>` regardless of type.

### Linking to headings

Link to a specific heading within any post using a `#` fragment:

```markdown
Jump to a heading in another post:
[[wuthering-heights-review#Part Two]]

With custom display text:
[[wuthering-heights-review#Part Two|the second section]]

Link to a heading within the current post:
[[#Part Two]]

Within-post link with display text:
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

- The slug is the unique identifier for a post. If two files produce the same slug, the second import updates the first post in place.
- **Renaming a file** changes the slug (if no explicit `slug` is set in frontmatter) and creates a new post. The old post is not deleted.
- **Setting `slug` explicitly** in frontmatter decouples the identifier from the filename, which is useful if you want to rename the file without breaking URLs.
- Re-running `make posts` is always safe. Existing posts are matched by slug and updated only if `title` or `post_body_markdown` has changed. `post_updated_at` is only touched on real content changes.

---

## Deploying

The recommended workflow keeps everything local — you never need to touch the server's filesystem or run seeds on the server.

### Step 1: write and import locally

```sh
make seed            # upsert books (fetches OL data where enrich=true)
make posts           # import your new/updated posts
make code            # import any new/updated code demo files
```

Or all at once: `make sync`

Optionally tweak tags:

```sh
PYTHONPATH=site uv run flask --app site/app manage-tags --book OL14933414W --add "classics"
```

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

This deletes `site/instance/site.db`, re-runs all migrations, re-seeds books from `writing/book_seed.json`, and re-imports all posts and code. OL metadata is re-fetched for seed entries with `"enrich": true`.

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
make posts        # re-import with updated schema
make deploy-db
```
