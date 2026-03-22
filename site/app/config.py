"""Different configuration classes for the application."""

import os
from dotenv import load_dotenv

load_dotenv()


def get_secret_key() -> str:
    """Return SECRET_KEY from environment, raising clearly if absent."""
    key = os.getenv("SECRET_KEY")
    if not key:
        raise ValueError(
            "SECRET_KEY environment variable is not set. "
            "Run site/scripts/generate_secret_key.sh to create one."
        )
    if len(key) < 32:
        raise ValueError(
            f"SECRET_KEY is too short ({len(key)} chars). "
            "Minimum 32 characters required."
        )
    return key


class Config:
    """Base config — shared across all environments."""

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PROXY_FIX = False
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    SECRET_KEY = get_secret_key()


class DevelopmentConfig(Config):
    """Development config."""

    DEBUG = True
    TESTING = False
    SECRET_KEY = "dev"
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{os.path.join(Config.BASE_DIR, 'instance', 'site.db')}"
    )


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    PROXY_FIX = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False
    PROXY_FIX = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{os.path.join(Config.BASE_DIR, 'instance', 'site.db')}"
    )


def check_config_safety(config: Config) -> None:
    """Raise if a development or testing config is used behind a proxy.

    PROXY_FIX=True is only set in ProductionConfig and indicates the app
    is running behind nginx on the VPS. DEBUG or TESTING being True in
    that context is a misconfiguration that must be refused immediately.
    """
    if not config.PROXY_FIX:
        return

    if config.DEBUG:
        raise RuntimeError(
            "DEBUG=True is not allowed when PROXY_FIX is set."
            "The app appears to be running on the VPS"
            + "with a development config."
            "Set FLASK_ENV=production in your environment."
        )

    if config.TESTING:
        raise RuntimeError(
            "TESTING=True is not allowed when PROXY_FIX is set."
            "The app appears to be running on the VPS with a testing config."
            "Set FLASK_ENV=production in your environment."
        )


if __name__ == "__main__":
    get_secret_key()
