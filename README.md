# Book Review Website


# Setup 

Reccomended setup is through [uv](https://docs.astral.sh/uv/getting-started/installation/). 

## Quick Start (using notebooks)

If you just want to use `notebooks/` to explore problems

```sh
uv sync
```

You do not need the dev setup if you aren't intending to change `src/` code 

Alternatively, you can set up using `pip`:

```sh
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e .
```

## Different Configs

The Flask application accepts different configs:
- **Development** is the local environment used when actively building. It has debug mode on - Flask auto-reloads on code changes, shows detailed error pages and verbose logs. 
- **Testing** is an isolated environment used when running the test suite. The key difference is that it uses a seperate, throwaway database.
- **Production** is the live, deployed app. Debug is strictly off. It uses the same database as development but this is accessed as a stable path within Docker. Errors are logged quietly. 

## Development setup 

If you plan to modify code, run tests, or commit changes:

1. Install dependencies 

```sh
uv sync
```

2. Install [pre-commit hooks](https://pre-commit.com/)

```sh
uv run pre-commit install
```

These enforce:
- Formatting via Ruff
- Lockfile validation via uv
- Shell + workflow checks

3. Run the development server. The Flask CLI knows how to find and call `create_app()` automatically when you point `--app` at the `site/app` package. 

```sh
uv run flask --app site/app run
```

This defaults to running with the `DevelopmentConfig`. You can switch configs at the command line:

```sh
# development (default)
uv run flask --app site/app run --debug

# testing
FLASK_ENV=testing uv run flask --app site/app run

# production
FLASK_ENV=production uv run flask --app site/app run
```

### Seeding 

```sh
cd site
uv run python -m app.database.convertor
```

### Using the Flask Shell

The Flask Shell is a Python REPL that runs inside the application context. `db`, models, and anything else that is configured are already available. The 
Flask Shell is useful for querying the database and playing with app config:

```sh
uv run flask --app site/app shell
```

Within the REPL, you can run commands like:

```python
from app.models import Book, Author 
Book.query.all()
db.session.execute(...)
```

### Querying the local DB

The development DB is a local SQLite3 file, you can query it like so:

```sh
sqlite3 site/instance/site.db "SELECT * from book"
```

### Running tests

Run 

```
uv run pytest -v
```

## Running helper modules (must be run from `site/`)

Some internal helpers live under `site/app`. Running them from the repository root normally fails with:

> ModuleNotFoundError: No module named 'app'

To avoid that, either:

- run from inside `site/`, or
- set `PYTHONPATH=site` when invoking Python.

For example, to run the Open Library helper:

```sh
cd site
uv run python -m app.database.open_library
```

Or (from the repo root):

```sh
PYTHONPATH=site uv run python -m app.database.open_library OL2743111W
```

## Production setup 

Generate a secret key using:

```sh
chmod +x scripts/generate_secret_key.sh
./scripts/generate_secret_key.sh
```

When a user interacts with a Flask application, a session cookie is used to store the session data.
The cookie is 'signed' using the secret key. This prevents session data from being accessed or tampered with. 

# Explanations
- See more notes/explanations on the design [here](/docs/design.md)