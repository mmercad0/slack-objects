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
        return Users(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger, user_id=user_id)

    def conversations(self, channel_id: Optional[str] = None) -> Conversations:
        return Conversations(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger, channel_id=channel_id)

    def files(self, file_id: Optional[str] = None) -> Files:
        return Files(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger, file_id=file_id)

    def messages(self, channel_id: Optional[str] = None, ts: Optional[str] = None) -> Messages:
        return Messages(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger, channel_id=channel_id, ts=ts)

    def workspaces(self, workspace_id: Optional[str] = None) -> Workspaces:
        return Workspaces(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger, workspace_id=workspace_id)

    def idp_groups(self, group_id: Optional[str] = None) -> IDP_groups:
        return IDP_groups(cfg=self.cfg, client=self.web_client, api=self.api, logger=self.logger, group_id=group_id)
