"""Pydantic models for OpenAI-compatible request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SpeechRequest(BaseModel):
    """OpenAI-compatible text-to-speech request body."""

    input: str = Field(..., description="The text to synthesize")
    model: str = Field("wyoming", description="Model identifier")
    voice: str = Field(..., description="Voice ID to use")
    response_format: str = Field("wav", alias="response_format", description="Audio format (only wav supported)")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech rate multiplier")
    stream: bool = Field(False, description="Enable streaming response")

    model_config = ConfigDict(populate_by_name=True)


class Voice(BaseModel):
    """OpenAI-compatible voice representation."""

    id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Human-readable voice name")
    description: str | None = Field(None, description="Voice description")
    languages: list[str] | None = Field(None, description="Supported language codes")


class VoicesResponse(BaseModel):
    """OpenAI-compatible voices list response."""

    voices: list[Voice] = Field(..., description="List of available voices")


class TranscriptionRequest(BaseModel):
    """OpenAI-compatible transcription/translation request body (non-file fields)."""

    model: str = Field("whisper-1", description="Model identifier")
    language: str | None = Field(None, description="Language code (e.g. 'en')")
    prompt: str | None = Field(None, description="Optional context prompt")
    response_format: str = Field("json", alias="response_format", description="Response format (json/text)")
    temperature: float = Field(0.0, ge=0.0, le=1.0, description="Sampling temperature")
    timestamp_granularities: list[str] | None = Field(
        None, alias="timestamp_granularities",
        description="Timestamp granularities (segment, word)",
    )

    model_config = ConfigDict(populate_by_name=True)


class TranscriptionResponse(BaseModel):
    """OpenAI-compatible transcription response."""

    text: str = Field(..., description="Transcribed text")


class TranslationResponse(BaseModel):
    """OpenAI-compatible translation response."""

    text: str = Field(..., description="Translated text")
