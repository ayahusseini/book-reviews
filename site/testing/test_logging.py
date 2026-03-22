"""Tests the logging setup"""

import logging
from unittest.mock import patch, MagicMock
from app.setup_logging import setup_logging
from flask import Flask


def test_setup_logging_adds_two_file_handlers(app):
    with patch("logging.FileHandler"):
        setup_logging(app=app)
    assert len(app.logger.handlers) == 2


def test_setup_logging_adds_streamhandler(app):
    with patch("logging.FileHandler") as mockFileHandler:
        setup_logging(app=app)
    stream_handlers = [
        h for h in app.logger.handlers if isinstance(h, logging.StreamHandler)
    ]
    assert len(stream_handlers) >= 1
    assert stream_handlers[-1].level == logging.INFO


def test_setup_logging_format_is_applied():
    custom_format = "%(levelname)s - %(message)s"
    with (
        patch("logging.FileHandler"),
        patch("logging.Formatter") as mock_formatter,
    ):
        setup_logging(app=None, format=custom_format)
    mock_formatter.assert_called_once_with(custom_format)  # currently fails
