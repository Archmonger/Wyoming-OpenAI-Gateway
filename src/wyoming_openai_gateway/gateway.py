"""Core translation layer — converts OpenAI API requests to Wyoming protocol."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event

from .audio_utils import assemble_wav, create_wav_header
from .config import Settings
from .errors import WyomingConnectionError, WyomingProtocolError
from .openai_models import SpeechRequest, Voice, VoicesResponse
from .wyoming_client import WyomingStreamClient

log = logging.getLogger(__name__)


class OpenAIGateway:
    """Translates OpenAI-compatible API requests into Wyoming protocol calls."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_voices(self) -> VoicesResponse:
        """List all available TTS voices from the Wyoming server."""
        try:
            async with WyomingStreamClient(
                self._settings.wyoming_host, self._settings.wyoming_port
            ) as client:
                info = await client.describe()
        except WyomingConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))

        voices: list[Voice] = []
        for tts_program in info.tts:
            if tts_program.installed and tts_program.voices:
                for voice in tts_program.voices:
                    voices.append(
                        Voice(
                            id=voice.name,
                            name=voice.description or voice.name,
                            description=voice.attribution,
                            languages=voice.languages,
                        )
                    )

        if not voices:
            return VoicesResponse(voices=[])
        return VoicesResponse(voices=voices)

    async def text_to_speech(self, request: SpeechRequest) -> Response:
        """Convert text to speech via Wyoming protocol.

        Returns either a complete WAV file or a streaming WAV response.
        """
        if request.stream:
            return await self._stream_speech(request)
        return await self._complete_speech(request)

    async def _complete_speech(self, request: SpeechRequest) -> Response:
        """Generate complete (non-streaming) speech response."""
        try:
            async with WyomingStreamClient(
                self._settings.wyoming_host, self._settings.wyoming_port
            ) as client:
                audio_params, audio_data = await client.synthesize_complete(
                    text=request.input,
                    voice=request.voice,
                    speed=request.speed,
                )
        except WyomingConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except WyomingProtocolError as e:
            raise HTTPException(status_code=500, detail=str(e))

        wav_bytes = assemble_wav(
            [audio_data],
            rate=audio_params["rate"],
            width=audio_params["width"],
            channels=audio_params["channels"],
        )

        log.info(
            "Generated %.1f KB of WAV audio for voice '%s'",
            len(wav_bytes) / 1024,
            request.voice,
        )
        return Response(content=wav_bytes, media_type="audio/wav")

    async def _stream_speech(self, request: SpeechRequest) -> StreamingResponse:
        """Generate streaming speech response."""
        return StreamingResponse(
            self._generate_audio_stream(request),
            media_type="audio/wav",
            headers={"Connection": "close"},
        )

    async def _generate_audio_stream(
        self, request: SpeechRequest
    ) -> AsyncGenerator[bytes, None]:
        """Async generator that yields WAV header then audio chunks."""
        try:
            async with WyomingStreamClient(
                self._settings.wyoming_host, self._settings.wyoming_port
            ) as client:
                wav_header_sent = False
                async for event in client.synthesize_stream(
                    text=request.input,
                    voice=request.voice,
                    speed=request.speed,
                ):
                    if not wav_header_sent and AudioStart.is_type(event.type):
                        audio_start = AudioStart.from_event(event)
                        bits_per_sample = audio_start.width * 8
                        header = create_wav_header(
                            sample_rate=audio_start.rate,
                            bits_per_sample=bits_per_sample,
                            channels=audio_start.channels,
                        )
                        yield header
                        wav_header_sent = True
                        log.debug("Streaming: WAV header sent")
                    elif wav_header_sent and AudioChunk.is_type(event.type):
                        yield AudioChunk.from_event(event).audio
                    elif AudioStop.is_type(event.type):
                        log.debug("Streaming: AudioStop received, finishing")
                        break
        except WyomingConnectionError as e:
            log.error("Streaming failed: %s", e)
            raise HTTPException(status_code=503, detail=str(e))
        except WyomingProtocolError as e:
            log.error("Streaming failed: %s", e)
            raise HTTPException(status_code=500, detail=str(e))
