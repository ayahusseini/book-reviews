APP     = site/app
PYPATH  = site
MIGRATIONS = site/migrations
POSTS   = writing/posts
SEEDS   = writing/book_seed.json

.PHONY: dev seed sync test migrate upgrade stamp shell setup reset reset-posts restart

dev:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) run --debug

seed:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) seed-books --path $(SEEDS)

sync: seed reset-posts restart

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

# Apply any pending migrations and sync content. Safe to run repeatedly.
setup:
	uv sync
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)
	$(MAKE) sync

# Wipe the database and rebuild from scratch.
reset:
	uv sync
	rm -f site/instance/site.db
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)
	$(MAKE) sync

# Clear reviews, poems, and quotes from the local DB and re-import from
# writing/posts/{reviews,poetry}. Books, authors, and tags are not touched.
reset-posts:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) reset-posts --path $(POSTS)

# Deploy to production: see site/scripts/deploy.sh
# ./site/scripts/deploy.sh [--reset-database]
