APP     = site/app
PYPATH  = site
MIGRATIONS = site/migrations
POSTS   = writing/posts
SEEDS   = writing/book_seed.json

.PHONY: dev seed seed-refresh posts sync test migrate shell setup reset install tags deploy-db

dev:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) run --debug

seed:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) seed-books --path $(SEEDS)

seed-refresh:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) seed-books --path $(SEEDS) --refresh

posts:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) import-posts --path $(POSTS)

sync: seed posts restart

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

# Wipe the database and rebuild from scratch (re-fetches all OL data).
reset:
	uv sync
	rm -f site/instance/site.db
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)
	$(MAKE) sync

# Copy the local SQLite database to production and restart Gunicorn.
# Set DEPLOY_HOST=user@host in your environment or pass it on the command line:
#   make deploy-db DEPLOY_HOST=root@1.2.3.4
deploy-db:
	@if [ -z "$(DEPLOY_HOST)" ]; then \
		echo "ERROR: DEPLOY_HOST is not set."; \
		echo "  Usage:  make deploy-db DEPLOY_HOST=root@your_server_ip"; \
		echo "  Or:     export DEPLOY_HOST=root@your_server_ip"; \
		exit 1; \
	fi
	./site/scripts/deploy_db.sh $(DEPLOY_HOST)
 
# Shorthand for flask manage-tags. Pass options via ARGS:
#   make tags ARGS="--book OL42549900W --add fiction --remove 2025"
tags:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) manage-tags $(ARGS)