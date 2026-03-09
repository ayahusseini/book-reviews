# Flask

## What is Flask?

- Flask is a *framework* for making web applications
- A defining characteristic of **frameworks** is **inversion of control**. This makes it distinct from a library. 
  - Typical libraries are imported, and then the code calls the library to import functions.
  - In frameworks, we write the functions, and the framework decides when and if to call them.
- E.G. in the below snippet, `form()` is called when the `/` route is accessed with the `"GET"` method

```python

from flask import Flask 

app = Flask(__name__)

@app.route("/", methods=["GET"]) 
def form(): 
    ...

if __name__ == "__main__":
    app.run()
```

- Rather than your code calling `Flask` functions, `Flask` calls your code. Nowhere do we define a `while True` loop which handles recieving the HTTP request, parsing it, deciding when to call `form()` and returning the response. We also never write code that reads raw bytes off a socket.

### So what does Flask do?

- Flask is lightweight, which means it doesn't have batteries included (c.f. Django)
- Out of the box, we get:
  - URL routing 
  - Request/response handling 
    - We get handed clean `request` objects and return `Response` objects - serialisation and reading raw bytes off a socket are abstracted away
  - A templating engine (Jinja2)

### The Flask server

- Flask code defines a WSGI application, which is a Python callable. 
- To *serve* the application:
  - In development: Flask runs its own local server  
  - In production: We'd put a proper WSGI server in front of the flask application instead.
- Strictly speaking, there's a difference between the Flask application and the server

## Why use Flask?

An alternative would be to just have a static website. E.G. GitHub Pages just serves HTML and CSS files. There is no server-side code running when you visit the website. Theoretically, this is sufficient for a book review website where:

- the content doesn't change often
- Its' not too bad writing code by hand
  - something which could be simplified even further by using Jekyll or Hugo
- We don't need user input

Flask earns its place here because:

- I want to learn how to use it. This is by far the most important reason. 
- I'd like to have some server-side logic:
  - dynamic pages
  - future features: 
    - user accounts

## The application factory pattern

- We can instantiate a `Flask` app as a module-level global. This gets messy quickly. Instead, we can create an app inside a function (conventionally) called `create_app()`. This pattern:
  - Avoids circular imports.
  - Enables us to have multiple app instances
    - E.g. each test can have a fresh app with its own configuration and an isolated test database.
  - Defers configuration 
    - Instead of setting the configuration at a global level, we can maintain different configuration parameters for development, testing, and production.
- A typical folder structure would be:

```sh
book_reviews/
  site/ # holds all code for the site
    run.py # entry point - which calls create_app() and runs the server
    config.py # config classes
    app/ 
      __init__.py # contains create_app()
      extensions.py 
      models.py 
      blueprints/ 
      ...
```

