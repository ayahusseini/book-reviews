# Design

The goal is to create a Flask application to display book reviews and personal writing, deploying as a website. The site is conceived as a personal reading journal - encompassing book reviews and general standalone posts. The application is built around the data model described below:

## The data model


### The schema

![data model](/docs/img/data_model.png)

Design decisions worth noting:

- **Books and tags are many-to-many.** A book can have many tags; a tag can apply to many books. This is resolved via the `book_to_tag_map` junction table. In SQLAlchemy, this table is modelled as a simple association table (rather than a full ORM class) since no additional metadata is stored on the relationship — see the SQLAlchemy section for details.
- **Books and authors are many-to-many.** This is also handled by a junction table.
- **Book metadata can be populated via Open Library.** When adding a book by ISBN, the CLI can fetch the book's title, description, publication year, cover URL, page count automatically. Only tags and the ratings can be set manually.
- **Posts don't need a `book_id`**. If the `book_id` is set to `NULL`, then posts are treated as standalone. 


## The API 

The Flask blueprint `site/app/blueprints.api.py` handles the api endpoints:
- `POST /api/books` adds a book and returns the `book_id`. An OpenLibrary 'works key' is required, and this errors if there is a duplicate or the key doesn't exist. 
- `PATCH /api/books/<book_id>` updates book fields and errors if the book_id doesn't exist
- `POST /api/posts` adds a post/review. Mapped to `book_id` or `isbn` (or `None` for either of these to have a stand-alone post)

These endpoints serve JSON rather than a HTML page. 

## Tech stack

An overview of everything used and a justification for why, how this will scale, and future improvements/alternatives

1. [Flask](/docs/flask.md)
2. [SQLAlchemy](/docs/sqlalchemy.md)
