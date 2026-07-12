"""Batch upsert helpers for SQLAlchemy models.

All functions operate within the caller's session and never commit.
Flush is used where IDs are needed to build subsequent statements.
Callers (CLI commands) are responsible for session.commit().

Insert operations use db.session.execute() with bulk mappings
rather than ORM add/append, which would emit one statement per row.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.backend.models import (
    Author,
    Book,
    BookToTagMapping,
    Poem,
    Quote,
    Tag,
)
from app.backend.extract_quotes import ExtractedQuote
from app.extensions import db
from app.backend.book_data import AuthorData, BookData


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def upsert_tags(tag_names: list[str]) -> dict[str, Tag]:
    """Return a {tag_name: Tag} mapping for all requested tag names.

    New tags are inserted in a single statement.
    Existing tags are returned as-is (tag_name is immutable).
    """
    if not tag_names:
        return {}

    unique_names = list(dict.fromkeys(tag_names))

    existing = {
        t.tag_name: t
        for t in Tag.query.filter(Tag.tag_name.in_(unique_names)).all()
    }

    new_names = [n for n in unique_names if n not in existing]

    if new_names:
        db.session.execute(
            sqlite_insert(Tag),
            [{"tag_name": name} for name in new_names],
        )
        db.session.flush()
        new_tags = {
            t.tag_name: t
            for t in Tag.query.filter(Tag.tag_name.in_(new_names)).all()
        }
    else:
        new_tags = {}

    return {**existing, **new_tags}


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------


def upsert_authors(author_datas: list[AuthorData]) -> dict[str, Author]:
    """Insert new authors by ol_id, return {ol_id: Author} for all given."""
    if not author_datas:
        return {}

    ol_ids = list({a.ol_id for a in author_datas})

    existing = {
        a.author_ol_id: a
        for a in Author.query.filter(Author.author_ol_id.in_(ol_ids)).all()
    }

    new_datas = [a for a in author_datas if a.ol_id not in existing]

    if new_datas:
        db.session.execute(
            sqlite_insert(Author).on_conflict_do_nothing(),
            [
                {"author_name": a.name, "author_ol_id": a.ol_id}
                for a in new_datas
            ],
        )
        db.session.flush()
        new_authors = {
            a.author_ol_id: a
            for a in Author.query.filter(
                Author.author_ol_id.in_([a.ol_id for a in new_datas])
            ).all()
        }
    else:
        new_authors = {}

    return {**existing, **new_authors}


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------


def _book_to_row(
    b: BookData,
    description_overrides: dict[str, str],
    rating_map: dict[str, float],
    title_overrides: dict[str, str] | None = None,
) -> dict:
    return {
        "book_ol_key": b.ol_key,
        "book_title": (title_overrides or {}).get(b.ol_key, b.title),
        "book_description": description_overrides.get(b.ol_key, b.description),
        "book_publication_year": b.publication_year,
        "book_page_count": b.page_count,
        "book_rating": rating_map.get(b.ol_key),
    }


def _insert_books(
    new_datas: list[BookData],
    description_overrides: dict[str, str],
    rating_map: dict[str, float],
    title_overrides: dict[str, str],
) -> dict[str, Book]:
    db.session.execute(
        sqlite_insert(Book),
        [
            _book_to_row(b, description_overrides, rating_map, title_overrides)
            for b in new_datas
        ],
    )
    db.session.flush()
    return {
        b.book_ol_key: b
        for b in Book.query.filter(
            Book.book_ol_key.in_([b.ol_key for b in new_datas])
        ).all()
    }


def _update_books(
    update_datas: list[BookData],
    existing: dict[str, Book],
    description_overrides: dict[str, str],
    rating_map: dict[str, float],
    title_overrides: dict[str, str],
) -> None:
    for b in update_datas:
        book = existing[b.ol_key]
        row = _book_to_row(
            b, description_overrides, rating_map, title_overrides
        )
        book.book_title = row["book_title"]
        book.book_description = row["book_description"]
        book.book_publication_year = row["book_publication_year"]
        book.book_page_count = row["book_page_count"]
        if row["book_rating"] is not None:
            book.book_rating = row["book_rating"]


def _attach_authors(
    book_datas: list[BookData],
    result: dict[str, Book],
    author_map: dict[str, Author],
) -> None:
    for book_data in book_datas:
        book = result.get(book_data.ol_key)
        if book is None:
            continue
        for a in book_data.authors:
            author = author_map.get(a.ol_id)
            if author and author not in book.authors:
                book.authors.append(author)


def _attach_book_tags(
    book_datas: list[BookData],
    result: dict[str, Book],
    tag_map: dict[str, list[str]],
) -> None:
    all_tag_names = list(
        {name for tag_names in tag_map.values() for name in tag_names}
    )
    if not all_tag_names:
        return

    tag_name_map = upsert_tags(all_tag_names)

    book_ids = [b.book_id for b in result.values()]
    existing = {
        (m.book_id, m.tag_id)
        for m in BookToTagMapping.query.filter(
            BookToTagMapping.book_id.in_(book_ids)
        ).all()
    }

    new_mappings = [
        {
            "book_id": result[ol_key].book_id,
            "tag_id": tag_name_map[name].tag_id,
        }
        for ol_key, tag_names in tag_map.items()
        if ol_key in result
        for name in tag_names
        if name in tag_name_map
        and (result[ol_key].book_id, tag_name_map[name].tag_id) not in existing
    ]

    if new_mappings:
        db.session.execute(
            sqlite_insert(BookToTagMapping).on_conflict_do_nothing(),
            new_mappings,
        )


def upsert_books(
    book_datas: list[BookData],
    tag_map: dict[str, list[str]] | None = None,
    rating_map: dict[str, float] | None = None,
    description_overrides: dict[str, str] | None = None,
    title_overrides: dict[str, str] | None = None,
) -> dict[str, Book]:
    """Upsert a batch of books and their relationships.

    Returns {ol_key: Book} for all processed books.
    """
    if not book_datas:
        return {}

    tag_map = tag_map or {}
    rating_map = rating_map or {}
    description_overrides = description_overrides or {}
    title_overrides = title_overrides or {}

    ol_keys = [b.ol_key for b in book_datas]

    existing = {
        b.book_ol_key: b
        for b in Book.query.filter(Book.book_ol_key.in_(ol_keys)).all()
    }

    new_datas = [b for b in book_datas if b.ol_key not in existing]
    update_datas = [b for b in book_datas if b.ol_key in existing]

    new_books = (
        _insert_books(
            new_datas, description_overrides, rating_map, title_overrides
        )
        if new_datas
        else {}
    )

    if update_datas:
        _update_books(
            update_datas,
            existing,
            description_overrides,
            rating_map,
            title_overrides,
        )

    result = {**existing, **new_books}

    all_author_datas = [a for b in book_datas for a in b.authors]
    author_map = upsert_authors(all_author_datas)

    _attach_authors(book_datas, result, author_map)
    _attach_book_tags(book_datas, result, tag_map)

    return result


def upsert_review(
    *,
    book: Book,
    body: str,
    created_at: datetime | None = None,
) -> tuple[Book, bool]:
    """Set a book's review content, tracking created/updated timestamps.

    Does not commit — caller is responsible.
    """
    is_new = book.review_markdown is None
    content_changed = book.review_markdown != body

    book.review_markdown = body

    if content_changed:
        book.review_updated_at = datetime.now(timezone.utc)

    if created_at is not None and book.review_created_at is None:
        book.review_created_at = created_at

    return book, is_new


def upsert_poem(
    *,
    slug: str,
    title: str,
    author: str,
    body: str,
    created_at: datetime | None = None,
) -> tuple[Poem, bool]:
    """Insert or update a poem by slug. Does not commit."""
    poem = Poem.query.filter_by(poem_slug=slug).first()
    is_new = poem is None

    if is_new:
        poem = Poem(
            poem_slug=slug,
            poem_title=title,
            poem_body_markdown=body,
            poem_author=author,
            poem_created_at=created_at,
        )
        db.session.add(poem)
    else:
        content_changed = (
            poem.poem_body_markdown != body or poem.poem_title != title
        )
        poem.poem_title = title
        poem.poem_body_markdown = body
        poem.poem_author = author

        if content_changed:
            poem.poem_updated_at = datetime.now(timezone.utc)

        if created_at is not None and poem.poem_created_at is None:
            poem.poem_created_at = created_at

    return poem, is_new


def sync_quotes_for_book(book: Book, quotes: list[ExtractedQuote]) -> None:
    """Upsert quotes by slug, attached to book."""
    for extracted in quotes:
        quote = Quote.query.filter_by(quote_slug=extracted.quote_slug).first()
        if quote is None:
            quote = Quote(
                quote_slug=extracted.quote_slug,
                quote_text=extracted.quote_text,
                book=book,
            )
            db.session.add(quote)
        else:
            quote.quote_text = extracted.quote_text
            quote.book = book


def sync_tags(book: Book, tag_names: list[str]) -> None:
    """Sync a book's tags to exactly tag_names, adding and removing as needed.

    Used by the seed command so that removing a tag from the seed file
    removes it from the book on the next sync.
    """
    desired = set(tag_names)
    tag_name_map = upsert_tags(list(desired)) if desired else {}

    for tag in list(book.tags):
        if tag.tag_name not in desired:
            book.tags.remove(tag)

    existing_names = {t.tag_name for t in book.tags}
    for name, tag in tag_name_map.items():
        if name not in existing_names:
            book.tags.append(tag)
