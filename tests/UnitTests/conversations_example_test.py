import unittest
from typing import Any, Dict

from slack_objects.conversations import Conversations
from slack_objects.config import SlackObjectsConfig


class FakeClient:
    """A fake Slack client exposing api_call(method, json=payload) like slack_sdk.WebClient does."""
    def __init__(self):
        self.calls = []

    def api_call(self, method: str, json: Dict[str, Any]):
        self.calls.append((method, dict(json)))

        if method == "conversations.info":
            # Minimal fake response
            chan = json["channel"]
            return {"ok": True, "channel": {"id": chan, "name": "general", "is_private": False}}

        if method == "conversations.history":
            # One-page history, no cursor
            return {"ok": True, "messages": [{"ts": "1", "text": "hello"}]}

        if method == "admin.conversations.search":
            # One-page search, exact match
            return {"ok": True, "conversations": [{"id": "C123", "name": json["query"]}], "next_cursor": ""}

        if method == "admin.conversations.archive":
            return {"ok": True}

        raise AssertionError(f"Unhandled method in FakeClient: {method}")


class FakeApiCaller:
    """A fake SlackApiCaller that calls the client's api_call directly."""
    def call(self, client, method: str, *, rate_tier=None, **kwargs):
        return client.api_call(method, json=kwargs)


class ConversationsTests(unittest.TestCase):
    def test_refresh_and_is_private(self):
        cfg = SlackObjectsConfig(bot_token="xoxb-test")  # minimal
        conv = Conversations(cfg=cfg, client=FakeClient(), logger=None, api=FakeApiCaller(), channel_id="C123")
        conv.refresh()
        self.assertEqual(conv.get_conversation_name(), "general")
        self.assertFalse(conv.is_private())

    def test_get_messages(self):
        cfg = SlackObjectsConfig(bot_token="xoxb-test")
        conv = Conversations(cfg=cfg, client=FakeClient(), logger=None, api=FakeApiCaller(), channel_id="C123")
        msgs = conv.get_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["text"], "hello")

    def test_get_conversation_ids_from_name(self):
        cfg = SlackObjectsConfig(bot_token="xoxb-test")
        conv = Conversations(cfg=cfg, client=FakeClient(), logger=None, api=FakeApiCaller())
        ids = conv.get_conversation_ids_from_name("general")
        self.assertEqual(ids, ["C123"])


if __name__ == "__main__":
    unittest.main()
