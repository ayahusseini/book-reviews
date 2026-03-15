import pytest
from unittest.mock import patch
from flask import Flask
import logging
from app.config import TestingConfig
from app import create_app, read_config_setting
from app.extensions import db as _db


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


@pytest.fixture
def db(app, scope="function"):
    """
    Create a empty DB with the expected schema
    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def cleanup_loggers(app):
    """
    Reset the logger after each test.
    This will prevent handler bleed
    """
    yield
    logging.getLogger().handlers.clear()
    app.logger.handlers.clear()
