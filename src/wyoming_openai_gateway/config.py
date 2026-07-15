"""Environment-driven configuration for Wyoming-OpenAI-Gateway."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Mapping


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
    wyoming_port: int = 10205
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
        return cls(
            wyoming_host=os.environ.get("WYOMING_HOST", "127.0.0.1"),
            wyoming_port=_get_int("WYOMING_PORT", 10205),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=_get_int("PORT", 8555),
            debug=_get_bool("DEBUG", False),
            log_level=_get_log_level("LOG_LEVEL", "INFO"),
            prefix=os.environ.get("PREFIX", "/v1"),
        )
