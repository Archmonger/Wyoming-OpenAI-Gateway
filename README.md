# Wyoming-OpenAI-Gateway

A gateway that exposes local [Wyoming](https://github.com/rhasspy/wyoming) protocol services via OpenAI-compatible API endpoints. This allows any OpenAI-compatible client to use local Wyoming speech services (TTS **and** STT) without modification.

## Features

- **OpenAI-Compatible API** — Drop-in replacement for OpenAI's `/v1/audio/speech`, `/v1/audio/transcriptions`, `/v1/audio/translations`, and `/v1/voices` endpoints
- **Wyoming Protocol** — Connects to any Wyoming-compatible TTS service (Piper, Sherpa-ONNX, etc.) **and** any Wyoming-compatible STT service (faster-whisper, Sherpa-ONNX, etc.)
- **Streaming Support** — Real-time audio streaming for both TTS and STT protocols
- **Zero System Dependencies** — Audio transcoding via `miniaudio` (bundled wheels, ~30x faster than subprocess-based ffmpeg)
- **Health Checks** — Kubernetes/Docker-ready `/healthz` and `/readyz` endpoints

## Quick Start

### Docker

```bash
docker run -d \
  --name wyoming-openai-gateway \
  -p 8555:8555 \
  -e TTS_HOST=your-tts-server \
  -e TTS_PORT=10200 \
  -e STT_HOST=your-stt-server \
  -e STT_PORT=10300 \
  ghcr.io/archmonger/wyoming-openai-gateway:latest
```

### Using pip

```bash
pip install wyoming-openai-gateway

TTS_HOST=127.0.0.1 TTS_PORT=10200 \
STT_HOST=127.0.0.1 STT_PORT=10300 \
wyoming-openai-gateway
```

### Using Docker Compose

```bash
wget https://raw.githubusercontent.com/archmonger/Wyoming-OpenAI-Gateway/main/compose.yml
TTS_HOST=127.0.0.1 TTS_PORT=10200 \
STT_HOST=127.0.0.1 STT_PORT=10300 \
docker compose up -d
```

## API Reference

### `GET /v1/voices`

Lists available TTS voices from the Wyoming server.

**Response:**
```json
{
  "voices": [
    {
      "id": "en_US-lessac-medium",
      "name": "Lessac (Medium)",
      "languages": ["en_US"]
    }
  ]
}
```

### `POST /v1/audio/speech`

Generates speech audio from text.

**Request Body:**
```json
{
  "input": "Hello, world!",
  "model": "wyoming",
  "voice": "en_US-lessac-medium",
  "response_format": "wav",
  "speed": 1.0,
  "stream": false
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input` | string | (required) | The text to synthesize |
| `model` | string | `"wyoming"` | Model identifier (can be any value) |
| `voice` | string | (required) | Voice ID from `/v1/voices` |
| `response_format` | string | `"wav"` | Output format (only `wav` supported) |
| `speed` | float | `1.0` | Speech rate multiplier |
| `stream` | bool | `false` | Enable streaming response |

**Response:** WAV audio data (Content-Type: `audio/wav`)

### `POST /v1/audio/transcriptions`

Transcribes audio to text using a Wyoming STT server.

**Request:** `multipart/form-data`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | file | (required) | Audio file (WAV, MP3, FLAC, etc.) |
| `model` | string | `"whisper-1"` | Model identifier (passed to Wyoming STT) |
| `language` | string | optional | Language code (e.g. `"en"`) |
| `response_format` | string | `"json"` | Response format (`json` or `text`) |
| `temperature` | float | `0.0` | Sampling temperature |

**Response:**
```json
{
  "text": "Your hands lay open in the long fresh grass."
}
```

### `POST /v1/audio/translations`

Same as transcriptions, but translates the audio to English text.

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_HOST` | *(none)* | Wyoming TTS server hostname (omit to disable TTS) |
| `TTS_PORT` | *(none)* | Wyoming TTS server port (required if TTS_HOST is set) |
| `STT_HOST` | *(none)* | Wyoming STT server hostname (omit to disable STT) |
| `STT_PORT` | *(none)* | Wyoming STT server port (required if STT_HOST is set) |
| `HOST` | `0.0.0.0` | Gateway HTTP listen address |
| `PORT` | `8555` | Gateway HTTP listen port |
| `PREFIX` | `/v1` | API route prefix |
| `DEBUG` | `false` | Enable debug logging |
| `LOG_LEVEL` | `INFO` | Logging level |

> **Validation:** At least one of `TTS_HOST` or `STT_HOST` must be defined. It is an error to set only a host without its corresponding port, or vice versa. If neither host is defined, the application will exit with an error.

## Architecture

```
┌─────────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│                     │       │                      │       │                      │
│  OpenAI-compatible  │ HTTP  │  Wyoming-OpenAI-     │ TCP   │  Wyoming Protocol    │
│  Client             │──────>│  Gateway             │──────>│  Server (TTS/STT)    │
│  (curl, ST, Home    │       │                      │       │                      │
│  Assistant, etc.)   │       │  FastAPI → Wyoming   │       │  Piper / Whisper     │
│                     │<──────│  Protocol Translator │<──────│                      │
└─────────────────────┘       └──────────────────────┘       └──────────────────────┘
```

The gateway acts as a **protocol translator** between OpenAI's HTTP API and the Wyoming TCP protocol. It maps REST endpoints to Wyoming events (Describe, Synthesize, Transcribe, etc.) and translates audio data formats transparently using `miniaudio`.

## Development

```bash
git clone https://github.com/archmonger/Wyoming-OpenAI-Gateway.git
cd Wyoming-OpenAI-Gateway

# Install with dev dependencies
pip install -e ".[test]"

# Run tests
pytest --cov=wyoming_openai_gateway

# Run linting
ruff check src/ tests/

# Start the gateway
TTS_HOST=127.0.0.1 TTS_PORT=10200 \
STT_HOST=127.0.0.1 STT_PORT=10300 \
python -m wyoming_openai_gateway
```

## License

MIT
