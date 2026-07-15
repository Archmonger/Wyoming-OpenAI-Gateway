"""Async Wyoming protocol client wrapper."""

from __future__ import annotations

import logging
from typing import AsyncGenerator, AsyncIterator

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.tts import Synthesize, SynthesizeVoice

from .errors import WyomingConnectionError, WyomingProtocolError

log = logging.getLogger(__name__)


class WyomingStreamClient:
    """Async context manager wrapping Wyoming's AsyncTcpClient."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._client: AsyncTcpClient | None = None

    async def __aenter__(self) -> WyomingStreamClient:
        try:
            self._client = AsyncTcpClient(self._host, self._port)
            await self._client.__aenter__()
            log.debug("Connected to Wyoming server at %s:%s", self._host, self._port)
            return self
        except Exception as e:
            raise WyomingConnectionError(
                f"Failed to connect to Wyoming server at {self._host}:{self._port}: {e}"
            ) from e

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None:
            try:
                await self._client.__aexit__(*args)
            except Exception:
                log.warning("Error disconnecting from Wyoming server", exc_info=True)
            self._client = None

    async def describe(self) -> Info:
        """Query the Wyoming server for capabilities and installed voices."""
        if self._client is None:
            raise WyomingConnectionError("Not connected to Wyoming server")

        try:
            await self._client.write_event(Describe().event())
            event = await self._client.read_event()
        except Exception as e:
            raise WyomingConnectionError(f"Error communicating with Wyoming server: {e}") from e

        if event is None:
            raise WyomingProtocolError("Wyoming server returned no response to Describe")

        if not Info.is_type(event.type):
            raise WyomingProtocolError(
                f"Expected Info event, got {event.type}"
            )

        return Info.from_event(event)

    async def synthesize_stream(
        self, text: str, voice: str, speed: float = 1.0
    ) -> AsyncGenerator[Event, None]:
        """Send a Synthesize request and yield Wyoming events as they arrive."""
        if self._client is None:
            raise WyomingConnectionError("Not connected to Wyoming server")

        voice_opts = SynthesizeVoice(name=voice.strip())
        synthesize_event = Synthesize(text=text, voice=voice_opts)
        if speed is not None:
            synthesize_event.speech_rate = speed

        try:
            await self._client.write_event(synthesize_event.event())
            while True:
                event = await self._client.read_event()
                if event is None:
                    break
                yield event
                if AudioStop.is_type(event.type):
                    break
        except Exception as e:
            raise WyomingProtocolError(f"Error during Wyoming synthesize stream: {e}") from e

    async def synthesize_complete(
        self, text: str, voice: str, speed: float = 1.0
    ) -> tuple[dict, bytes]:
        """Send a Synthesize request and collect all audio data.

        Returns (audio_params_dict, audio_data_bytes).
        """
        audio_chunks: list[bytes] = []
        audio_params: dict | None = None

        async for event in self.synthesize_stream(text, voice, speed):
            if AudioStart.is_type(event.type):
                audio_start = AudioStart.from_event(event)
                audio_params = {
                    "rate": audio_start.rate,
                    "width": audio_start.width,
                    "channels": audio_start.channels,
                }
            elif AudioChunk.is_type(event.type):
                audio_chunks.append(AudioChunk.from_event(event).audio)

        if audio_params is None:
            raise WyomingProtocolError("No AudioStart event received during synthesis")

        if not audio_chunks:
            raise WyomingProtocolError("No audio data received during synthesis")

        return audio_params, b"".join(audio_chunks)
