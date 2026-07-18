"""Tests for the FastAPI application routes."""

from __future__ import annotations

import pytest

# Valid WAV: 16-bit mono 16000 Hz, 160 samples (10ms) of silence
# Total file = 44 header + 320 data = 364 bytes
# RIFF chunk size = 364 - 8 = 356 (0x164)
# Data chunk size = 320 (0x140)
_WAV_SIZE = 356  # total file size - 8
_WAV_DATA_SIZE = 160 * 2  # 320 bytes

_WAV_SILENCE = (
    b"RIFF"
    + _WAV_SIZE.to_bytes(4, "little")
    + b"WAVE"
    + b"fmt "
    + b"\x10\x00\x00\x00"  # fmt chunk size (16)
    + b"\x01\x00"  # PCM
    + b"\x01\x00"  # mono
    + b"\x80\x3e\x00\x00"  # 16000 Hz
    + (16000 * 1 * 2).to_bytes(4, "little")  # byte rate
    + b"\x02\x00"  # block align (2)
    + b"\x10\x00"  # 16-bit
    + b"data"
    + _WAV_DATA_SIZE.to_bytes(4, "little")
    + b"\x00\x00" * 160  # 160 samples (10 ms at 16 kHz)
)


# ── Health / Readiness ──────────────────────────────────────────────────────────


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


# ── Voices ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_voices_no_wyoming(client):
    """Test the /v1/voices endpoint returns 503 when no Wyoming server."""
    response = await client.get("/v1/voices")
    assert response.status_code == 503


# ── TTS ─────────────────────────────────────────────────────────────────────────


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


# ── STT (Transcriptions) ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stt_transcriptions_no_wyoming(client):
    """Test POST /v1/audio/transcriptions returns 503 when no Wyoming server."""
    response = await client.post(
        "/v1/audio/transcriptions",
        files={"file": ("test.wav", _WAV_SILENCE, "audio/wav")},
        data={"model": "whisper-1"},
    )
    # Should fail with 503 since no Wyoming ASR server is available,
    # or 422 if validation fails first on the file.
    assert response.status_code in (422, 503)


@pytest.mark.asyncio
async def test_stt_transcriptions_missing_file(client):
    """Test POST /v1/audio/transcriptions without a file returns 422."""
    response = await client.post(
        "/v1/audio/transcriptions",
        data={"model": "whisper-1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_stt_transcriptions_with_language(client):
    """Test POST /v1/audio/transcriptions with language and prompt fields."""
    response = await client.post(
        "/v1/audio/transcriptions",
        files={"file": ("speech.wav", _WAV_SILENCE, "audio/wav")},
        data={
            "model": "whisper-1",
            "language": "en",
            "prompt": "This is a test.",
            "response_format": "json",
            "temperature": "0.2",
        },
    )
    # No Wyoming ASR server, so expect 503 (or 422 on file parse)
    assert response.status_code in (422, 503)


# ── STT (Translations) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stt_translations_no_wyoming(client):
    """Test POST /v1/audio/translations returns 503 when no Wyoming server."""
    response = await client.post(
        "/v1/audio/translations",
        files={"file": ("test.wav", _WAV_SILENCE, "audio/wav")},
        data={"model": "whisper-1"},
    )
    assert response.status_code in (422, 503)


@pytest.mark.asyncio
async def test_stt_translations_missing_file(client):
    """Test POST /v1/audio/translations without a file returns 422."""
    response = await client.post(
        "/v1/audio/translations",
        data={"model": "whisper-1"},
    )
    assert response.status_code == 422
