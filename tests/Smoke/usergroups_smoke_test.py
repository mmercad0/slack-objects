from __future__ import annotations

import logging

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.usergroups import Usergroups

from tests.Smoke._smoke_harness import (
    FakeWebClient,
    FakeApiCaller,
    CallSpec,
    run_smoke,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.usergroups")

    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        default_rate_tier=RateTier.TIER_4,
    )

    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    ug = Usergroups(
        cfg=cfg,
        client=client,
        api=api,
        logger=logger,
    )

    bound = ug.with_usergroup("S0614TZR7")

    specs = [
        # Factory helper
        CallSpec("with_usergroup()", lambda: ug.with_usergroup("S0614TZR7")),

        # Listing
        CallSpec("get_usergroups()", lambda: ug.get_usergroups()),

        # Members
        CallSpec("get_members(by arg)", lambda: ug.get_members("S0614TZR7")),
        CallSpec("get_members(bound)", lambda: bound.get_members()),

        # Membership check
        CallSpec("is_member(hit)", lambda: ug.is_member(user_id="U1", usergroup_id="S0614TZR7")),
        CallSpec("is_member(miss)", lambda: ug.is_member(user_id="U_UNKNOWN", usergroup_id="S0614TZR7")),
        CallSpec("is_member(bound)", lambda: bound.is_member(user_id="U2")),
    ]

    run_smoke("Usergroups smoke (all public methods)", specs)


if __name__ == "__main__":
    main()