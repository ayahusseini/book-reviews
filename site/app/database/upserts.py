"""Batch upsert helpers for SQLAlchemy models.

All functions operate within the caller's session and never commit.
Flush is used where IDs are needed to build subsequent statements.
Callers (CLI commands) are responsible for session.commit().

Insert and update operations use db.session.execute() with bulk mappings
rather than ORM add/append, which would emit one statement per row.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database.models import (
    Author,
    Book,
    BookAuthorMapping,
    BookToTagMapping,
    Post,
    Tag,
)
from app.extensions import db
from app.open_library import AuthorData, BookData


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
    """Return a {ol_id: Author} mapping for all requested authors.

    Inserts new authors and updates names of existing ones, both in bulk.
    """
    if not author_datas:
        return {}

    by_ol_id = {a.ol_id: a for a in author_datas}  # dedupe
    ol_ids = list(by_ol_id.keys())

    existing = {
        a.author_ol_id: a
        for a in Author.query.filter(Author.author_ol_id.in_(ol_ids)).all()
    }

    new_datas = [a for a in by_ol_id.values() if a.ol_id not in existing]
    update_datas = [a for a in by_ol_id.values() if a.ol_id in existing]

    if new_datas:
        db.session.execute(
            sqlite_insert(Author),
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

    if update_datas:
        db.session.execute(
            update(Author),
            [
                {"author_ol_id": a.ol_id, "author_name": a.name}
                for a in update_datas
            ],
        )
        for a in update_datas:
            existing[a.ol_id].author_name = a.name

    return {**existing, **new_authors}


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------


def _book_to_row(b: BookData, description_overrides: dict[str, str]) -> dict:
    return {
        "book_ol_key": b.ol_key,
        "book_title": b.title,
        "book_isbn": b.isbn,
        "book_description": description_overrides.get(b.ol_key, b.description),
        "book_publication_year": b.publication_year,
        "book_page_count": b.page_count,
    }


def _insert_books(
    new_datas: list[BookData], description_overrides: dict[str, str]
) -> dict[str, Book]:
    db.session.execute(
        sqlite_insert(Book),
        [_book_to_row(b, description_overrides) for b in new_datas],
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
) -> None:
    db.session.execute(
        update(Book),
        [_book_to_row(b, description_overrides) for b in update_datas],
    )
    for b in update_datas:
        book = existing[b.ol_key]
        row = _book_to_row(b, description_overrides)
        book.book_title = row["book_title"]
        book.book_isbn = row["book_isbn"]
        book.book_description = row["book_description"]
        book.book_publication_year = row["book_publication_year"]
        book.book_page_count = row["book_page_count"]


def _attach_authors(
    book_datas: list[BookData],
    result: dict[str, Book],
    author_map: dict[str, Author],
) -> None:
    book_ids = [b.book_id for b in result.values()]
    existing = {
        (m.book_id, m.author_id)
        for m in BookAuthorMapping.query.filter(
            BookAuthorMapping.book_id.in_(book_ids)
        ).all()
    }

    new_mappings = [
        {
            "book_id": result[b.ol_key].book_id,
            "author_id": author_map[a.ol_id].author_id,
        }
        for b in book_datas
        for a in b.authors
        if a.ol_id in author_map
        and (result[b.ol_key].book_id, author_map[a.ol_id].author_id)
        not in existing
    ]

    if new_mappings:
        db.session.execute(
            sqlite_insert(BookAuthorMapping).on_conflict_do_nothing(),
            new_mappings,
        )


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
    description_overrides: dict[str, str] | None = None,
) -> dict[str, Book]:
    """Upsert a batch of books and their relationships.

    Returns {ol_key: Book} for all processed books.
    """
    if not book_datas:
        return {}

    tag_map = tag_map or {}
    description_overrides = description_overrides or {}

    ol_keys = [b.ol_key for b in book_datas]
    existing = {
        b.book_ol_key: b
        for b in Book.query.filter(Book.book_ol_key.in_(ol_keys)).all()
    }

    new_datas = [b for b in book_datas if b.ol_key not in existing]
    update_datas = [b for b in book_datas if b.ol_key in existing]

    new_books = (
        _insert_books(new_datas, description_overrides) if new_datas else {}
    )
    if update_datas:
        _update_books(update_datas, existing, description_overrides)

    result = {**existing, **new_books}

    all_author_datas = [a for b in book_datas for a in b.authors]
    author_map = upsert_authors(all_author_datas)

    _attach_authors(book_datas, result, author_map)
    _attach_book_tags(book_datas, result, tag_map)

    return result


def upsert_single_book(ol_key: str) -> Book:
    """Return the Book for ol_key, or fetch from Open Library and create it.

    Used by the post importer when a referenced book is not in the DB.
    Does not commit — caller is responsible.
    """
    book = Book.query.filter_by(book_ol_key=ol_key).first()
    if book:
        return book

    from app.open_library import fetch_book_data

    book_data = fetch_book_data(ol_key)
    books = upsert_books([book_data])
    return books[ol_key]


def upsert_post(
    *,
    slug: str,
    title: str,
    author: str,
    body: str,
    post_type: str | None,
    post_rating: float | None,
    book: Book | None,
    created_at: datetime | None = None,
) -> tuple[Post, bool]:
    """Update an existing post (looked up by slug) or create a new one.

    Returns (post, is_new). Does not commit.
    """
    post = Post.query.filter_by(post_slug=slug).first()
    is_new = post is None

    if is_new:
        post = Post(
            post_slug=slug,
            post_title=title,
            post_body_markdown=body,
            post_type=post_type,
            post_author=author,
            post_rating=post_rating,
            book=book,
            post_created_at=created_at or datetime.now(timezone.utc),
        )
        db.session.add(post)
    else:
        post.post_title = title
        post.post_body_markdown = body
        post.post_type = post_type
        post.post_author = author
        post.post_rating = post_rating
        post.book = book
        # deliberately never update post_created_at on re-import

    return post, is_new


def attach_tags(book: Book, tag_names: list[str]) -> None:
    """Add any missing tags to a book via a single bulk junction insert.

    Used by the post importer to attach per-post tags to the book.
    """
    if not tag_names:
        return

    tag_name_map = upsert_tags(tag_names)

    existing_tag_ids = {
        m.tag_id
        for m in BookToTagMapping.query.filter_by(book_id=book.book_id).all()
    }

    new_mappings = [
        {"book_id": book.book_id, "tag_id": tag.tag_id}
        for tag in tag_name_map.values()
        if tag.tag_id not in existing_tag_ids
    ]

    if new_mappings:
        db.session.execute(
            sqlite_insert(BookToTagMapping).on_conflict_do_nothing(),
            new_mappings,
        )
