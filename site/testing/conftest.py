"""Pytest configuration and shared fixtures."""

import logging
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Create a Flask app for the test session using an in-memory database."""
    with patch("app.read_config_setting", return_value="testing"):
        app = create_app()
    app.logger.handlers.clear()
    yield app


@pytest.fixture
def db(app):
    """Provide a clean database schema for each test function."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def cleanup_loggers(app):
    """Reset logger handlers after each test to prevent handler bleed."""
    yield
    logging.getLogger().handlers.clear()
    app.logger.handlers.clear()
