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
    check_config_safety,
)
from app.database import models as models
from app.extensions import db, migrate, cache
from app.setup_logging import setup_logging
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()


def read_config_setting() -> str:
    """Read the config setting from the environment"""
    config = os.getenv("FLASK_ENV")
    if config is None:
        raise ValueError("Config must be set in the environment.")
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
    config_name = read_config_setting()
    config_obj = get_config_obj(config_name)
    check_config_safety(config_obj)
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_obj)

    if app.config.get("PROXY_FIX", False):
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
        )

    setup_logging(app)
    app.logger.info(f"Starting app with config: {config_name}")

    app.logger.info(f"Starting app with config: {config_obj}")
    app.logger.info(f"Starting app with config: {config_name}")

    os.makedirs(app.instance_path, exist_ok=True)

    from .blueprints.books import books_bp
    from .blueprints.main import main_bp
    from .blueprints.posts import posts_bp
    from .blueprints.poems import poems_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(books_bp, url_prefix="/books")
    app.register_blueprint(posts_bp, url_prefix="/posts")
    app.register_blueprint(poems_bp, url_prefix="/poems")

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
