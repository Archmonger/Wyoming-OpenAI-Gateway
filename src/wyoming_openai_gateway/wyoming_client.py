"""Async Wyoming protocol client wrapper."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from wyoming.asr import Transcribe, Transcript
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

    async def transcribe(
        self,
        audio_bytes: bytes,
        rate: int = 16000,
        width: int = 2,
        channels: int = 1,
        language: str | None = None,
        model_name: str | None = None,
    ) -> str:
        """Send audio data for transcription via Wyoming ASR protocol.

        Returns the transcribed text.
        """
        if self._client is None:
            raise WyomingConnectionError("Not connected to Wyoming server")

        try:
            # 1. Send Transcribe event with metadata
            transcribe_event = Transcribe(
                name=model_name,
                language=language,
            )
            await self._client.write_event(transcribe_event.event())

            # 2. Send AudioStart with format info
            audio_start = AudioStart(
                rate=rate,
                width=width,
                channels=channels,
            )
            await self._client.write_event(audio_start.event())

            # 3. Send audio data as one or more AudioChunks
            # Split into reasonable chunks (e.g., 8192 bytes per chunk)
            chunk_size = 8192
            offset = 0
            while offset < len(audio_bytes):
                chunk_data = audio_bytes[offset : offset + chunk_size]
                audio_chunk = AudioChunk(
                    rate=rate,
                    width=width,
                    channels=channels,
                    audio=chunk_data,
                )
                await self._client.write_event(audio_chunk.event())
                offset += chunk_size

            # 4. Send AudioStop
            audio_stop = AudioStop()
            await self._client.write_event(audio_stop.event())

            # 5. Read the response — expect Transcript event
            while True:
                event = await self._client.read_event()
                if event is None:
                    raise WyomingProtocolError(
                        "Wyoming server closed connection without returning a transcript"
                    )

                if Transcript.is_type(event.type):
                    transcript = Transcript.from_event(event)
                    return transcript.text
        except WyomingConnectionError:
            raise
        except WyomingProtocolError:
            raise
        except Exception as e:
            raise WyomingProtocolError(f"Error during Wyoming transcribe: {e}") from e
