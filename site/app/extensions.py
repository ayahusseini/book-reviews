"""Flask extensions for the book review website.
The purpose of this file is to instantiate extensions
without importing the app.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
