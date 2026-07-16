"""Environment-driven configuration for Wyoming-OpenAI-Gateway."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _get_bool(key: str, default: str | bool = False) -> bool:
    if isinstance(default, bool):
        default_str = str(default).lower()
    else:
        default_str = default
    val = os.environ.get(key, default_str).lower()
    return val in ("true", "1", "t", "yes")


def _get_int(key: str, default: str | int) -> int:
    if isinstance(default, int):
        default_str = str(default)
    else:
        default_str = default
    return int(os.environ.get(key, default_str))


def _get_log_level(key: str, default: str = "INFO") -> str:
    level = os.environ.get(key, default).upper()
    valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    return level if level in valid else default


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings parsed from environment variables."""

    wyoming_host: str = "127.0.0.1"
    wyoming_port: int = 10200
    asr_host: str = "127.0.0.1"
    asr_port: int = 10200
    host: str = "0.0.0.0"
    port: int = 8555
    debug: bool = False
    log_level: str = "INFO"
    prefix: str = "/v1"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Create Settings from environment variables or a mapping (for testing)."""
        if env is not None:
            # Temporarily patch os.environ for parsing
            old_environ = os.environ.copy()
            os.environ.update({k: v for k, v in env.items() if v is not None})
            try:
                return cls._parse()
            finally:
                os.environ.clear()
                os.environ.update(old_environ)
        return cls._parse()

    @classmethod
    def _parse(cls) -> Settings:
        fallback_host = os.environ.get("WYOMING_HOST", "127.0.0.1")
        fallback_port = _get_int("WYOMING_PORT", 10200)

        return cls(
            wyoming_host=fallback_host,
            wyoming_port=fallback_port,
            asr_host=os.environ.get("ASR_HOST", fallback_host),
            asr_port=_get_int("ASR_PORT", fallback_port),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=_get_int("PORT", 8555),
            debug=_get_bool("DEBUG", False),
            log_level=_get_log_level("LOG_LEVEL", "INFO"),
            prefix=os.environ.get("PREFIX", "/v1"),
        )
