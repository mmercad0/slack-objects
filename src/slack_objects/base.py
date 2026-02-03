import logging
from dataclasses import dataclass
from typing import Optional
from slack_sdk import WebClient

from .api_caller import SlackApiCaller
from .config import SlackObjectsConfig


@dataclass
class SlackObjectBase:
    """
    Base class that all object helpers inherit from.
    Holds shared context so every object doesn't need to reinvent plumbing (i.e., don't need to pass cfg, client, logger, and the apicaller).
    """
    cfg: SlackObjectsConfig
    client: WebClient
    logger: logging.Logger
    api: SlackApiCaller

    def __post_init__(self) -> None:
        # Light validation to fail early with clearer errors
        if self.cfg is None:
            raise ValueError("cfg is required")
        if self.client is None:
            raise ValueError("client is required")
        if self.logger is None:
            raise ValueError("logger is required")
        if self.api is None:
            raise ValueError("api is required")
