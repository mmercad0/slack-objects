from __future__ import annotations

import logging

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.idp_groups import IDP_groups

from tests._smoke_harness import (
    FakeWebClient,
    FakeApiCaller,
    FakeScimSession,
    CallSpec,
    run_smoke,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.idp_groups")

    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_4,
    )

    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    idp = IDP_groups(
        cfg=cfg,
        client=client,
        api=api,
        logger=logger,
        scim_session=FakeScimSession(),
    )

    bound = IDP_groups(
        cfg=cfg,
        client=client,
        api=api,
        logger=logger,
        group_id="G1",
        scim_session=FakeScimSession(),
    )

    specs = [
        # Factory helper
        CallSpec("with_group()", lambda: idp.with_group("G1")),

        # Group listing (paginated)
        CallSpec("get_groups()", lambda: idp.get_groups()),
        CallSpec("get_groups(fetch_count=1)", lambda: idp.get_groups(fetch_count=1)),

        # Members
        CallSpec("get_members(by arg)", lambda: idp.get_members("G1")),
        CallSpec("get_members(bound)", lambda: bound.get_members()),

        # Membership check
        CallSpec("is_member(hit)", lambda: idp.is_member(user_id="U1", group_id="G1")),
        CallSpec("is_member(miss)", lambda: idp.is_member(user_id="U_UNKNOWN", group_id="G1")),
        CallSpec("is_member(bound)", lambda: bound.is_member(user_id="U2")),
    ]

    run_smoke("IDP_groups smoke (all public methods)", specs)


if __name__ == "__main__":
    main()
