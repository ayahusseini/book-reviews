CREATE TABLE IF NOT EXISTS authors (
    author_id INTEGER PRIMARY KEY,
    author_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    book_id INTEGER PRIMARY KEY,
    book_title TEXT NOT NULL,
    book_description TEXT,
    book_publication_year INTEGER,
    book_rating_personal INTEGER,
    author_id INTEGER REFERENCES authors(author_id)
);

CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY,
    book_id INTEGER REFERENCES books(book_id),
    note_markdown TEXT,
    note_date TIMESTAMP,
    note_parent_id INTEGER REFERENCES notes(note_id),
    note_type TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY,
    tag_name TEXT NOT NULL,
    tag_description TEXT
);

CREATE TABLE IF NOT EXISTS book_to_tag_map (
    book_to_tag_map_id INTEGER PRIMARY KEY,
    book_id INTEGER REFERENCES books(book_id),
    tag_id INTEGER REFERENCES tags(tag_id)
);