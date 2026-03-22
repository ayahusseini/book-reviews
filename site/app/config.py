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
    PROXY_FIX = False
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
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{os.path.join(Config.BASE_DIR, 'instance', 'site.db')}"
    )


if __name__ == "__main__":
    get_secret_key()
