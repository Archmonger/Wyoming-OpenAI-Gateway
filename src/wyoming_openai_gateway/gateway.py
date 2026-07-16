"""Core translation layer — converts OpenAI API requests to Wyoming protocol."""

from __future__ import annotations

import io
import logging
import struct
import wave
from collections.abc import AsyncGenerator

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


def _pcm_from_upload(
    file: UploadFile,
    target_rate: int = 16000,
    target_width: int = 2,
    target_channels: int = 1,
) -> tuple[bytes, int, int, int]:
    """Extract raw PCM audio from an uploaded audio file.

    Returns (pcm_bytes, rate, width, channels).
    WAV files are decoded; other formats are passed through raw.
    """
    raw = file.file.read()

    if raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        try:
            with io.BytesIO(raw) as buf:
                with wave.open(buf, "rb") as wav:
                    rate = wav.getframerate()
                    width = wav.getsampwidth()
                    channels = wav.getnchannels()
                    frames = wav.readframes(wav.getnframes())
            log.debug(
                "Decoded WAV: %d Hz, %d-bit, %d ch, %d frames",
                rate, width * 8, channels, len(frames) // (width * channels) if width * channels > 0 else 0,
            )
            # Convert to target format if needed
            pcm = frames
            _, src_width, src_channels = rate, width, channels

            # Simple mono conversion: mix to mono if stereo
            if src_channels == 2 and target_channels == 1:
                # Rough mono mix from 16-bit stereo interleaved
                if src_width == 2:
                    samples = struct.unpack("<" + "h" * (len(pcm) // 2))
                    mono = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)]
                    pcm = struct.pack("<" + "h" * len(mono), *mono)
                elif src_width == 1:
                    mono = bytes((pcm[i] + pcm[i + 1]) // 2 for i in range(0, len(pcm), 2))
                    pcm = mono
                src_channels = 1

            # Convert to 16-bit if needed
            if src_width == 1 and target_width == 2:
                pcm = struct.pack("<" + "h" * len(pcm), *(b << 8 for b in pcm))
                src_width = 2

            return pcm, rate, src_width, src_channels
        except Exception as e:
            log.warning("Failed to decode uploaded WAV: %s — sending raw bytes", e)

    log.debug(
        "Passing through raw PCM (%d bytes, %d Hz, %d-bit, %d ch)",
        len(raw), target_rate, target_width, target_channels,
    )
    return raw, target_rate, target_width, target_channels


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
                            description=str(voice.attribution) if voice.attribution else None,
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

    async def transcribe_audio(
        self,
        file: UploadFile,
        request: TranscriptionRequest,
        is_translation: bool = False,
    ) -> TranscriptionResponse | TranslationResponse:
        """Transcribe or translate audio using Wyoming ASR protocol.

        Accepts OpenAI-compatible multipart form data, extracts PCM audio,
        sends it to the Wyoming ASR server, and returns the result as JSON.
        """
        log.info(
            "Processing STT request: model=%s, language=%s, translate=%s",
            request.model,
            request.language,
            is_translation,
        )

        pcm_bytes, rate, width, channels = _pcm_from_upload(
            file, target_rate=16000, target_width=2, target_channels=1,
        )

        if not pcm_bytes:
            raise HTTPException(status_code=400, detail="No audio data received")

        log.debug(
            "Audio input: %d bytes, %d Hz, %d-bit, %d channels",
            len(pcm_bytes), rate, width * 8, channels,
        )

        try:
            async with WyomingStreamClient(
                self._settings.asr_host, self._settings.asr_port
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
