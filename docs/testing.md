# Testing

## Table of contents

1. [Running the tests](#running-the-tests)
2. [Test structure](#test-structure)
3. [Fixtures](#fixtures)
4. [Writing a new test](#writing-a-new-test)
5. [What to test](#what-to-test)
6. [What not to test](#what-not-to-test)

---

## Running the tests

```sh
make test          # run all tests with verbose output
uv run pytest -q   # quieter output
uv run pytest site/testing/test_upsert.py   # run one file
uv run pytest -k "test_creates_new_tags"    # run one test by name
```

Tests use an **in-memory SQLite database** and a **null cache** — no files are touched and no network requests are made.

---

## Test structure

```
site/testing/
├── conftest.py              ← shared fixtures (app, db, session, client)
├── test_app_init.py         ← app factory and config mapping
├── test_logging.py          ← logging setup
├── test_models.py           ← SQLAlchemy model reprs and registration
├── test_open_library.py     ← Open Library API client (parsing functions)
├── test_extract_quotes.py   ← ad-quote block extraction
├── test_markdown_posts.py   ← frontmatter parsing, wikilinks, HTML rendering
├── test_upsert.py           ← database write operations (upsert_*)
└── test_routes.py           ← HTTP routes (status codes, rendered content)
```

Each file maps to one source module. Tests within a file are grouped into
classes by the function or behaviour they cover.

---

## Fixtures

Fixtures are defined in `conftest.py` and are available to all test files automatically.

### `app`

A Flask application instance configured for testing (in-memory SQLite, no cache). Created once for the entire test session.

```python
def test_something(app):
    assert app.config["TESTING"] is True
```

### `db`

A clean database for one test. Creates all tables before the test, drops them after. Use this when you need direct database access without transaction isolation.

```python
def test_something(db):
    from app.database.models import Book
    book = Book(book_ol_key="OL1W", book_title="Dune")
    db.session.add(book)
    db.session.commit()
```

### `session`

A **transactional** database session. All changes are rolled back automatically after each test — nothing is committed to the actual database. Use this for most tests that need database access.

```python
def test_something(session):
    from app.database.models import Tag
    tag = Tag(tag_name="fiction")
    session.add(tag)
    session.flush()  # makes the tag visible within this transaction
    assert session.query(Tag).count() == 1
    # After the test, the transaction is rolled back — Tag is gone
```

### `client`

A Flask test client for making HTTP requests. Depends on `session`, so routes can see data you set up in the test.

```python
def test_something(client, session):
    from app.database.models import Book
    book = Book(book_ol_key="OL1W", book_title="Dune")
    session.add(book)
    session.flush()

    response = client.get(f"/books/{book.book_id}")
    assert response.status_code == 200
    assert b"Dune" in response.data
```

### `execute_spy`

Wraps `session.execute` with a `MagicMock` so you can assert on the number of bulk SQL operations. Useful for verifying that batch operations don't regress to N+1 queries.

```python
def test_something(session, execute_spy):
    upsert_books([...])
    assert execute_spy.call_count == 4  # 1 books, 1 authors, 1 tags, 1 tag-map
```

---

## Writing a new test

### 1. Pick the right file

Add your test to the file that corresponds to the module you're testing. If no file exists yet, create `test_<module_name>.py`.

### 2. Group related tests in a class

```python
class TestUpsertTags:
    def test_creates_new_tags(self, session): ...
    def test_returns_existing_tags(self, session): ...
```

Class names start with `Test` + the function or concept under test. This keeps related tests together and makes failures easier to read.

### 3. One assertion per test (usually)

Each test should verify one specific behaviour. If a test fails, its name should tell you exactly what broke.

```python
# Good — one clear thing being tested
def test_upsert_tags_deduplicates_input(self, session):
    result = upsert_tags(["poetry", "poetry"])
    assert len(result) == 1

# Less clear — multiple things at once
def test_upsert_tags(self, session):
    result = upsert_tags(["a", "a", "b"])
    assert len(result) == 2
    assert "a" in result
    assert result["a"].tag_id is not None
    ...
```

### 4. Use `tmp_path` for markdown file tests

The built-in `tmp_path` fixture gives you a temporary directory. Write `.md` files there to test the parser:

```python
def test_missing_title_raises(self, tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\nauthor: Aya\ntype: standalone\n---\nbody")
    with pytest.raises(ValueError, match="title"):
        parse_markdown_with_frontmatter(path)
```

### 5. Use `session.flush()` not `session.commit()`

In tests that use the `session` fixture, call `session.flush()` to make objects visible within the current transaction without permanently committing them. This keeps tests isolated.

### 6. Name tests as sentences

```python
def test_review_without_book_raises()        # ✓ clear
def test_upsert_post_review_validation()     # ✗ vague
```

---

## What to test

Focus on logic that is easy to get wrong and hard to notice without a test:

- **Validation** — what happens when required fields are missing or invalid
- **Edge cases** — empty inputs, duplicate slugs, missing optional fields
- **Side effects** — does `upsert_post` actually set `book.book_rating`?
- **Route status codes** — does `/books/999` return 404 and not 500?
- **Content in responses** — does the book detail page show the title?

---

## What not to test

- **Flask and SQLAlchemy internals** — don't test that `db.session.add()` works
- **Open Library HTTP requests** — the `test_open_library.py` tests cover the parsing logic; network calls are not made in tests
- **Template layout and CSS** — testing that a `<div>` has a specific class is brittle and not worth it
- **Obvious one-liners** — a function that just returns `works_data["title"]` doesn't need a test

---

## Adding a fixture

If multiple tests need the same setup, add a helper fixture to the relevant test file (not conftest unless it's needed across files):

```python
# At the top of test_upsert.py

def make_book(session, ol_key="OL1W", title="A Book"):
    book = Book(book_ol_key=ol_key, book_title=title)
    session.add(book)
    session.flush()
    return book
```

Keep factory functions simple — one model, minimal required fields, sensible defaults.
