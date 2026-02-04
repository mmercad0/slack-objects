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
        self.cfg = cfg
        self.logger = logger or logging.getLogger("slack-objects")

        # Prefer bot token for general Web API calls; fall back to user token.
        web_token = cfg.bot_token or cfg.user_token
        if not web_token:
            raise ValueError("SlackObjectsClient requires cfg.bot_token or cfg.user_token.")

        self.web_client = WebClient(token=web_token)
        self.api = SlackApiCaller(cfg)

    def users(self, user_id: Optional[str] = None) -> Users:
        base = Users(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger)
        return base if user_id is None else base.with_user(user_id)

    def conversations(self) -> Conversations:
        return Conversations(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger)

    def files(self) -> Files:
        return Files(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger)

    def messages(self) -> Messages:
        return Messages(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger)

    def workspaces(self) -> Workspaces:
        return Workspaces(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger)

    def idp_groups(self) -> IDP_groups:
        return IDP_groups(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger)
