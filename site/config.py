"""Different configuration classes for the application."""


class Config:
    """Base config — shared across all environments."""

    SECRET_KEY = "change-me-in-production"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Development config."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///instance/site.db"


class TestingConfig(Config):
    pass
