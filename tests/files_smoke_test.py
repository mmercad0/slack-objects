from __future__ import annotations

import logging

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.files import Files
from slack_objects.conversations import Conversations

from tests._smoke_harness import FakeWebClient, FakeApiCaller, FakeHttpSession, CallSpec, run_smoke


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.files")

    # bot_token is required for url_private download in Files.get_text_content()
    cfg = SlackObjectsConfig(bot_token="xoxb-fake", user_token=None, scim_token=None, default_rate_tier=RateTier.TIER_4)
    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    f = Files(cfg=cfg, client=client, api=api, logger=logger)
    f.http_session = FakeHttpSession()

    bound = f.with_file("F_TEST")

    # A real Conversations instance works here because it delegates to Messages (which uses our fake client/api)
    conv = Conversations(cfg=cfg, client=client, api=api, logger=logger).with_conversation("C1")

    def _prep_refresh_and_content():
        bound.refresh(get_content=False)
        return True

    specs = [
        CallSpec("with_file()", lambda: f.with_file("F_TEST")),
        CallSpec("refresh()", lambda: bound.refresh(get_content=False)),
        CallSpec("get_file_info()", lambda: bound.get_file_info("F_TEST")),
        CallSpec("list_files()", lambda: bound.list_files(count=10)),
        CallSpec("delete_file()", lambda: bound.delete_file()),
        CallSpec(
            "upload_to_slack() (uses explicit content)",
            lambda: bound.upload_to_slack(title="t", channel="C1", filename="a.txt", content="hello"),
        ),
        CallSpec(
            "get_text_content() (requires url_private + bot_token)",
            lambda: (_prep_refresh_and_content(), bound.get_text_content()),
        ),
        CallSpec(
            "get_file_source_message()",
            lambda: (bound.refresh(), bound.get_file_source_message(conversation=conv, file_id="F_TEST", user_id="U_FILE_OWNER", limit=5)),
        ),
    ]

    run_smoke("Files smoke (all public methods)", specs)


if __name__ == "__main__":
    main()
