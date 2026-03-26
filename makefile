APP     = site/app
PYPATH  = site
MIGRATIONS = site/migrations
POSTS   = site/content/posts
SEEDS   = site/content/seeds/book_seed.json

.PHONY: dev seed seed-refresh posts sync test migrate shell setup tags deploy-db

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

migrate:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db migrate --directory $(MIGRATIONS) -m "$(m)"
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)

shell:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) shell

setup:
	rm -f site/instance/site.db
	$(MAKE) migrate
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
	./site/scripts/deploy-db.sh $(DEPLOY_HOST)
 
# Shorthand for flask manage-tags. Pass options via ARGS:
#   make tags ARGS="--book OL42549900W --add fiction --remove 2025"
tags:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) manage-tags $(ARGS)