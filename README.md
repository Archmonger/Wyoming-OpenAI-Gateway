# Wyoming-OpenAI-Gateway

A gateway that exposes local [Wyoming](https://github.com/rhasspy/wyoming) protocol services via OpenAI-compatible API endpoints. This allows any OpenAI-compatible client to use local Wyoming speech services (TTS **and** ASR/STT) without modification.

## Features

- **OpenAI-Compatible API** — Drop-in replacement for OpenAI's `/v1/audio/speech`, `/v1/audio/transcriptions`, `/v1/audio/translations`, and `/v1/voices` endpoints
- **Wyoming Protocol** — Connects to any Wyoming-compatible TTS service (Piper, Sherpa-ONNX, etc.) **and** any Wyoming-compatible ASR service (faster-whisper, Sherpa-ONNX, etc.)
- **Streaming Support** — Real-time audio streaming for both TTS and ASR protocols
- **Single Binary** — Install via pip or Docker, deploy anywhere
- **Health Checks** — Kubernetes/Docker-ready `/healthz` and `/readyz` endpoints

## Quick Start

### Docker

```bash
docker run -d \
  --name wyoming-openai-gateway \
  -p 8555:8555 \
  -e WYOMING_HOST=your-tts-server \
  -e WYOMING_PORT=10205 \
  -e ASR_HOST=your-asr-server \
  -e ASR_PORT=10200 \
  ghcr.io/archmonger/wyoming-openai-gateway:latest
```

### Using pip

```bash
pip install wyoming-openai-gateway

WYOMING_HOST=127.0.0.1 WYOMING_PORT=10205 \
ASR_HOST=127.0.0.1 ASR_PORT=10200 \
wyoming-openai-gateway
```

### Using Docker Compose

```bash
wget https://raw.githubusercontent.com/archmonger/Wyoming-OpenAI-Gateway/main/compose.yml
WYOMING_HOST=127.0.0.1 WYOMING_PORT=10205 \
ASR_HOST=127.0.0.1 ASR_PORT=10200 \
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

Transcribes audio into the input language. Mirrors OpenAI's [Create Transcription](https://platform.openai.com/docs/api-reference/audio/createTranscription) endpoint.

**Request Body (multipart/form-data):**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | file | (required) | The audio file to transcribe (WAV or raw PCM) |
| `model` | string | `"whisper-1"` | Model identifier (passed to Wyoming ASR) |
| `language` | string | `null` | Language code (e.g. `"en"`) |
| `prompt` | string | `null` | Optional context prompt (not yet implemented) |
| `response_format` | string | `"json"` | Response format (`json` or `text`) |
| `temperature` | float | `0.0` | Sampling temperature |

**Example using `curl`:**
```bash
curl http://localhost:8555/v1/audio/transcriptions \
  -F "file=@recording.wav" \
  -F "model=whisper-1" \
  -F "language=en"
```

**Response (JSON):**
```json
{
  "text": "Hello, world! This is a transcription."
}
```

### `POST /v1/audio/translations`

Translates audio into English. Mirrors OpenAI's [Create Translation](https://platform.openai.com/docs/api-reference/audio/createTranslation) endpoint.

**Request Body (multipart/form-data):**

Same fields as `POST /v1/audio/transcriptions`.

**Example using `curl`:**
```bash
curl http://localhost:8555/v1/audio/translations \
  -F "file=@french_recording.wav" \
  -F "model=whisper-1"
```

**Response (JSON):**
```json
{
  "text": "Hello, this is a translation."
}
```

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WYOMING_HOST` | `127.0.0.1` | Wyoming TTS server hostname |
| `WYOMING_PORT` | `10200` | Wyoming TTS server port |
| `ASR_HOST` | value of `WYOMING_HOST` | Wyoming ASR (STT) server hostname |
| `ASR_PORT` | value of `WYOMING_PORT` | Wyoming ASR (STT) server port |
| `HOST` | `0.0.0.0` | Gateway HTTP listen address |
| `PORT` | `8555` | Gateway HTTP listen port |
| `PREFIX` | `/v1` | API route prefix |
| `DEBUG` | `false` | Enable debug logging |
| `LOG_LEVEL` | `INFO` | Logging level |

> **Note:** `ASR_HOST` and `ASR_PORT` default to the values of `WYOMING_HOST` and `WYOMING_PORT` respectively. If your TTS and ASR servers run on the same host but different ports, you only need to set the port overrides.

## Architecture

```
                        ┌──────────────────────────────────┐
                        │          Wyoming Server(s)       │
                        │  ┌────────────────────────────┐  │
┌─────────────────┐     │  │  Wyoming TTS Server         │  │
│                 │     │  │  (Piper, Sherpa-ONNX, ...)  │  │
│ OpenAI-compatible│ HTTP │  └────────────────────────────┘  │
│ Client          │────▶│                                   │
│ (curl, ST, Home │     │  ┌────────────────────────────┐  │
│  Assistant, etc.)│     │  │  Wyoming ASR Server        │  │
│                 │◀────│  │  (faster-whisper,          │  │
└─────────────────┘     │  │   Sherpa-ONNX, ...)        │  │
                        │  └────────────────────────────┘  │
                        └──────────────────────────────────┘
                                ▲
                                │ TCP (Wyoming Protocol)
                                ▼
                        ┌──────────────────────┐
                        │                      │
                        │  Wyoming-OpenAI-     │
                        │  Gateway             │
                        │                      │
                        │  FastAPI → Wyoming   │
                        │  Protocol Translator  │
                        │                      │
                        └──────────────────────┘
                                ▲
                                │ HTTP (OpenAI API)
                                ▼
                        ┌─────────────────┐
                        │                 │
                        │  OpenAI-compatible│
                        │  Client          │
                        │                 │
                        └─────────────────┘
```

The gateway acts as a **protocol translator** between OpenAI's HTTP API and the Wyoming TCP protocol. It maps REST endpoints to Wyoming events:

| OpenAI Endpoint | Wyoming Events |
|-----------------|----------------|
| `POST /v1/audio/speech` | `Describe` → `Synthesize` → `AudioStart` → `AudioChunk(s)` → `AudioStop` |
| `POST /v1/audio/transcriptions` | `Transcribe` → `AudioStart` → `AudioChunk(s)` → `AudioStop` → `Transcript` |
| `POST /v1/audio/translations` | `Transcribe` → `AudioStart` → `AudioChunk(s)` → `AudioStop` → `Transcript` |

Audio data from uploaded files is automatically decoded (WAV files are parsed for sample rate, bit depth, and channel count; other formats are passed through as raw PCM).

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
python -m wyoming_openai_gateway
```

## License

MIT
