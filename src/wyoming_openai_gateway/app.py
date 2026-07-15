"""ASGI app factory for Wyoming-OpenAI-Gateway."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings
from .errors import WyomingConnectionError
from .gateway import OpenAIGateway
from .openai_models import SpeechRequest
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

    return app
