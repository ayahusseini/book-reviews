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
PYTHONPATH=site uv run flask --app site/app shell
```

Inside the shell:

```python
from app.extensions import db
db.create_all()
exit()
```

Then stamp and migrate:

```sh
PYTHONPATH=site uv run flask --app site/app db stamp head --directory site/migrations
make migrate
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

This writes `SECRET_KEY=...` to `.env`. The script will error if a key already exists — delete the existing line manually if you genuinely need to regenerate it (note: this will invalidate active user sessions).

## Running tests

```sh
make test
```

---

## Production setup (one-off)

This section documents the full steps to deploy the app on a fresh Ubuntu VPS (e.g. Vultr, Hetzner, DigitalOcean).

### 1. Provision the VPS and SSH in

Rent a VPS running Ubuntu. SSH in as root:

```sh
ssh root@your_server_ip
```

### 2. Update the system and install dependencies

```sh
sudo apt update && sudo apt upgrade -y
sudo apt install nginx git python3-certbot-nginx -y
```

Install uv:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 3. Clone the repo

```sh
sudo mkdir -p /var/www/book_reviews
sudo chown $USER:$USER /var/www/book_reviews
git clone https://github.com/ayahusseini/book-reviews.git /var/www/book_reviews
cd /var/www/book_reviews
```

### 4. Install Python dependencies

```sh
uv sync
```

### 5. Set up environment variables

Generate a secret key and set the Flask environment:

```sh
python3 site/scripts/generate_secret_key.sh
echo "FLASK_ENV=production" >> .env
```

Verify `.env` looks correct:

```sh
cat .env
```

You should see exactly two lines: `SECRET_KEY=...` and `FLASK_ENV=production`.

### 6. Set up the database

Create the base schema, stamp it, then run migrations:

```sh
PYTHONPATH=site uv run flask --app site/app shell
```

Inside the shell:

```python
from app.extensions import db
db.create_all()
exit()
```

Then stamp and migrate:

```sh
PYTHONPATH=site uv run flask --app site/app db stamp head --directory site/migrations
make migrate
```

### 7. Seed the database

```sh
make seed
make posts
```

### 8. Set up Gunicorn as a systemd service

Create the service file:

```sh
sudo nano /etc/systemd/system/gunicorn.service
```

Paste in:

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

Enable and start it:

```sh
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
sudo systemctl status gunicorn
```

You should see `active (running)`.

### 9. Configure Nginx

Create the config:

```sh
sudo nano /etc/nginx/sites-available/book_reviews
```
and configure nginx. Enable it and restart:

```sh
sudo ln -s /etc/nginx/sites-available/book_reviews /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 10. Set up SSL with certbot

Open the firewall ports and run certbot:

```sh
ufw allow 80
ufw allow 443
certbot --nginx
```

Follow the prompts. Certbot will automatically update your Nginx config to handle HTTPS and set up certificate renewal.

---

## Updating the site

### Pushing new posts

Since `content/posts/` is gitignored, posts must be copied to the server manually via `scp`. From your laptop:

```sh
scp -r site/content/posts root@the_server_id:/var/www/book_reviews/site/content/posts/
```

Then on the VPS:

```sh
cd /var/www/book_reviews
make posts
```

Note: if this is the first time copying posts to a fresh server, you may need to create the directory first:

```sh
mkdir -p /var/www/book_reviews/site/content/posts
```

### Pushing code changes

```sh
cd /var/www/book_reviews
git pull
sudo systemctl restart gunicorn
```

### Pushing model changes

If you changed `models.py`, generate and apply a migration locally first, commit it, then on the VPS:

```sh
cd /var/www/book_reviews
git pull
make migrate
sudo systemctl restart gunicorn
```

---

## Further reading

- [Design notes](/docs/design.md)
- [Flask notes](/docs/flask.md)
- [SQLAlchemy notes](/docs/sqlalchemy.md)
