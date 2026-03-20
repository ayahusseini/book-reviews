APP     = site/app
PYPATH  = site
MIGRATIONS = site/migrations
POSTS   = site/content/posts

.PHONY: dev seed posts sync test migrate migration shell setup

dev:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) run --debug

seed:
	PYTHONPATH=$(PYPATH) uv run python -m seed_database.convertor

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
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) shell -c "from app.extensions import db; db.create_all()"
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db stamp head --directory $(MIGRATIONS)
	$(MAKE) migrate
	$(MAKE) sync