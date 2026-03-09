"""Instantiate the Flask application."""

from flask import Flask
from app.models import db


def create_app(config=None):
    """Create and configure the Flask application."""

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config)
    db.init_app(app)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
