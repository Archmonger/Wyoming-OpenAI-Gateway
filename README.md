# Wyoming-OpenAI-Gateway

A gateway that exposes local [Wyoming](https://github.com/rhasspy/wyoming) protocol services via OpenAI-compatible API endpoints. This allows any OpenAI-compatible client to use local Wyoming speech services (TTS) without modification.

## Features

- **OpenAI-Compatible API** — Drop-in replacement for OpenAI's `/v1/audio/speech` and `/v1/voices` endpoints
- **Wyoming Protocol** — Connects to any Wyoming-compatible service (Piper, Sherpa-ONNX, etc.)
- **Streaming Support** — Real-time audio streaming for both OpenAI and Wyoming protocols
- **Single Binary** — Install via pip or Docker, deploy anywhere
- **Health Checks** — Kubernetes/Docker-ready `/healthz` and `/readyz` endpoints

## Quick Start

### Docker

```bash
docker run -d \
  --name wyoming-openai-gateway \
  -p 8555:8555 \
  -e WYOMING_HOST=your-wyoming-server \
  -e WYOMING_PORT=10205 \
  ghcr.io/archmonger/wyoming-openai-gateway:latest
```

### Using pip

```bash
pip install wyoming-openai-gateway

WYOMING_HOST=127.0.0.1 WYOMING_PORT=10205 wyoming-openai-gateway
```

### Using Docker Compose

```bash
wget https://raw.githubusercontent.com/archmonger/Wyoming-OpenAI-Gateway/main/compose.yml
WYOMING_HOST=127.0.0.1 WYOMING_PORT=10205 docker compose up -d
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

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WYOMING_HOST` | `127.0.0.1` | Wyoming server hostname |
| `WYOMING_PORT` | `10205` | Wyoming server port |
| `HOST` | `0.0.0.0` | Gateway HTTP listen address |
| `PORT` | `8555` | Gateway HTTP listen port |
| `DEBUG` | `false` | Enable debug logging |
| `LOG_LEVEL` | `INFO` | Logging level |

## Architecture

```
┌─────────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│                     │       │                      │       │                      │
│  OpenAI-compatible  │ HTTP  │  Wyoming-OpenAI-     │ TCP   │  Wyoming Protocol    │
│  Client             │──────▶│  Gateway             │──────▶│  Server (e.g. Piper) │
│  (curl, ST, Home   │       │                      │       │                      │
│   Assistant, etc.)  │       │  FastAPI → Wyoming   │       │  TTS Service         │
│                     │◀──────│  Protocol Translator  │◀──────│                      │
└─────────────────────┘       └──────────────────────┘       └──────────────────────┘
```

The gateway acts as a **protocol translator** between OpenAI's HTTP API and the Wyoming TCP protocol. It maps REST endpoints to Wyoming events (Describe, Synthesize, etc.) and translates audio data formats transparently.

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
