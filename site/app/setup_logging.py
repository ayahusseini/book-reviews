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
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    if app:
        # Use DEBUG level in debug mode, INFO otherwise
        log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
        file_handler.setLevel(log_level)
        console_handler.setLevel(log_level)

        app.logger.setLevel(log_level)
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
    else:
        logging.basicConfig(
            level=logging.DEBUG, handlers=[file_handler, console_handler]
        )
