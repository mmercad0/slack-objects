import logging
from typing import Any, Dict, Optional

from slack_objects.client import SlackObjectsClient
from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.api_caller import SlackApiCaller


class FakeWebClient:
    def api_call(self, method: str, json: Optional[Dict[str, Any]] = None):
        payload = json or {}

        if method == "users.info":
            return {"ok": True, "user": {
                "id": payload.get("user", "U_TEST"),
                "real_name": "[External] Test User",
                "profile": {"display_name": "Testy"},
                "is_restricted": False,
                "is_ultra_restricted": False,
            }}

        if method == "users.lookupByEmail":
            if payload.get("email") == "found@example.com":
                return {"ok": True, "user": {"id": "U_FOUND"}}
            return {"ok": False, "error": "users_not_found"}

        return {"ok": True}


class FakeApiCaller(SlackApiCaller):
    def __init__(self, cfg):
        self.cfg = cfg
        self.policy = None

    def call(self, client, method: str, *, rate_tier=None, **kwargs):
        # No sleeping, no SlackResponse normalization needed for this fake
        return client.api_call(method, json=kwargs)


def test_factory_users_unbound_and_bound():
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_3,
    )

    # Build a SlackObjectsClient, but swap its internals to fakes for unit tests
    slack = SlackObjectsClient(cfg, logger=logging.getLogger("test"))
    slack.web_client = FakeWebClient()
    slack.api = FakeApiCaller(cfg)
    slack._users = None  # force rebuild with the fakes

    users = slack.users()
    assert users.user_id is None

    bound = slack.users("U123")
    attrs = bound.refresh()
    assert attrs["id"] == "U123"
    assert bound.is_contingent_worker() is True

    uid = users.get_user_id_from_email("found@example.com")
    assert uid == "U_FOUND"
