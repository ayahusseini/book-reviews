APP     = site/app
PYPATH  = site
MIGRATIONS = site/migrations
POSTS   = site/content/posts
SEEDS   = site/content/seeds/book_seed.json

.PHONY: dev seed seed-refresh posts sync test migrate migration shell setup

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
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade --directory $(MIGRATIONS)

migration:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db migrate --directory $(MIGRATIONS) -m "$(m)"

shell:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) shell

setup:
	rm -f site/instance/site.db
	$(MAKE) migration m="initial"
	$(MAKE) migrate
	$(MAKE) sync