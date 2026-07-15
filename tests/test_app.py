"""Tests for the FastAPI application routes."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    """Test the /healthz endpoint returns OK."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_readyz_no_wyoming(client):
    """Test the /readyz endpoint returns 503 when no Wyoming server."""
    response = await client.get("/readyz")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_list_voices_no_wyoming(client):
    """Test the /v1/voices endpoint returns 503 when no Wyoming server."""
    response = await client.get("/v1/voices")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_tts_missing_body(client):
    """Test POST /v1/audio/speech with missing body returns 422."""
    response = await client.post("/v1/audio/speech", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tts_invalid_voice(client):
    """Test POST /v1/audio/speech with invalid data."""
    response = await client.post(
        "/v1/audio/speech",
        json={
            "input": "Hello",
            "voice": "test-voice",
            "model": "wyoming",
        },
    )
    # Should fail with 503 since no Wyoming server is available
    assert response.status_code in (422, 503)
