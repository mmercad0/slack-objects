from slack_sdk import WebClient
import logging
from typing import Optional

from .config import SlackObjectsConfig
from .api_caller import SlackApiCaller
from .users import Users
from .messages import Messages
from .conversations import Conversations
from .files import Files
from .workspaces import Workspaces
from .idp_groups import IDP_groups


class SlackObjectsClient:
    """
    Central factory / context object.
    Owns config, Slack client, and rate-limited API caller.
    """

    def __init__(self, cfg: SlackObjectsConfig, logger: logging.Logger | None = None):
        if not cfg.bot_token:
            raise ValueError("SlackObjectsConfig must have a bot_token for SlackObjectsClient")

        self.cfg = cfg
        self.logger = logger or logging.getLogger("slack-objects")

        self.web_client = WebClient(token=cfg.bot_token)
        self.api = SlackApiCaller(cfg)

    def users(self, user_id: Optional[str] = None) -> Users:
        return Users(self.cfg, self.web_client, self.logger, self.api)

    def conversations(self) -> Conversations:
        return Conversations(self.cfg, self.web_client, self.logger, self.api)

    def files(self) -> Files:
        return Files(self.cfg, self.web_client, self.logger, self.api)

    def messages(self) -> Messages:
        return Messages(self.cfg, self.web_client, self.logger, self.api)

    def workspaces(self) -> Workspaces:
        return Workspaces(self.cfg, self.web_client, self.logger, self.api)

    def idp_groups(self) -> IDP_groups:
        return IDP_groups(self.cfg, self.logger)