"""Tests for audio utility functions."""

from __future__ import annotations

import struct

from wyoming_openai_gateway.audio_utils import assemble_wav, create_wav_header


def test_create_wav_header():
    """Test WAV header creation."""
    header = create_wav_header(sample_rate=22050, bits_per_sample=16, channels=1)
    assert len(header) == 44  # Standard WAV header is 44 bytes
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    assert header[12:16] == b"fmt "
    # Parse format fields
    audio_format, num_channels, sample_rate, byte_rate, block_align, bits = struct.unpack(
        "<HHLLHH", header[20:36]
    )
    assert audio_format == 1  # PCM
    assert num_channels == 1
    assert sample_rate == 22050
    assert bits == 16


def test_create_wav_header_stereo():
    """Test WAV header for stereo 48kHz."""
    header = create_wav_header(sample_rate=48000, bits_per_sample=16, channels=2)
    assert header[:4] == b"RIFF"
    _, _, _, _, _, audio_format, num_channels, sample_rate, _, _, bits = struct.unpack(
        "<4sL4s4sLHHLLHH", header[:36]
    )
    assert audio_format == 1
    assert num_channels == 2
    assert sample_rate == 48000
    assert bits == 16


def test_assemble_wav():
    """Test assembling a WAV file from audio chunks."""
    # Create some dummy PCM audio data
    audio_chunks = [b"\x00\x00" * 100]  # 100 samples of 16-bit silence
    wav_bytes = assemble_wav(audio_chunks, rate=16000, width=2, channels=1)
    assert len(wav_bytes) > 44  # Header + data
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    # Data chunk ID is at byte 36
    assert wav_bytes[36:40] == b"data"
    # Data size at byte 40 should be the PCM data length
    data_size = int.from_bytes(wav_bytes[40:44], "little")
    assert data_size == 200  # 100 samples * 2 bytes
    # Total file size should be header (44) + data
    assert len(wav_bytes) == 44 + data_size
