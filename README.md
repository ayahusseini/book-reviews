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


# Explanations

## DuckDB 

This repo uses duckdb as a database. DuckDB is distinct to PostgreSQL in that it is embedded (literally a file in the repo). The Flask app can just open it and run queries, similar to a local SQLite file. This does come with limited concurrency (only one 'write' operation can happen at a time) - not much of a bottleneck in this use case. I'm the only writer so a single-writer limitation isn't too much of a problem. Its' also columnar - I'm not planning to start with any heavy analytics but it is something I'd eventually like to do.

## Flask

Flask is a framework for building web applications. When developing locally, Flask runs as a server process locally: a tiny web server gets started on `http://127.0.0.1:5000/`. So your browser communicates with (sends requests to) the flask server via HTTP. 