"""Tests for OpenAI-compatible Pydantic models."""

from __future__ import annotations

from wyoming_openai_gateway.openai_models import (
    SpeechRequest,
    TranscriptionRequest,
    TranscriptionResponse,
    TranslationResponse,
    Voice,
    VoicesResponse,
)

# ── TTS models ──────────────────────────────────────────────────────────────────


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


# ── STT models ──────────────────────────────────────────────────────────────────


def test_transcription_request_defaults():
    """Test TranscriptionRequest with only required fields."""
    request = TranscriptionRequest(model="whisper-1")
    assert request.model == "whisper-1"
    assert request.language is None
    assert request.prompt is None
    assert request.response_format == "json"
    assert request.temperature == 0.0
    assert request.timestamp_granularities is None


def test_transcription_request_full():
    """Test TranscriptionRequest with all fields specified."""
    request = TranscriptionRequest(
        model="custom-model",
        language="en",
        prompt="Context prompt",
        response_format="text",
        temperature=0.5,
        timestamp_granularities=["segment", "word"],
    )
    assert request.model == "custom-model"
    assert request.language == "en"
    assert request.prompt == "Context prompt"
    assert request.response_format == "text"
    assert request.temperature == 0.5
    assert request.timestamp_granularities == ["segment", "word"]


def test_transcription_request_alias():
    """Test that the response_format and timestamp_granularities aliases work."""
    request = TranscriptionRequest(
        model="whisper-1",
        response_format="text",
        timestamp_granularities=["word"],
    )
    assert request.response_format == "text"
    assert request.timestamp_granularities == ["word"]


def test_transcription_response():
    """Test TranscriptionResponse model."""
    response = TranscriptionResponse(text="Hello world")
    assert response.text == "Hello world"


def test_translation_response():
    """Test TranslationResponse model."""
    response = TranslationResponse(text="Bonjour le monde")
    assert response.text == "Bonjour le monde"
