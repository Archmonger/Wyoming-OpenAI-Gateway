"""Core translation layer — converts OpenAI API requests to Wyoming protocol."""

from __future__ import annotations

import io
import logging
import struct
import subprocess
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

    Handles WAV files natively. All other formats (MP3, FLAC, OGG, WebM, etc.)
    are decoded via ffmpeg to the target format. If ffmpeg is not available,
    falls back to passing the raw bytes through.
    """
    raw = file.file.read()

    if not raw:
        log.warning("Uploaded file is empty")
        return b"", target_rate, target_width, target_channels

    # --- Case 1: Native WAV decoding ---
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
                rate, width * 8, channels,
                len(frames) // (width * channels) if width * channels > 0 else 0,
            )

            pcm = frames
            src_width, src_channels = width, channels

            # Stereo-to-mono downmix
            if src_channels == 2 and target_channels == 1:
                if src_width == 2:
                    samples = struct.unpack("<" + "h" * (len(pcm) // 2))
                    mono = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)]
                    pcm = struct.pack("<" + "h" * len(mono), *mono)
                elif src_width == 1:
                    mono = bytes((pcm[i] + pcm[i + 1]) // 2 for i in range(0, len(pcm), 2))
                    pcm = mono
                src_channels = 1

            # 8-bit to 16-bit up-conversion
            if src_width == 1 and target_width == 2:
                pcm = struct.pack("<" + "H" * len(pcm), *(b << 8 for b in pcm))
                src_width = 2

            # Return original rate — the Wyoming server handles resampling
            return pcm, rate, src_width, src_channels

        except Exception as e:
            log.warning("Failed to parse uploaded WAV: %s — trying ffmpeg fallback", e)

    # --- Case 2: Non-WAV — decode via ffmpeg ---
    try:
        # Probe the input format first
        probe = subprocess.run(
            ["ffprobe", "-hide_banner", "-v", "quiet", "-show_format", "-show_streams",
             "-of", "json", "pipe:0"],
            input=raw,
            capture_output=True,
            timeout=15,
        )
        if probe.returncode != 0:
            log.warning("ffprobe could not identify audio format, sending raw bytes")
            return raw, target_rate, target_width, target_channels

        # Convert to WAV via ffmpeg
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-v", "error",
                "-i", "pipe:0",
                "-ar", str(target_rate),
                "-ac", str(target_channels),
                "-sample_fmt", "s16",
                "-f", "wav",
                "pipe:1",
            ],
            input=raw,
            capture_output=True,
            timeout=120,
        )

        if proc.returncode != 0:
            log.warning(
                "ffmpeg conversion failed (rc=%d): %s",
                proc.returncode,
                proc.stderr.decode(errors="replace")[:200],
            )
            return raw, target_rate, target_width, target_channels

        wav_bytes = proc.stdout
        if len(wav_bytes) < 44:
            log.warning("ffmpeg produced invalid WAV (%d bytes), sending raw", len(wav_bytes))
            return raw, target_rate, target_width, target_channels

        # Extract PCM from the converted WAV
        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, "rb") as wav:
                pcm = wav.readframes(wav.getnframes())

        log.info(
            "Decoded %s via ffmpeg: %d Hz, 16-bit, %d ch, %d PCM bytes",
            file.filename or "audio",
            target_rate, target_channels,
            len(pcm),
        )
        return pcm, target_rate, target_width, target_channels

    except FileNotFoundError:
        log.warning("ffmpeg not found on system — cannot decode audio format, sending raw bytes")
        return raw, target_rate, target_width, target_channels
    except subprocess.TimeoutExpired:
        log.warning("ffmpeg conversion timed out — sending raw bytes")
        return raw, target_rate, target_width, target_channels
    except Exception as e:
        log.warning("ffmpeg conversion error: %s — sending raw bytes", e)
        return raw, target_rate, target_width, target_channels


class OpenAIGateway:
    """Translates OpenAI-compatible API requests into Wyoming protocol calls."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_voices(self) -> VoicesResponse:
        """List all available TTS voices from the Wyoming TTS server."""
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
        """Transcribe or translate audio using Wyoming ASR protocol.

        Accepts OpenAI-compatible multipart form data. Audio is decoded to
        PCM (via wave or ffmpeg) and streamed to the Wyoming ASR server.
        """
        log.info(
            "Processing STT request: model=%s, language=%s, format=%s, translate=%s",
            request.model,
            request.language,
            request.response_format,
            is_translation,
        )

        pcm_bytes, rate, width, channels = _pcm_from_upload(
            file,
            target_rate=16000,
            target_width=2,
            target_channels=1,
        )

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
