"""File to handle creation of a logger"""

from flask import Flask
import logging


def setup_logging(
    app: Flask = None,
    log_file: str = "app.log",
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> None:
    """Attach file and console handlers to Flask's logger."""

    formatter = logging.Formatter(format)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    if app:
        # Attach directly to Flask's built-in logger
        app.logger.setLevel(logging.DEBUG)
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)

    else:
        # Fallback to root logger
        logging.basicConfig(
            level=logging.DEBUG, handlers=[file_handler, console_handler]
        )
