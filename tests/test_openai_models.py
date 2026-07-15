"""Tests for OpenAI-compatible Pydantic models."""

from __future__ import annotations

from wyoming_openai_gateway.openai_models import SpeechRequest, Voice, VoicesResponse


def test_speech_request_defaults():
    """Test SpeechRequest with only required fields."""
    request = SpeechRequest(input="Hello", voice="test-voice")
    assert request.input == "Hello"
    assert request.voice == "test-voice"
    assert request.model == "wyoming"
    assert request.response_format == "wav"
    assert request.speed == 1.0
    assert request.stream is False


def test_speech_request_custom():
    """Test SpeechRequest with all fields specified."""
    request = SpeechRequest(
        input="Test text",
        voice="en_US-voice",
        model="custom-model",
        response_format="wav",
        speed=1.5,
        stream=True,
    )
    assert request.input == "Test text"
    assert request.voice == "en_US-voice"
    assert request.model == "custom-model"
    assert request.speed == 1.5
    assert request.stream is True


def test_voice_model():
    """Test Voice model creation."""
    voice = Voice(
        id="en_US-test",
        name="Test Voice",
        description="A test voice",
        languages=["en_US", "en_GB"],
    )
    assert voice.id == "en_US-test"
    assert voice.name == "Test Voice"
    assert voice.description == "A test voice"
    assert voice.languages == ["en_US", "en_GB"]


def test_voice_minimal():
    """Test Voice with only required fields."""
    voice = Voice(id="test", name="Test")
    assert voice.description is None
    assert voice.languages is None


def test_voices_response():
    """Test VoicesResponse model."""
    voices = [
        Voice(id="voice1", name="Voice 1"),
        Voice(id="voice2", name="Voice 2"),
    ]
    response = VoicesResponse(voices=voices)
    assert len(response.voices) == 2
    assert response.voices[0].id == "voice1"
    assert response.voices[1].id == "voice2"
