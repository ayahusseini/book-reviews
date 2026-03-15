"""Tests the instantiation of a Flask app"""

from unittest.mock import patch
from _pytest import config
import pytest
import os
from app import get_config_obj, read_config_setting
from app.config import (
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    Config,
)


@pytest.mark.parametrize(
    "config_str",
    [
        ("development"),
        ("DEVELOPMENT"),
        ("production"),
        ("testing"),
        ("arbitrary_value"),
        (""),
    ],
)
def test_read_config_setting(config_str):
    with patch.dict(os.environ, {"FLASK_ENV": config_str}, clear=True):
        assert read_config_setting() == config_str


@patch("app.load_dotenv")
def test_read_config_setting_default_works(mock_load_dotenv):
    mock_load_dotenv.return_value = None
    with patch.dict(os.environ, clear=True):
        assert read_config_setting(default="abc") == "abc"


def test_read_config_setting_with_wrong_type_raises_typerror():
    with patch.dict(os.environ, {"FLASK_ENV": "development"}, clear=True):
        with pytest.raises(TypeError):
            read_config_setting(default=3)


@pytest.mark.parametrize(
    "config_string, config_obj",
    [
        ("development", DevelopmentConfig),
        ("DEVELOPMENT", DevelopmentConfig),
        ("production", ProductionConfig),
        ("testing", TestingConfig),
    ],
)
def test_mapping_from_get_config_obj(config_string, config_obj):
    """
    Tests that the right config setting gets mapped to the
    correct config object
    """
    assert get_config_obj(config_string) == config_obj
    assert issubclass(get_config_obj(config_string), Config)