- Conventionally, `__init__.py` holds `create_app()` logic
  - We want it to be at the top-level (whenever anything is imported from `app/`, the first  thing that is executed is `__init__.py`
- E.G. for `run.py`, the main entry point that actually starts the server, we'd just need

```python
# run.py 

from site import create_app()

if __name__ == "__main__":
  app = create_app()
  app.run()
```

### Configuring the application

In Flask, we have dictionary-like object called `app.config` which holds things like

- database path
- secret key
- mode (debug mode?)

The cleanest way of managing this is creating a single config class per environment in `config.py` 

```python
# config.py
class Config:
    """Base config — shared across all environments."""
    SECRET_KEY = "change-me-in-production"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///instance/site.db"

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  # in-memory db, wiped after each test

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///instance/site.db"
    SECRET_KEY = "read-this-from-an-env-var-not-here"
```

then, `create_app()` should load the right `Config` object:

```python
# app/__init__.py
def create_app(config: Config):
  app = Flask(__name__)
  app.config.from_object(config)
```

#### Testing vs Development configuration

- The `TESTING = True` flag means that Flask will propagate exceptions rather than producing error pages. In development, we want to see a debugger page in-browser. In unit tests, we want the raw exception to bubble up so it can be reported properly. 
- Unit tests shouldn't run against the actual database because:
  - tests that write data will pollute the real database
  - tests that delete or modify data could destroy the things we care about. 
  - test results would depend on whatever state the database actually happens to be in, rather than considering all possible edge-cases. This also makes test results non-deterministic.
- So tests need their own isolated database. The URI `sqlite:///:memory:` means 'don't use a file at all, keep the entire database in-memory'. It is created instantly and automatically destroyed when the connection closes. 
  - The test seup will need to run `db.create_all()` to build the schema fresh at the start.

#### The Secret Key

- The secret key is just a long random string. It's used by flask as the input to a **cryptographic signing algorithm** - each session cookie has a signature produced 
- E.G. if we have the same SECRET KEY across all dev sessions, then the environment is consistent and reproducible. 
- For production, we should have a secret key in the `.env` file - this is loaded into our process at startup

## Flask extensions

- Flask has several extensions that can add functionality to the app. E.G.:
  - Flask-SQLAlchemy integrates SQLAlchemy with Flask's request lifecycle 
  - Flask-Migrate adds database migration commands to the Flask CLI
- A flask extension is distinct froma  regular python library because it needs to know about your app (e.g. its config, request context, etc.)
- Each extension needs to be *instantiated* and *migrated* 
- Naiively:

```python
from flask_sqlalchemy import SQLAlchemy 
from flask import Flask 

app = Flask(__name__)
db = SQLAlchemy(app)
```

- The above snippet instantiates a `SQLAlchemy` database and *binds it to the app*. 
- Any other file that imports `db` also triggers app creation
  - Note that this can lead to problems with circular imports everywhere. Instead, we should follow the **application factory pattern** and seperate instantiation from binding

```python
# app/extensions.py 
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
```

- In the above snippet, `db` is only instantiated. It is dormant until an `init_app()` method is called on it.

```python
# app/__init__.py 
from app.extensions import db

def create_app():
    app = Flask(__name__)
    db.init_app(app) # bind db to this specific application 
    return app 
```

### Flask extensions - Database integration

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

- Our flask config needs to set the `SQLALCHEMY_DATABASE_URI` 
- Then we import `db` and it is set up according to the app configuration. Everthing is accessible from the `db` object

### Where and how do we access the app in other files?

- We can import the app from the module in which its' defined, but this still leads to circular imports. 
- Instead, we can use Flask's application context:
  - If a request comes in, an application context is pushed onto the stack
  - Whist the application context is active, we can access the current app via a **proxy object** called `current_app`. This isn't the app itself, but a proxy that points to whichever app is currently handling the request.

```python
from flask import current_app
```

## Blueprints

- The `@app.route` decorator tells us what function to execute when a request is made to a certain route
- Having loads of these scattered across different files will get messy fast. 
- Instead, routes are organised by domain using *blueprints* 
- In the case of our app, we can have one blueprint per entity

```
/authors          → authors blueprint
/books            → books blueprint
/books/<id>/posts → posts blueprint  
/tags             → tags blueprint
/api              → used to actually create reviews
```

We can define blueprints in a `blueprints/` folder:

```python
# app/blueprints/books.py
from flask import Blueprint

books_bp = Blueprint("books", __name__, url_prefix="/books")

@books_bp.route("/")
def list_books():
    # this is for the route books/

@books_bp.route("/<int:book_id>")
def get_book(book_id):
    # this is for the route books/<book_id>
```

And we must register the blueprint when creating the app:

```python
# app/__init__.py
from app.blueprints.books import books_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(books_bp)
    return app
```

## Flask CLI commands

- The Flaask CLI comes built into flask. When we run `flask run`, the Flask CLI starts our development server. 
- We can register our own custom flask commands. 
- In this case, we'll want CLI commands for ingesting draft posts and adding books 
- We define these using `@app.cli.command()` 
  - this registers a function to be caclled when we type a command in the terminal. It is triggered locally at the command line. 
  - contrast this to `@app.route` which registers a function to be called when a HTTP request arrives at a particular URL

