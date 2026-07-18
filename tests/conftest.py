"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from wyoming_openai_gateway.app import create_app
from wyoming_openai_gateway.config import Settings
from wyoming_openai_gateway.openai_models import SpeechRequest, TranscriptionRequest

# A port that is unlikely to have a Wyoming server for testing "no server" scenarios
_DEAD_PORT = 19999


@pytest.fixture
def settings_no_wyoming() -> Settings:
    """Settings that point to a non-existent Wyoming server."""
    return Settings(
        tts_host="127.0.0.1",
        tts_port=_DEAD_PORT,
        stt_host="127.0.0.1",
        stt_port=_DEAD_PORT,
    )


@pytest.fixture
def app(settings_no_wyoming):  # type: ignore[misc]
    return create_app(settings_no_wyoming)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_speech_request():
    return SpeechRequest(
        input="Hello, world!",
        voice="en_US-lessac-medium",
        model="wyoming",
        response_format="wav",
        speed=1.0,
        stream=False,
    )


@pytest.fixture
def sample_transcription_request():
    """Sample TranscriptionRequest with typical defaults."""
    return TranscriptionRequest(
        model="whisper-1",
        language=None,
        prompt=None,
        response_format="json",
        temperature=0.0,
        timestamp_granularities=None,
    )


@pytest.fixture
def sample_transcription_request_with_lang():
    """Sample TranscriptionRequest with language and prompt specified."""
    return TranscriptionRequest(
        model="whisper-1",
        language="en",
        prompt="Hello, this is a test.",
        response_format="text",
        temperature=0.5,
        timestamp_granularities=["segment"],
    )
