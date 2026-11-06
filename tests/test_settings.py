from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_example_dotenv_loads():
    example = Path(__file__).resolve().parents[1] / ".env.example"
    settings = Settings(_env_file=example, mock_mode=True, app_env="development")
    assert settings.evon_max_concurrent == 1
    assert isinstance(settings.evon_max_concurrent, int)


def test_concurrency_from_environment(monkeypatch):
    monkeypatch.setenv("EVON_MAX_CONCURRENT", "1")
    settings = Settings(_env_file=None, mock_mode=True, app_env="development")
    assert settings.evon_max_concurrent == 1


@pytest.mark.parametrize("value", ["0", "2", "invalid"])
def test_invalid_concurrency_from_environment(monkeypatch, value):
    monkeypatch.setenv("EVON_MAX_CONCURRENT", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mock_mode=True, app_env="development")
