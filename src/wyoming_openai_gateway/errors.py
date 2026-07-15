"""Custom exception hierarchy for Wyoming-OpenAI-Gateway."""


class WyomingOpenAIError(Exception):
    """Base exception for all Wyoming-OpenAI-Gateway errors."""


class WyomingConnectionError(WyomingOpenAIError):
    """Raised when unable to connect to the Wyoming server."""


class WyomingProtocolError(WyomingOpenAIError):
    """Raised when Wyoming protocol data is unexpected or malformed."""


class AudioGenerationError(WyomingOpenAIError):
    """Raised when audio generation or processing fails."""
