import pytest
from unittest.mock import patch
from flask import Flask
import logging
from app.config import TestingConfig
from app import create_app, read_config_setting


@pytest.fixture
def app(scope="session"):
    """
    Create a minimal Flask app for testing.
    This uses an in-memory SQLite database.

    The app has a scope of session, which means that
    it is only created once per pytest run.
    """
    with patch("app.read_config_setting", return_value="testing"):
        app = create_app()
    app.logger.handlers.clear()
    yield app


@pytest.fixture(autouse=True)
def cleanup_loggers(app):
    """
    Reset the logger after each test.
    This will prevent handler bleed
    """
    yield
    logging.getLogger().handlers.clear()
    app.logger.handlers.clear()
