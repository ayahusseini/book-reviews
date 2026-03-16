"""Instantiate the Flask application."""

from dotenv import load_dotenv
import os
from flask import Flask
from app.extensions import db, migrate
from app.database import models as models
from app.config import (
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    Config,
)
from app.setup_logging import setup_logging


def read_config_setting(default: str = "development") -> str:
    """Reads the config setting from the environment
    Defaults to default"""
    load_dotenv()

    if not isinstance(default, str):
        raise TypeError(
            "The default must be a string"
            + "Instead, got"
            + f"default={default} ({type(default)})"
        )

    config = os.getenv("FLASK_ENV", default)
    return config


def get_config_obj(config_str: str) -> Config:
    """Return a Config subclass given a string"""
    config_str = config_str.strip().lower()

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

    config = read_config_setting(default="development")

    app = Flask(__name__, instance_relative_config=True)
    setup_logging()

    app.config.from_object(get_config_obj(config))
    app.logger.info(f"Starting app with config: {config}")  # use app.logger

    os.makedirs(app.instance_path, exist_ok=True)

    from .blueprints.books import books_bp
    from .blueprints.main import main_bp
    from .blueprints.posts import posts_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(books_bp, url_prefix="/books")
    app.register_blueprint(posts_bp, url_prefix="/posts")

    db.init_app(app)
    migrate.init_app(app, db)

    from . import cli as cli_module

    cli_module.init_app(app)

    if app.config.get("TESTING", False):
        # Only auto-create tables for tests
        # Otherwise, rely on migrations
        with app.app_context():
            db.create_all()

    app.logger.info(
        "Database initialised with model(s):"
        + "\n"
        + ",\n".join(models.get_registered_models())
    )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
