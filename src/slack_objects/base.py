import logging
from dataclasses import dataclass, field
from typing import Optional, Any
from slack_sdk import WebClient

from .api_caller import SlackApiCaller
from .config import SlackObjectsConfig


# Keys that are safe to include in error messages (never contain tokens)
_SAFE_ERROR_KEYS = frozenset({"ok", "error", "needed", "provided", "response_metadata"})


def safe_error_context(resp: Any, *, max_len: int = 300) -> str:
    """
    Return a truncated, token-free summary of an API response for use in exception messages.

    Only well-known diagnostic keys are kept. The result is capped at *max_len* characters
    to prevent massive payloads from flooding logs or error-tracking systems.
    """
    if isinstance(resp, dict):
        summary = {k: v for k, v in resp.items() if k in _SAFE_ERROR_KEYS}
    else:
        summary = repr(resp)
    text = str(summary)
    return text[:max_len] + ("..." if len(text) > max_len else "")


@dataclass
class SlackObjectBase:
    """
    Base class that all object helpers inherit from.

    Holds shared context so every object doesn't need to reinvent plumbing (i.e., don't need to pass cfg, client, logger, and the apicaller).
    Logging is optional; a default package logger will be used if none is provided.
    """
    cfg: SlackObjectsConfig
    client: WebClient
    api: SlackApiCaller
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("slack-objects"))  # logger is guaranteed to exist via default_factory

    def __post_init__(self) -> None:
        # Required dependencies check
        if self.cfg is None:
            raise ValueError("cfg is required")
        if self.client is None:
            raise ValueError("client is required")
        if self.api is None:
            raise ValueError("api is required")
