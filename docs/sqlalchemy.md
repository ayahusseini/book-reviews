# SQLAlchemy 

## SQLite databse

This repo uses SQLite as a database. SQLite is distinct to PostgreSQL in that it is embedded (literally a file in the repo). The Flask app can just open it and run queries. This does come with limited concurrency (only one 'write' operation can happen at a time) - not much of a bottleneck in this use case. I'm the only writer so a single-writer limitation isn't too much of a problem. Its' also row-based rather than columnar (c.f. DuckDB), so optimised for transactions rather than analytics. 

- Talking to SQLite means opening a **connection** - some channel between the python process and the database file. Through this connection, we can run queries and get results back. 
- In one-off scripts, we might use `sqlite3` for creating connections

```python
import sqlite3

with sqlite3.connect("site.db") as conn:
  cursor = conn.cursor()
  cursor.execute("SELECT * from book WHERE book_id = 1")
  row = cursor.fetchone()

```

- In web applications:
  - Its not clear when to open the connection (at startup, per request)
  - Its not clear when to *close* the connection 
  - If something goes wrong mid-request, we'd need to roll-back any partial writes
  - If more than one connection request happens simultaneously, they need seperate connections so they don't interfere 
  - ...

## Using the SQLAlchemy library to solve these complexities 

These are the complexities that `SQLAlchemy` solves:

- SQLAlchemy sits between the python code and the raw database connection.
  - It has the responsibility of managing a 'pool' of connections and lending them out as needed. When a request is made, it borrows a connection from the pool. 
  - SQLAlchemy also introduces the concept of a `db.session` - this tracks everything read and written during a single operation. Only when we run `db.session.commit()` are all of these updates made. If anything goes wrong, `db.session.rollback()` undoes everything since the last commit. 
  - On top of sessions, we can define Python classes that map to tables in the data model (rather than writing hard-to-maintain SQL strings). 
  - Dialect abstraction - we write the same Python code independent of SQL dialect.

SQLAlchemy is framework agnostic. In order to work, it needs to know about Flask's request lifecycle. This is why we use the `Flask-SQLAlchemy` extension. 

- At the start of each HTTP request, a SQLAlchemy session is automatically created
- It automatically commits, rolls back, and exits at the end 
  - We never have to think about the session lifecycle since it *matches the request lifecycle*

#### Using Flask-SQLAlchemy

- Our flask config needs to set the `SQLALCHEMY_DATABASE_URI` - this is set by the `Config` objects
- Then we import `db` and it is set up according to the app configuration. Everthing is accessible from the `db` object

## Understanding Sessions
SQLALchemy uses sessions to manage database connections
Whenever an object from the database is loaded, it is attatched to a session. Through this session, the object can go back and fetch related items on demand. The 