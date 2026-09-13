import pytest
from backend.security.uploads import validate_filename


def test_valid_filename():
    assert validate_filename("main.py") == "main.py"


def test_path_filename_rejected():
    with pytest.raises(ValueError):
        validate_filename("../main.py")


def test_unsupported_extension_rejected():
    with pytest.raises(ValueError):
        validate_filename("secret.exe")
