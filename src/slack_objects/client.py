from slack_sdk import WebClient
import logging
from typing import Optional

from .config import SlackObjectsConfig
from .api_caller import SlackApiCaller
from .users import Users
#from .channels import Channels
#from .files import Files
#from .messages import Messages
#from .workspaces import Workspaces
#from .idp_groups import IDP_groups


class SlackObjectsClient:
    """
    Central factory / context object.
    Owns config, Slack client, and rate-limited API caller.
    """

    def __init__(self, cfg: SlackObjectsConfig, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.logger = logger or logging.getLogger("slack-objects")

        self.web_client = WebClient(token=cfg.bot_token)
        self.api = SlackApiCaller(cfg)

    def users(self, user_id: Optional[str] = None) -> Users:
        """
        Factory method:
            users = slack.users()          -> shared unbound instance
            user  = slack.users("U123")    -> bound instance sharing context
        """
        return Users(self.cfg, self.web_client, self.logger, self.api)

    def channels(self) -> Channels:
        return Channels(self.cfg, self.web_client, self.logger, self.api)

    def files(self) -> Files:
        return Files(self.cfg, self.web_client, self.logger, self.api)

    def messages(self) -> Messages:
        return Messages(self.cfg, self.web_client, self.logger, self.api)

    def workspaces(self) -> Workspaces:
        return Workspaces(self.cfg, self.web_client, self.logger, self.api)

    def idp_groups(self) -> IDP_groups:
        return IDP_groups(self.cfg, self.logger)
