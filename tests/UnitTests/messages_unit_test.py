# tests/messages_example_test.py

import unittest
from typing import Any, Dict, Optional, List

from slack_objects.messages import Messages
from slack_objects.config import SlackObjectsConfig


class FakeClient:
    """
    Fake Slack client that mimics slack_sdk.WebClient.api_call(method, json=payload).
    """
    def __init__(self):
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    def api_call(self, method: str, json: Optional[Dict[str, Any]] = None):
        payload = json or {}
        self.calls.append((method, dict(payload)))

        # conversations.history -> single page
        if method == "conversations.history":
            return {
                "ok": True,
                "messages": [
                    {"ts": "1.0", "text": "hello"},
                    {"ts": "2.0", "text": "world"},
                ],
                "response_metadata": {"next_cursor": ""},
            }

        # conversations.replies -> thread messages (includes parent first)
        if method == "conversations.replies":
            return {
                "ok": True,
                "messages": [
                    {"ts": payload["ts"], "text": "parent"},
                    {"ts": "3.0", "text": "reply 1"},
                ],
                "response_metadata": {"next_cursor": ""},
            }

        # chat.update
        if method == "chat.update":
            return {"ok": True, "channel": payload["channel"], "ts": payload["ts"], "text": payload.get("text", "")}

        # chat.delete
        if method == "chat.delete":
            return {"ok": True, "channel": payload["channel"], "ts": payload["ts"]}

        raise AssertionError(f"Unhandled method in FakeClient: {method}")


class FakeApiCaller:
    """
    Fake SlackApiCaller that directly calls FakeClient.api_call (no sleeping).
    """
    def call(self, client, method: str, *, rate_tier=None, **kwargs):
        return client.api_call(method, json=kwargs)


class MessagesExampleTests(unittest.TestCase):
    def setUp(self):
        self.cfg = SlackObjectsConfig(bot_token="xoxb-test")
        self.client = FakeClient()
        self.api = FakeApiCaller()
        self.msgs = Messages(cfg=self.cfg, client=self.client, logger=None, api=self.api, channel_id="C123")

    def test_get_messages(self):
        out = self.msgs.get_messages(limit=10)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["text"], "hello")
        self.assertEqual(out[1]["text"], "world")

    def test_get_message_threads(self):
        thread = self.msgs.get_message_threads(thread_ts="2.0")
        self.assertEqual(len(thread), 2)
        self.assertEqual(thread[0]["text"], "parent")
        self.assertEqual(thread[1]["text"], "reply 1")

    def test_update_and_delete(self):
        update = self.msgs.update_message(channel_id="C123", ts="2.0", text="updated")
        self.assertTrue(update["ok"])
        self.assertEqual(update["text"], "updated")

        delete = self.msgs.delete_message(channel_id="C123", ts="2.0")
        self.assertTrue(delete["ok"])

    def test_replace_message_block(self):
        # Cache a fake message with blocks
        msg = Messages(
            cfg=self.cfg,
            client=self.client,
            logger=None,
            api=self.api,
            channel_id="C123",
            ts="2.0",
            message={
                "blocks": [
                    {"type": "section", "block_id": "A", "text": {"type": "mrkdwn", "text": "old"}},
                    {"type": "divider", "block_id": "B"},
                ]
            },
        )

        resp = msg.replace_message_block(block_id="A", text="new text")
        self.assertTrue(resp["ok"])

        # Ensure chat.update was called
        called_methods = [m for (m, _) in self.client.calls]
        self.assertIn("chat.update", called_methods)


if __name__ == "__main__":
    unittest.main()
