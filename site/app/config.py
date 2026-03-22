"""Different configuration classes for the application."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base config — shared across all environments."""

    SECRET_KEY = "change-me-in-production"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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
    SECRET_KEY = "test"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    PROXY_FIX = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{os.path.join(Config.BASE_DIR, 'instance', 'site.db')}"
    )
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is not set")
