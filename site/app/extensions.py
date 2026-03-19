"""Flask extensions for the book review website.
The purpose of this file is to instantiate extensions
without importing the app.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache

cache = Cache()

db = SQLAlchemy()
migrate = Migrate()
