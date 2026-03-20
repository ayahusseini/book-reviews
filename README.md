# Book Review Website

A Flask application for displaying book reviews and personal writing, backed by SQLite and Open Library.

See: https://husseinireads.com/books/

![main-page](docs/img/main_page_sh.png)

## Setup

Recommended setup is through [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sh
uv sync
```

Install [pre-commit hooks](https://pre-commit.com/) if you plan to commit changes:

```sh
uv run pre-commit install
```

One-off setup of the database:

```sh
make setup
```

This initialises the migrations directory, generates an initial migration from the current models, applies it, and seeds books and posts.

If the migrations directory is missing (e.g. after cloning fresh), initialise it first:

```sh
PYTHONPATH=site uv run flask --app site/app db init --directory site/migrations
make setup
```

## Development workflow

All common tasks are available from the repo root via `make`:

```sh
make dev          # start the development server
make seed         # seed books from site/content/seeds/book_seed.json
make seed-refresh # re-fetch all book metadata from Open Library and reseed
make posts        # import markdown posts from site/content/posts/
make sync         # seed books then import posts
make test         # run the test suite
make migrate      # apply pending database migrations
make migration m="describe change"  # autogenerate a new migration
make shell        # open a Flask shell with DB access
make setup        # one-off database setup (wipes and recreates)
```

## Project structure

```
book_reviews/
├── Makefile
├── site/
│   ├── app/
│   │   ├── blueprints/         ← books, posts, main route handlers
│   │   ├── database/
│   │   │   ├── models.py       ← SQLAlchemy models
│   │   │   └── upserts.py      ← batch upsert helpers
│   │   ├── templates/
│   │   ├── static/
│   │   ├── open_library.py     ← Open Library API client (pure, no Flask deps)
│   │   ├── cli.py              ← import-posts and seed-books commands
│   │   └── config.py
│   ├── content/
│   │   ├── posts/              ← markdown post files live here (gitignored)
│   │   ├── seeds/
│   │   │   └── book_seed.json  ← book seed data
│   │   ├── markdown_posts.py   ← markdown parser and MarkdownPost dataclass
│   │   └── extract_quotes.py   ← ad-quote block extraction
│   ├── migrations/
│   └── testing/
```

## Adding posts

Posts are markdown files with YAML frontmatter. Add them to `site/content/posts/` and run `make posts` to import into the database.

### Frontmatter reference

```yaml
---
title: "My Review"           # required
author: "Aya"                # required
type: "review"               # required: review | essay | standalone | note | quotes | poem
book_ol_key: "OL42549900W"   # required for review and essay posts
rating: 4.5                  # only used when type is review, must be 0–5
slug: "my-review"            # optional, defaults to the filename stem
tags:
  - "non-fiction"
  - "2026"
---

Post body in Markdown...
```

- `review` and `essay` posts should reference a book via `book_ol_key`. If the book is not already in the database it will be fetched automatically from Open Library. Omitting `book_ol_key` on these types produces a warning but the post will still be created as standalone.
- `standalone`, `note`, and `poem` posts have no book link — omit `book_ol_key`.
- `rating` is only meaningful on `review` posts and is ignored on all other types.
- Tags are normalised to lowercase and attached to the referenced book. New tags are created automatically.
- `slug` defaults to the filename stem if not set. The slug is the unique identifier for a post — changing it creates a new post.
- Re-running `make posts` is safe — existing posts are matched by slug and updated in place.

### Inline quotes

Wrap quote blocks with ` ```ad-quote ` fences in the post body:

````markdown
```ad-quote
Some memorable passage from the book.
```
````

Each block is extracted as a separate `quotes`-type post and rendered as a blockquote in the parent post. Quote slugs are generated deterministically from the content — editing quote text will create a new quote post and delete the old one.

### Book ratings

A book's rating is the average `rating` across all of its `review`-type posts. There is no manually set rating on books.

## Adding books

Books are seeded from `site/content/seeds/book_seed.json`:

```json
[
  {
    "olid": "OL42549900W",
    "comment": "Flesh",
    "tags": ["2026"]
  },
  {
    "olid": "OL166482W",
    "description": "A custom description override."
  }
]
```

Each entry requires `olid`. Optional fields:
- `tags` — attached to the book after seeding
- `description` — overrides the Open Library description

Run `make seed` to upsert from the seed file. Books already in the DB are not re-fetched from Open Library unless you run `make seed-refresh`.

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
make migration m="describe change"
make migrate
```

## Managing tags

Tags are attached to books during import (`make posts`) and seeding (`make seed`).

Use the `manage-tags` CLI command to make ad-hoc changes without re-importing anything.
 
```sh
# Add one or more tags to a book
flask manage-tags --book OL42549900W --add "fiction" --add "2026"
 
# Remove a tag from a book (does not delete the tag itself)
flask manage-tags --book OL42549900W --remove "2025"
```
 
`--add` and `--remove` can be combined in a single call:
 
```sh
flask manage-tags --book OL42549900W --add "2026" --remove "2025"
```
 
All tag names are normalised to lowercase with collapsed whitespace before being written to the database.
 
The `flask manage-tags` command is the canonical interface. 

> **Note:** avoid `make tags ARGS="..."` for tag names that contain hyphens,
> spaces, or quotes — `make` strips quoting before the shell sees it, which
> causes argument-splitting errors. Use the alias or invoke `flask manage-tags`
> directly instead.

## Generating a production secret key

```sh
chmod +x site/scripts/generate_secret_key.sh
./site/scripts/generate_secret_key.sh
```

This writes `SECRET_KEY=...` to `.env`. The script errors if a key already exists — delete the existing line manually if you genuinely need to regenerate it (this will invalidate active user sessions).

## Running tests

```sh
make test
```
---

## Deploying the database
 
For routine content updates (new posts, tag edits) it is faster to copy the local SQLite database directly to the server than to re-seed and re-import everything from scratch.
 
```sh
# One-off: export your server's address
export DEPLOY_HOST=root@your_server_ip
 
# Deploy
make deploy-db
```
 
What `make deploy-db` does:
 
1. Copies `site/instance/site.db` to the server via `scp`.
2. Restarts Gunicorn so the in-process `SimpleCache` is cleared.
 

---

## Production setup (one-off)

This section documents the full steps to deploy the app on a fresh Ubuntu VPS.

### 1. Provision the VPS and SSH in

```sh
ssh root@your_server_ip
```

### 2. Update the system and install dependencies

```sh
sudo apt update && sudo apt upgrade -y
sudo apt install nginx git python3-certbot-nginx -y
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 3. Clone the repo

```sh
sudo mkdir -p /var/www/book_reviews
sudo chown $USER:$USER /var/www/book_reviews
git clone https://github.com/ayahusseini/book-reviews.git /var/www/book_reviews
cd /var/www/book_reviews
uv sync
```

### 4. Set up environment variables

```sh
python3 site/scripts/generate_secret_key.sh
echo "FLASK_ENV=production" >> .env
```

### 5. Initialise and seed the database

```sh
PYTHONPATH=site uv run flask --app site/app db init --directory site/migrations
make setup
```

### 6. Set up Gunicorn as a systemd service

```sh
sudo nano /etc/systemd/system/gunicorn.service
```

```ini
[Unit]
Description=HusseiniReads Gunicorn
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/book_reviews/site
ExecStart=/var/www/book_reviews/.venv/bin/gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 3
Restart=always
Environment="PYTHONPATH=/var/www/book_reviews/site"

[Install]
WantedBy=multi-user.target
```

```sh
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
```

### 7. Configure Nginx and SSL

```sh
sudo nano /etc/nginx/sites-available/book_reviews
sudo ln -s /etc/nginx/sites-available/book_reviews /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
ufw allow 80 && ufw allow 443
certbot --nginx
```

---

## Updating the site
 
### Pushing new posts (recommended workflow)
 
1. Write your markdown posts under `site/content/posts/`.
2. Run `make posts` locally to import them into the local database.
3. Optionally tweak tags: `flask manage-tags --book OL123W --add "mytag"`.
4. Deploy the database to production:
 
   ```sh
   make deploy-db
   ```
 
No need to `scp` individual post files or touch the server's filesystem.
 
### Pushing code changes
 
```sh
cd /var/www/book_reviews
git pull
sudo systemctl restart gunicorn
```
 
### Pushing model/schema changes
 
If you changed `models.py`, generate and apply a migration locally first, commit it, then on the VPS:
 
```sh
cd /var/www/book_reviews
git pull
make migrate
sudo systemctl restart gunicorn
```
 
---
 
## Makefile reference
 
```
make dev        start the development server
make seed       seed books from seed_database/book_seed.json
make posts      import markdown posts from site/content/posts/
make sync       seed + posts in one step
make deploy-db  copy local DB to production and restart Gunicorn
make tags       shorthand for flask manage-tags (pass ARGS="...")
make test       run the test suite
make migrate    apply pending database migrations
make migration  generate a new migration (pass m="description")
make shell      open a Flask shell with DB access
make setup      one-off database initialisation
```
---

## Further reading

- [Design notes](/docs/design.md)
- [Flask notes](/docs/flask.md)
- [SQLAlchemy notes](/docs/sqlalchemy.md)