"""Core translation layer — converts OpenAI API requests to Wyoming protocol."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import miniaudio
from fastapi import HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from wyoming.audio import AudioChunk, AudioStart, AudioStop

from .audio_utils import assemble_wav, create_wav_header
from .config import Settings
from .errors import WyomingConnectionError, WyomingProtocolError
from .openai_models import (
    SpeechRequest,
    TranscriptionRequest,
    TranscriptionResponse,
    TranslationResponse,
    Voice,
    VoicesResponse,
)
from .wyoming_client import WyomingStreamClient

log = logging.getLogger(__name__)


WYOMING_TARGET_RATE = 16000
WYOMING_TARGET_WIDTH = 2
WYOMING_TARGET_CHANNELS = 1


def _pcm_from_upload(
    file: UploadFile,
) -> tuple[bytes, int, int, int]:
    """Decode uploaded audio to raw PCM via miniaudio.

    Returns (pcm_bytes, rate, width, channels).

    Supports WAV, MP3, FLAC, and other formats miniaudio can decode.
    """
    raw = file.file.read()

    if not raw:
        log.warning("Uploaded file is empty")
        return b"", WYOMING_TARGET_RATE, WYOMING_TARGET_WIDTH, WYOMING_TARGET_CHANNELS

    try:
        result = miniaudio.decode(
            raw,
            output_format=miniaudio.SampleFormat.SIGNED16,
        )
        # result: DecodeResult with .samples (array('h')), .sample_rate, .nchannels
        pcm = result.samples.tobytes()
        log.debug(
            "Decoded %s: %d Hz, 16-bit, %d ch, %d PCM bytes",
            file.filename or "audio",
            result.sample_rate,
            result.nchannels,
            len(pcm),
        )
        # Return native sample rate — the Wyoming server handles resampling
        return pcm, result.sample_rate, WYOMING_TARGET_WIDTH, result.nchannels
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format or corrupt file: {e}",
        )


class OpenAIGateway:
    """Translates OpenAI-compatible API requests into Wyoming protocol calls."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_voices(self) -> VoicesResponse:
        """List all available TTS voices from the Wyoming TTS server."""
        if self._settings.tts_host is None or self._settings.tts_port is None:
            raise HTTPException(status_code=503, detail="TTS not configured")

        try:
            async with WyomingStreamClient(
                self._settings.tts_host, self._settings.tts_port
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
                            description=str(voice.attribution) if voice.attribution else None,
                            languages=voice.languages,
                        )
                    )

        if not voices:
            return VoicesResponse(voices=[])
        return VoicesResponse(voices=voices)

    async def list_models(self) -> list[dict]:
        """List available models based on configured services."""
        models = []
        if self._settings.tts_host and self._settings.tts_port:
            models.append({"id": "wyoming-tts", "object": "model", "created": 0, "owned_by": "wyoming"})
        if self._settings.stt_host and self._settings.stt_port:
            models.append({"id": "whisper-1", "object": "model", "created": 0, "owned_by": "wyoming"})
        return models

    async def text_to_speech(self, request: SpeechRequest) -> Response:
        """Convert text to speech via Wyoming protocol."""
        if self._settings.tts_host is None or self._settings.tts_port is None:
            raise HTTPException(status_code=503, detail="TTS not configured")

        if request.stream:
            return await self._stream_speech(request)
        return await self._complete_speech(request)

    async def _complete_speech(self, request: SpeechRequest) -> Response:
        """Generate complete (non-streaming) speech response."""
        try:
            async with WyomingStreamClient(
                self._settings.tts_host, self._settings.tts_port
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
                self._settings.tts_host, self._settings.tts_port
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

    async def transcribe_audio(
        self,
        file: UploadFile,
        request: TranscriptionRequest,
        is_translation: bool = False,
    ) -> TranscriptionResponse | TranslationResponse:
        """Transcribe or translate audio using Wyoming ASR protocol."""
        if self._settings.stt_host is None or self._settings.stt_port is None:
            raise HTTPException(status_code=503, detail="STT not configured")

        log.info(
            "Processing STT request: model=%s, language=%s, format=%s, translate=%s",
            request.model,
            request.language,
            request.response_format,
            is_translation,
        )

        pcm_bytes, rate, width, channels = _pcm_from_upload(file)

        if not pcm_bytes:
            raise HTTPException(status_code=400, detail="No audio data received")

        log.debug(
            "Audio input: %d bytes, %d Hz, %d-bit, %d channels",
            len(pcm_bytes), rate, width * 8, channels,
        )

        try:
            async with WyomingStreamClient(
                self._settings.stt_host, self._settings.stt_port
            ) as client:
                text = await client.transcribe(
                    audio_bytes=pcm_bytes,
                    rate=rate,
                    width=width,
                    channels=channels,
                    language=request.language,
                    model_name=request.model,
                )
        except WyomingConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except WyomingProtocolError as e:
            raise HTTPException(status_code=500, detail=str(e))

        log.info("Transcription result (%d chars): %s", len(text), text[:100])

        if is_translation:
            return TranslationResponse(text=text)

        return TranscriptionResponse(text=text)
