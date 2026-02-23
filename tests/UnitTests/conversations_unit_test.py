import unittest
from typing import Any, Dict

from slack_objects.conversations import Conversations
from slack_objects.config import SlackObjectsConfig, CONVERSATION_ID_RE


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


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSATION_ID_RE
# ═══════════════════════════════════════════════════════════════════════════

class TestConversationIdRegex(unittest.TestCase):
    """CONVERSATION_ID_RE should match Slack conversation ID patterns."""

    def test_valid_channel_ids(self):
        for valid in ("C01ABC123", "C123", "CABC"):
            self.assertTrue(CONVERSATION_ID_RE.match(valid), f"Expected match for {valid!r}")

    def test_valid_group_ids(self):
        for valid in ("G01ABC123", "G123", "GABC"):
            self.assertTrue(CONVERSATION_ID_RE.match(valid), f"Expected match for {valid!r}")

    def test_valid_dm_ids(self):
        for valid in ("D01ABC123", "D123", "DABC"):
            self.assertTrue(CONVERSATION_ID_RE.match(valid), f"Expected match for {valid!r}")

    def test_rejects_lowercase(self):
        for invalid in ("c01abc", "Cabc", "g0abc", "d0abc"):
            self.assertFalse(CONVERSATION_ID_RE.match(invalid), f"Should not match {invalid!r}")

    def test_rejects_non_conversation_prefixes(self):
        for invalid in ("U123", "W456", "T789", "S000", ""):
            self.assertFalse(CONVERSATION_ID_RE.match(invalid), f"Should not match {invalid!r}")

    def test_rejects_special_chars(self):
        for invalid in ("C-123", "G_ABC", "D01/../../"):
            self.assertFalse(CONVERSATION_ID_RE.match(invalid), f"Should not match {invalid!r}")


# ═══════════════════════════════════════════════════════════════════════════
# _looks_like_channel_id
# ═══════════════════════════════════════════════════════════════════════════

class TestLooksLikeChannelId(unittest.TestCase):
    """_looks_like_channel_id delegates to CONVERSATION_ID_RE."""

    def test_valid(self):
        self.assertTrue(Conversations._looks_like_channel_id("C01ABC123"))
        self.assertTrue(Conversations._looks_like_channel_id("G0ABC"))
        self.assertTrue(Conversations._looks_like_channel_id("D01ABC123"))

    def test_invalid(self):
        self.assertFalse(Conversations._looks_like_channel_id("U01ABC123"))
        self.assertFalse(Conversations._looks_like_channel_id("general"))
        self.assertFalse(Conversations._looks_like_channel_id("S123"))
        self.assertFalse(Conversations._looks_like_channel_id(""))


if __name__ == "__main__":
    unittest.main()
