from app.database.upserts import upsert_books
from app.open_library import BookData, AuthorData


def test_upsert_books_batches_everything(session, execute_spy):
    books = [
        BookData(
            ol_key="OL1",
            title="Book 1",
            isbn="123",
            description="desc",
            publication_year=2000,
            page_count=100,
            authors=[AuthorData(name="Author 1", ol_id="A1")],
        ),
        BookData(
            ol_key="OL2",
            title="Book 2",
            isbn="456",
            description="desc",
            publication_year=2001,
            page_count=200,
            authors=[AuthorData(name="Author 2", ol_id="A2")],
        ),
    ]

    result = upsert_books(books, tag_map={"OL1": ["fiction"]})

    assert len(result) == 2

    # EXPECTED batch operations:
    # 1 insert books
    # 1 insert authors
    # 1 attach authors
    # 1 upsert tags
    # 1 attach tags
    assert execute_spy.call_count == 5
