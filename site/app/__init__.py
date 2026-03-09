"""Instantiate the Flask application."""

import os
from flask import Flask
from app.models import db
from app.config import DevelopmentConfig, Config


def create_app(config: Config = DevelopmentConfig):
    """Create and configure the Flask application."""

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
