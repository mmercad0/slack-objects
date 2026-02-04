from __future__ import annotations

import logging

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.messages import Messages

from tests._smoke_harness import FakeWebClient, FakeApiCaller, CallSpec, run_smoke


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.messages")

    cfg = SlackObjectsConfig(bot_token="xoxb-fake", user_token=None, scim_token=None, default_rate_tier=RateTier.TIER_4)
    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    msgs = Messages(cfg=cfg, client=client, api=api, logger=logger)

    # Bound instances for convenience
    msgs_c = msgs.with_channel("C1")
    msgs_m = msgs.with_message("C1", "1700000000.000100", message={"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]})

    specs = [
        CallSpec("with_channel()", lambda: msgs.with_channel("C1")),
        CallSpec("with_message()", lambda: msgs.with_message("C1", "1700000000.000100")),
        CallSpec("update_message()", lambda: msgs_m.update_message(text="updated")),
        CallSpec("delete_message()", lambda: msgs_m.delete_message()),
        CallSpec("get_messages()", lambda: msgs_c.get_messages(limit=2)),
        CallSpec("get_message_threads()", lambda: msgs_c.get_message_threads(thread_ts="1700000000.000100", limit=10)),
        CallSpec(
            "replace_message_block() by type",
            lambda: msgs_m.replace_message_block(block_type="section", text="replacement"),
        ),
    ]

    run_smoke("Messages smoke (all public methods)", specs)


if __name__ == "__main__":
    main()
