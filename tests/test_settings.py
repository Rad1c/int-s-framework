import pytest
from pydantic import ValidationError

from integration_framework.settings import FrameworkSettings
from tests.conftest import make_settings


def test_defaults():
    settings = make_settings()
    assert settings.rabbitmq_host == "localhost"
    assert settings.rabbitmq_port == 5672
    assert settings.rabbitmq_user == "guest"
    assert settings.rabbitmq_vhost == "/"
    assert settings.rabbitmq_request_topic == "requests"
    assert settings.rabbitmq_response_topic == "responses"
    assert settings.consumer_prefetch_count == 10
    assert settings.rabbitmq_max_retry_attempts == 0
    assert settings.http_port == 8080
    assert settings.log_level == "INFO"


def test_required_fields():
    with pytest.raises(ValidationError):
        FrameworkSettings(_env_file=None)


def test_rabbitmq_user_env(monkeypatch):
    monkeypatch.setenv("RABBITMQ_USER", "ibo-style")
    settings = make_settings()
    assert settings.rabbitmq_user == "ibo-style"


def test_rabbitmq_username_alias(monkeypatch):
    # Betbox-style env var name must also work.
    monkeypatch.setenv("RABBITMQ_USERNAME", "betbox-style")
    settings = make_settings()
    assert settings.rabbitmq_user == "betbox-style"


def test_is_development():
    assert not make_settings().is_development
    assert make_settings(app_env="Development").is_development
    assert make_settings(app_env="development").is_development
    assert not make_settings(app_env="production").is_development


def test_extra_env_vars_ignored(monkeypatch):
    # Services load service-specific env vars; the base class must not reject them.
    monkeypatch.setenv("BETBOX_API_BASE_URL", "https://example.com")
    settings = make_settings()
    assert settings.service_type == "test_service"
