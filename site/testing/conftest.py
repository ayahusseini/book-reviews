import pytest
from flask import Flask
import logging
from app.config import TestingConfig


@pytest.fixture
def app(scope="session"):
    """
    Create a minimal Flask app for testing.
    This uses an in-memory SQLite database.

    The app has a scope of session, which means that
    it is only created once per pytest run.
    """
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.logger.handlers.clear()

    return app


@pytest.fixture(autouse=True)
def cleanup_loggers(app):
    """
    Reset the logger after each test.
    This will prevent handler bleed
    """
    yield
    logging.getLogger().handlers.clear()
    app.logger.handlers.clear()
