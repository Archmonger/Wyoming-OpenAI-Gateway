"""Pydantic models for OpenAI-compatible request/response schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    """OpenAI-compatible text-to-speech request body."""

    input: str = Field(..., description="The text to synthesize")
    model: str = Field("wyoming", description="Model identifier")
    voice: str = Field(..., description="Voice ID to use")
    response_format: str = Field("wav", alias="response_format", description="Audio format (only wav supported)")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech rate multiplier")
    stream: bool = Field(False, description="Enable streaming response")

    class Config:
        populate_by_name = True


class Voice(BaseModel):
    """OpenAI-compatible voice representation."""

    id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Human-readable voice name")
    description: Optional[str] = Field(None, description="Voice description")
    languages: Optional[list[str]] = Field(None, description="Supported language codes")


class VoicesResponse(BaseModel):
    """OpenAI-compatible voices list response."""

    voices: list[Voice] = Field(..., description="List of available voices")
