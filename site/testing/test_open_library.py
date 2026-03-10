"""Tests app/open_library.py"""

import pytest
from app.open_library import validate_response, OpenLibraryError
import requests


def test_validate_reponse_success():
    real_response = requests.Response()
    real_response.status_code = 200
    validate_response(real_response)


def test_validate_reponse_errors():
    real_response = requests.Response()
    real_response.status_code = 404
    with pytest.raises(OpenLibraryError):
        validate_response(real_response)
