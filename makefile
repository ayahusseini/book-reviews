# Makefile
APP     = site/app
PYPATH  = site

.PHONY: dev seed posts sync test migrate shell

dev:
	uv run flask --app $(APP) run --debug

seed:
	PYTHONPATH=$(PYPATH) uv run python -m seed_database.convertor

posts:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) import-posts

sync: seed posts

test:
	uv run pytest -v

migrate:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) db upgrade

shell:
	PYTHONPATH=$(PYPATH) uv run flask --app $(APP) shell