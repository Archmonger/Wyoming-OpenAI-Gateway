"""CLI entrypoint for Wyoming-OpenAI-Gateway."""

from __future__ import annotations

import logging
import sys


def main() -> None:
    """Run the Wyoming-OpenAI-Gateway server."""
    from .config import Settings
    from .app import create_app

    settings = Settings._parse()

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = create_app(settings)

    import uvicorn

    log_level = "debug" if settings.debug else settings.log_level.lower()
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None, log_level=log_level)


if __name__ == "__main__":
    main()
