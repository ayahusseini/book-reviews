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

### Adding reviews

To add a review, run 

```python3
uv run python3 site/scripts/post
```

## Production setup 

Generate a secret key using:
```
chmod +x scripts/generate_secret_key.sh
./scripts/generate_secret_key.sh
```

When a user interacts with a Flask application, a session cookie is used to store the session data.
The cookie is 'signed' using the secret key. This prevents session data from being accessed or tampered with. 

# Explanations
- See more notes/explanations on the design [here](/docs/design.md)