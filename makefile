APP     = site/app
PYPATH  = site
MIGRATIONS = site/migrations
POSTS   = writing/posts
CODE    = writing/posts/other
SEEDS   = writing/book_seed.json
AUTHOR  = aya

.PHONY: dev seed posts code sync test migrate shell setup reset reset-posts install tags deploy-db

dev:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) run --debug

seed:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) seed-books --path $(SEEDS)

posts:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) import-posts --path $(POSTS)

code:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) import-code --path $(CODE) --author "$(AUTHOR)"

sync: posts code restart

restart:
	touch site/app/__init__.py

test:
	uv run pytest -v

# Only run migrations manually when you want to generate them
# Usage: make migrate MSG="Add book_rating column"
migrate:
ifndef MSG
	$(error MSG is undefined. Use e.g. make migrate MSG="Add book_rating column")
endif
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db migrate --directory $(MIGRATIONS) -m "$(MSG)"
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)

# Quick upgrade without creating a new migration
upgrade:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)

# Stamp DB to current head (useful if DB is already manually correct)
stamp:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db stamp head --directory $(MIGRATIONS)
# Launch a Flask shell
shell:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) shell

install:
	uv sync

# Apply any pending migrations and sync content. Safe to run repeatedly —
# skips OL fetches for books already in the DB.
setup:
	uv sync
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)
	$(MAKE) sync

# Wipe the database and rebuild from scratch.
# OL metadata is re-fetched for seed entries that have "enrich": true.
reset:
	uv sync
	rm -f site/instance/site.db
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)
	$(MAKE) sync

# Delete all posts from the local DB and re-import from markdown.
# Books, authors, and tags are not touched.
reset-posts:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) reset-posts --path $(POSTS)

# Copy the local SQLite database to production and restart Gunicorn.
# Host is read from .env (VPS_USER + VPS_HOST). Override with DEPLOY_HOST:
#   make deploy-db DEPLOY_HOST=root@1.2.3.4
deploy-db:
	./site/scripts/deploy_db.sh $(if $(DEPLOY_HOST),$(DEPLOY_HOST),)
 
# Shorthand for flask manage-tags. Pass options via ARGS:
#   make tags ARGS="--book OL42549900W --add fiction --remove 2025"
tags:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) manage-tags $(ARGS)