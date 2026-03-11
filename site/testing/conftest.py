import pytest
from flask import Flask
import logging
from app.config import TestingConfig


@pytest.fixture
def app():
    """
    Create a minimal Flask app for testing.
    This uses an in-memory SQLite database
    """
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.logger.handlers.clear()
    return app
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
