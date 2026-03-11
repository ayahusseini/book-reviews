"""Instantiate the Flask application."""

from dotenv import load_dotenv
import os
from flask import Flask
from app.extensions import db
from app import models as models
from app.config import (
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    Config,
)


def read_config_setting(default: str = "development") -> str:
    """Reads the config setting from the environment
    Defaults to default"""
    load_dotenv()
    if not isinstance(default, str):
        return TypeError(
            "The default must be a string"
            + "Instead, got"
            + f"default={default} ({type(default)})"
        )
    return os.getenv("FLASK_ENV", default).lower()


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

    config = read_config_setting()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(get_config_obj(config))

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from app.blueprints.api import api_bp

    app.register_blueprint(api_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
