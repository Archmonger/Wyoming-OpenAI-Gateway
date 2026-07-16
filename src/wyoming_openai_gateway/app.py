"""ASGI app factory for Wyoming-OpenAI-Gateway."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from . import __version__
from .config import Settings
from .errors import WyomingConnectionError
from .gateway import OpenAIGateway
from .openai_models import (
    SpeechRequest,
    TranscriptionRequest,
)
from .wyoming_client import WyomingStreamClient

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings._parse()

    gateway = OpenAIGateway(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info(
            "Starting Wyoming-OpenAI-Gateway v%s (Wyoming target: %s:%s)",
            __version__,
            settings.wyoming_host,
            settings.wyoming_port,
        )
        # Validate Wyoming connectivity on startup (non-fatal)
        try:
            async with WyomingStreamClient(settings.wyoming_host, settings.wyoming_port) as client:
                await client.describe()
            log.info("Successfully connected to Wyoming server")
        except WyomingConnectionError:
            log.warning(
                "Could not connect to Wyoming server at %s:%s — will retry on each request",
                settings.wyoming_host,
                settings.wyoming_port,
            )
        except Exception:
            log.warning("Unexpected error during Wyoming connectivity check", exc_info=True)
        yield
        log.info("Shutting down Wyoming-OpenAI-Gateway")

    app = FastAPI(
        title="Wyoming-OpenAI-Gateway",
        description="A gateway that exposes local Wyoming protocol services via OpenAI-compatible API endpoints.",
        version=__version__,
        lifespan=lifespan,
    )

    prefix = settings.prefix

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    async def readyz():
        try:
            async with WyomingStreamClient(settings.wyoming_host, settings.wyoming_port) as client:
                await client.describe()
            return {"status": "ready"}
        except WyomingConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))

    @app.get(f"{prefix}/voices")
    async def list_voices():
        return await gateway.list_voices()

    @app.post(f"{prefix}/audio/speech")
    async def text_to_speech(request: SpeechRequest):
        return await gateway.text_to_speech(request)

    # --- STT Routes ---

    @app.post(f"{prefix}/audio/transcriptions")
    async def create_transcription(
        file: UploadFile = File(..., description="Audio file to transcribe"),
        model: str = Form("whisper-1", description="Model identifier"),
        language: str | None = Form(None, description="Language code (e.g. 'en')"),
        prompt: str | None = Form(None, description="Optional context prompt"),
        response_format: str = Form("json", description="Response format (json/text)"),
        temperature: float = Form(0.0, description="Sampling temperature"),
    ):
        request = TranscriptionRequest(
            model=model,
            language=language,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
        )
        result = await gateway.transcribe_audio(file, request, is_translation=False)
        return result

    @app.post(f"{prefix}/audio/translations")
    async def create_translation(
        file: UploadFile = File(..., description="Audio file to translate"),
        model: str = Form("whisper-1", description="Model identifier"),
        language: str | None = Form(None, description="Language code (e.g. 'en')"),
        prompt: str | None = Form(None, description="Optional context prompt"),
        response_format: str = Form("json", description="Response format (json/text)"),
        temperature: float = Form(0.0, description="Sampling temperature"),
    ):
        request = TranscriptionRequest(
            model=model,
            language=language,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
        )
        result = await gateway.transcribe_audio(file, request, is_translation=True)
        return result

    return app
