"""Pytest configuration and shared fixtures."""

import logging
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.extensions import db as flask_db

from sqlalchemy.orm import scoped_session, sessionmaker


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
        flask_db.create_all()
        yield flask_db
        flask_db.session.remove()
        flask_db.drop_all()


@pytest.fixture(autouse=True)
def cleanup_loggers(app):
    """Reset logger handlers after each test to prevent handler bleed."""
    yield
    logging.getLogger().handlers.clear()
    app.logger.handlers.clear()


@pytest.fixture
def session(db):
    connection = db.engine.connect()
    transaction = connection.begin()

    factory = sessionmaker(bind=connection)
    scoped = scoped_session(factory)

    db.session = scoped

    yield scoped

    scoped.remove()
    transaction.rollback()
    connection.close()


@pytest.fixture
def execute_spy(session, monkeypatch):
    spy = MagicMock(wraps=session.execute)
    monkeypatch.setattr(session, "execute", spy)
    return spy
