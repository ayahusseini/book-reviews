"""Tests the logging setup"""

import logging
import pytest
from unittest.mock import patch, MagicMock
from app.setup_logging import setup_logging
from app.config import TestingConfig
from flask import Flask


@pytest.fixture
def app():
    """Create a minimal Flask app for testing."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    return app
