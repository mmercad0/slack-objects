from __future__ import annotations

import logging

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.conversations import Conversations

from tests.Smoke._smoke_harness import FakeWebClient, FakeApiCaller, CallSpec, run_smoke


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.conversations")

    cfg = SlackObjectsConfig(bot_token="xoxb-fake", user_token="xoxp-fake", scim_token=None, default_rate_tier=RateTier.TIER_4)
    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    convos = Conversations(cfg=cfg, client=client, api=api, logger=logger)
    bound = convos.with_conversation("C1")

    specs = [
        CallSpec("with_conversation()", lambda: convos.with_conversation("C1")),
        CallSpec("refresh()", lambda: bound.refresh()),
        CallSpec("get_conversation_info()", lambda: bound.get_conversation_info("C1")),
        CallSpec("is_private()", lambda: (bound.refresh(), bound.is_private())),
        CallSpec("get_conversation_name(bound)", lambda: (bound.refresh(), bound.get_conversation_name())),
        CallSpec("get_conversation_name(by id)", lambda: bound.get_conversation_name(channel_id="C1")),
        CallSpec(
            "get_conversation_ids_from_name()",
            lambda: bound.get_conversation_ids_from_name("general", workspace_id="T1"),
        ),
        CallSpec("archive()", lambda: bound.archive()),
        CallSpec("share_to_workspaces()", lambda: bound.share_to_workspaces("T2", source_ws_id="T1")),
        CallSpec("move_to_workspace()", lambda: bound.move_to_workspace(channel_id="C1", source_ws_id="T1", target_ws_id="T2")),
        CallSpec(
            "restrict_access_add_group()",
            lambda: bound.restrict_access_add_group(channel_id="C1", group_id="G1", workspace_id="T1"),
        ),
        CallSpec("get_members()", lambda: bound.get_members(workspace_id="T1", include_members_who_left=True)),
        CallSpec("messages() helper", lambda: bound.messages()),
        CallSpec("get_messages() delegates to Messages", lambda: bound.get_messages(limit=2)),
        CallSpec("get_message_threads() delegates to Messages", lambda: bound.get_message_threads(thread_ts="1700000000.000100", limit=10)),
    ]

    run_smoke("Conversations smoke (all public methods)", specs)


if __name__ == "__main__":
    main()
