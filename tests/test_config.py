"""Tests for the Settings configuration."""

from __future__ import annotations

from wyoming_openai_gateway.config import Settings


def test_defaults():
    """Test Settings with default values."""
    settings = Settings()
    assert settings.tts_host == "127.0.0.1"
    assert settings.tts_port == 10200
    assert settings.host == "0.0.0.0"
    assert settings.port == 8555
    assert settings.debug is False
    assert settings.log_level == "INFO"
    assert settings.prefix == "/v1"


def test_custom_values():
    """Test Settings with custom values via constructor."""
    settings = Settings(
        tts_host="10.0.0.1",
        tts_port=10200,
        host="192.168.1.1",
        port=8080,
        debug=True,
        log_level="DEBUG",
        prefix="/api/v1",
    )
    assert settings.tts_host == "10.0.0.1"
    assert settings.tts_port == 10200
    assert settings.host == "192.168.1.1"
    assert settings.port == 8080
    assert settings.debug is True
    assert settings.log_level == "DEBUG"
    assert settings.prefix == "/api/v1"


def test_from_env():
    """Test Settings.from_env() with a mapping."""
    settings = Settings.from_env({
        "TTS_HOST": "10.0.0.2",
        "TTS_PORT": "10206",
        "HOST": "0.0.0.0",
        "PORT": "9000",
        "DEBUG": "true",
        "LOG_LEVEL": "WARNING",
    })
    assert settings.tts_host == "10.0.0.2"
    assert settings.tts_port == 10206
    assert settings.port == 9000
    assert settings.debug is True
    assert settings.log_level == "WARNING"
