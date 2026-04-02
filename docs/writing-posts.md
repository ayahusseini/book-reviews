# Writing and deploying posts

## Table of contents

1. [Post types](#post-types)
2. [Frontmatter reference](#frontmatter-reference)
3. [Writing a book review](#writing-a-book-review)
4. [Writing a standalone post, note, or poem](#writing-a-standalone-post-note-or-poem)
5. [Inline quotes](#inline-quotes)
6. [Slugs and re-importing](#slugs-and-re-importing)
7. [Deploying](#deploying)

---

## Post types

| Type | URL | Needs a book? | Notes |
|---|---|---|---|
| `review` | `/books/<id>` | Yes | One per book. Sets the book's rating. |
| `essay` | `/books/<id>` | Yes (recommended) | Longer piece about a book. |
| `standalone` | `/posts/<slug>` | No | General post with no book link. |
| `note` | `/posts/<slug>` | No | Short post with no book link. |
| `poem` | `/poems/<slug>` | No | Displayed on the poems page. |
| `designdoc` | `/design/all` | No | Site design notes. |
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
book_ol_key: "OL14933414W"                 # required for review and essay
rating: 4.5                                # review only, 0–5
tags:
  - "classics"
  - "2026"
---

Post body in Markdown...
```

### Field notes

- **`title`** and **`author`** are always required.
- **`type`** must be one of the valid post types above.
- **`slug`** defaults to the filename stem (`wuthering-heights.md` → `wuthering-heights`). The slug is the stable unique identifier — changing it creates a new post and orphans the old one.
- **`date`** sets `post_created_at`. If omitted, it defaults to the time `make posts` is first run. Re-importing does not change this.
- **`book_ol_key`** is the Open Library works key (e.g. `OL14933414W`). If the book is not already in the database it will be fetched automatically from Open Library.
- **`rating`** is only valid on `review` posts and is ignored on all other types. Must be between 0 and 5.
- **`tags`** are normalised to lowercase, deduplicated, and attached to the referenced book. New tags are created automatically.

---

## Writing a book review

1. Find the book's Open Library works key. Go to [openlibrary.org](https://openlibrary.org), search for the book, open the Works page, and copy the key from the URL (e.g. `OL14933414W`).

2. Add the book to `writing/book_seed.json` if you want it to appear in the book list before the review is written:

   ```json
   { "olid": "OL14933414W", "tags": ["2026"] }
   ```

3. Create a markdown file under `writing/posts/reviews/`:

   ```
   writing/posts/reviews/wuthering-heights.md
   ```

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

   The book is fetched from Open Library automatically if it is not already in the database. Running `make posts` again after editing the file updates the post in place.

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
make posts           # import your new/updated posts
```

Optionally tweak tags:

```sh
PYTHONPATH=site uv run flask --app site/app manage-tags --book OL14933414W --add "classics"
```

### Step 2: push the database

```sh
export DEPLOY_HOST=root@your_server_ip
make deploy-db
```

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
