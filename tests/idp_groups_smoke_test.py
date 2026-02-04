from __future__ import annotations

import logging

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.idp_groups import IDP_groups

from tests._smoke_harness import FakeWebClient, FakeApiCaller, FakeScimSession, CallSpec, run_smoke


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.idp_groups")

    cfg = SlackObjectsConfig(bot_token="xoxb-fake", user_token=None, scim_token="xoxp-fake", default_rate_tier=RateTier.TIER_4)
    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    idp = IDP_groups(cfg=cfg, client=client, api=api, logger=logger)
    idp.scim_session = FakeScimSession()

    bound = idp.with_group("G1")

    specs = [
        CallSpec("with_group()", lambda: idp.with_group("G1")),
        CallSpec("get_groups()", lambda: idp.get_groups(scim_version="v1", fetch_count=1000)),
        CallSpec("get_members(bound)", lambda: bound.get_members(scim_version="v1")),
        CallSpec("get_members(by id)", lambda: idp.get_members(group_id="G1", scim_version="v1")),
        CallSpec("is_member(True)", lambda: idp.is_member(user_id="U1", group_id="G1", scim_version="v1")),
        CallSpec("is_member(False)", lambda: idp.is_member(user_id="U_NOPE", group_id="G1", scim_version="v1")),
    ]

    run_smoke("IDP_groups smoke (all public methods)", specs)


if __name__ == "__main__":
    main()
