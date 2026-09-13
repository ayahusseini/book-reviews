.PHONY: build dev test

build:
	uv run python site/build.py

dev: build
	uv run python -m http.server -d site/dist 8000

test:
	uv run pytest -v
