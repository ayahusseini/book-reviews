"""Instantiate the Flask application."""

import os
import random

from dotenv import load_dotenv
from flask import Flask

from app.config import (
    Config,
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
)
from app.database import models as models
from app.extensions import db, migrate, cache
from app.setup_logging import setup_logging


def read_config_setting(default: str = "development") -> str:
    """Read the config setting from the environment, defaulting to default."""
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
    """Return a Config subclass given a string."""
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
    app.logger.info(f"Starting app with config: {config}")

    os.makedirs(app.instance_path, exist_ok=True)

    from .blueprints.books import books_bp
    from .blueprints.main import main_bp
    from .blueprints.posts import posts_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(books_bp, url_prefix="/books")
    app.register_blueprint(posts_bp, url_prefix="/posts")

    db.init_app(app)
    cache.init_app(
        app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 0}
    )
    migrate.init_app(app, db)

    from . import cli as cli_module

    cli_module.init_app(app)

    @app.context_processor
    def inject_random_quote():
        """
        Injects a random quote into the app's context
        (the return value is merged into the template context for
        every render_template call)
        If the cache already has a list of all_quotes, a random one
        is returned. Otherwise, the list is generated, cached, and
        then returned.
        """
        from app.database.models import Post

        quotes = Post.query.filter_by(post_type="quotes").all()

        return {"random_quote": random.choice(quotes) if quotes else None}

    if app.config.get("TESTING", False):
        with app.app_context():
            db.create_all()

    return app
