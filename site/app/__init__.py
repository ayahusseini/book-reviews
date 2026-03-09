"""Instantiate the Flask application."""

import os
from flask import Flask
from app.models import db
from app.config import (
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    Config,
)


def get_config_obj(config_str: str) -> Config:
    """Return a Config subclass given a string"""
    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }

    if config_str not in configs.keys():
        raise ValueError(
            "The config string must be one of"
            + f"{','.join(list(configs.keys()))}"
        )

    return configs[config_str]


def create_app():
    """Create and configure the Flask application."""

    config = os.getenv("FLASK_ENV", "development").lower()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(get_config_obj(config))

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
