"""Audio processing utilities for Wyoming-OpenAI-Gateway."""

from __future__ import annotations

import io
import struct
import wave


def create_wav_header(sample_rate: int, bits_per_sample: int, channels: int) -> bytes:
    """Create a WAV header with placeholder sizes for streaming.

    Uses 0xFFFFFFFF for chunk sizes to indicate unknown total size,
    which is acceptable for streaming scenarios.
    """
    chunk_size = 0xFFFFFFFF
    final_data_size = 0xFFFFFFFF
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    return struct.pack(
        "<4sL4s4sLHHLLHH4sL",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,  # subchunk1 size (PCM)
        1,  # audio format (1 = PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        final_data_size,
    )


def assemble_wav(audio_chunks: list[bytes], rate: int, width: int, channels: int) -> bytes:
    """Assemble a complete WAV file from audio chunks using the wave module."""
    complete_audio_data = b"".join(audio_chunks)
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_writer:
            wav_writer.setframerate(rate)
            wav_writer.setsampwidth(width)
            wav_writer.setnchannels(channels)
            wav_writer.writeframes(complete_audio_data)
        return wav_io.getvalue()
