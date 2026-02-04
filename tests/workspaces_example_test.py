# tests/test_workspaces_example.py
import logging
from typing import Any, Dict, Optional

from slack_objects.client import SlackObjectsClient
from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.api_caller import SlackApiCaller


class FakeWebClient:
    def api_call(self, method: str, json: Optional[Dict[str, Any]] = None):
        payload = json or {}

        if method == "team.info":
            return {"ok": True, "team": {"id": payload.get("team"), "name": "Fake Workspace"}}

        if method == "admin.teams.list":
            # one page only in this fake
            return {"ok": True, "teams": [{"id": "T1", "name": "One"}, {"id": "T2", "name": "Two"}]}

        if method == "admin.users.list":
            return {"ok": True, "users": [{"id": "U1"}, {"id": "U2"}], "response_metadata": {"next_cursor": ""}}

        if method == "admin.teams.admins.list":
            return {"ok": True, "admin_ids": ["U_ADMIN"], "response_metadata": {"next_cursor": ""}}

        return {"ok": True}


class FakeApiCaller(SlackApiCaller):
    def __init__(self, cfg):
        self.cfg = cfg
        self.policy = None

    def call(self, client, method: str, *, rate_tier=None, **kwargs):
        return client.api_call(method, json=kwargs)


def test_workspaces_factory_and_helpers():
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_3,
    )

    slack = SlackObjectsClient(cfg, logger=logging.getLogger("test"))
    slack.web_client = FakeWebClient()
    slack.api = FakeApiCaller(cfg)
    slack._workspaces = None  # force rebuild with fakes if you cache it

    workspaces = slack.workspaces()
    all_ws = workspaces.list_workspaces()
    assert len(all_ws) == 2

    wid = workspaces.get_workspace_id("Two")
    assert wid == "T2"

    ws = slack.workspaces("T1")
    attrs = ws.refresh()
    assert attrs["id"] == "T1"

    users = ws.list_users()
    assert [u["id"] for u in users] == ["U1", "U2"]

    admins = ws.list_admin_ids()
    assert admins == ["U_ADMIN"]
