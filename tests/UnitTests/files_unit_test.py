import logging
from typing import Any, Dict, Optional

from slack_objects.client import SlackObjectsClient
from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.api_caller import SlackApiCaller


class FakeWebClient:
    """
    Fake Slack client implementing api_call(method, json=payload).
    """

    def api_call(self, method: str, json: Optional[Dict[str, Any]] = None):
        payload = json or {}

        if method == "files.info":
            # Minimal response structure matching Slack:
            return {
                "ok": True,
                "file": {
                    "id": payload.get("file", "F_TEST"),
                    "name": "example.txt",
                    "mimetype": "text/plain",
                    "pretty_type": "text",
                    "url_private": "https://files.slack.com/files-pri/T123-F123/example.txt",
                    "user": "U_UPLOADER",
                },
                "response_metadata": {"next_cursor": ""},
            }

        if method == "files.delete":
            return {"ok": True}

        if method == "files.list":
            return {"ok": True, "files": [{"id": "F1"}, {"id": "F2"}]}

        if method == "files.uploadV2":
            return {"ok": True, "file": {"id": "F_UPLOADED"}}

        return {"ok": True}


class FakeApiCaller(SlackApiCaller):
    def __init__(self, cfg):
        self.cfg = cfg
        self.policy = None

    def call(self, client, method: str, *, rate_tier=None, **kwargs):
        # No sleeps/retries for tests
        return client.api_call(method, json=kwargs)


class FakeConversation:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id

    def get_messages(self, channel_id: str, limit: int = 5):
        # Return a small set of messages, one contains the file
        return [
            {"ts": "1", "user": "U_OTHER", "text": "hello"},
            {"ts": "2", "user": "U_UPLOADER", "text": "uploaded", "files": [{"id": "F123"}]},
        ]


class FakeResponse:
    def __init__(self, ok: bool = True, status_code: int = 200, content: bytes = b"hello\n"):
        self.ok = ok
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", errors="ignore")


class FakeSession:
    def get(self, url: str, headers: Dict[str, str], timeout: int):
        return FakeResponse(ok=True, status_code=200, content=b"col1,col2\n1,2\n")


def test_files_factory_and_refresh_and_content_download():
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_3,
    )

    slack = SlackObjectsClient(cfg, logger=logging.getLogger("test"))
    slack.web_client = FakeWebClient()
    slack.api = FakeApiCaller(cfg)
    slack._files = None  # force rebuild with fakes

    files = slack.files()
    assert files.file_id is None

    f = slack.files("F123")
    f.http_session = FakeSession()  # inject fake downloader

    attrs = f.refresh(get_content=False)
    assert attrs["id"] == "F123"

    text = f.get_text_content()
    assert "col1,col2" in text


def test_files_source_message_lookup():
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_3,
    )

    slack = SlackObjectsClient(cfg, logger=logging.getLogger("test"))
    slack.web_client = FakeWebClient()
    slack.api = FakeApiCaller(cfg)
    slack._files = None

    f = slack.files("F123")
    f.refresh()

    convo = FakeConversation(channel_id="C123")
    msg = f.get_file_source_message(conversation=convo, limit=5)
    assert msg is not None
    assert msg["ts"] == "2"
