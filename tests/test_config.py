"""Tests for the Settings configuration."""

from __future__ import annotations

from wyoming_openai_gateway.config import Settings, validate


def test_defaults():
    """Test Settings with default values (all None)."""
    settings = Settings()
    assert settings.tts_host is None
    assert settings.tts_port is None
    assert settings.stt_host is None
    assert settings.stt_port is None
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
        "STT_HOST": "10.0.0.3",
        "STT_PORT": "10300",
        "HOST": "0.0.0.0",
        "PORT": "9000",
        "DEBUG": "true",
        "LOG_LEVEL": "WARNING",
    })
    assert settings.tts_host == "10.0.0.2"
    assert settings.tts_port == 10206
    assert settings.stt_host == "10.0.0.3"
    assert settings.stt_port == 10300
    assert settings.port == 9000
    assert settings.debug is True
    assert settings.log_level == "WARNING"


def test_validate_neither():
    """Validate returns errors when neither TTS nor STT is configured."""
    settings = Settings()
    errors = validate(settings)
    assert len(errors) == 1
    assert "Neither TTS_HOST nor STT_HOST" in errors[0]


def test_validate_partial_tts():
    """Validate returns error when TTS_HOST is set but TTS_PORT is not."""
    settings = Settings(tts_host="10.0.0.1")
    errors = validate(settings)
    assert len(errors) >= 1
    assert any("TTS_HOST" in e and "TTS_PORT" in e for e in errors)


def test_validate_partial_tts_port():
    """Validate returns error when TTS_PORT is set but TTS_HOST is not."""
    settings = Settings(tts_port=10200)
    errors = validate(settings)
    assert len(errors) >= 1
    assert any("TTS_PORT" in e and "TTS_HOST" in e for e in errors)


def test_validate_ok_tts_only():
    """Validate succeeds with only TTS configured."""
    settings = Settings(tts_host="10.0.0.1", tts_port=10200)
    assert validate(settings) == []


def test_validate_ok_stt_only():
    """Validate succeeds with only STT configured."""
    settings = Settings(stt_host="10.0.0.1", stt_port=10300)
    assert validate(settings) == []


def test_validate_ok_both():
    """Validate succeeds with both TTS and STT configured."""
    settings = Settings(tts_host="10.0.0.1", tts_port=10200, stt_host="10.0.0.2", stt_port=10300)
    assert validate(settings) == []
