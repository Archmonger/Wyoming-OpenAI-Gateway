"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from wyoming_openai_gateway.app import create_app
from wyoming_openai_gateway.openai_models import SpeechRequest


@pytest.fixture
def app():
    return create_app()


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
