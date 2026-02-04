from __future__ import annotations

import logging

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.workspaces import Workspaces

from tests._smoke_harness import FakeWebClient, FakeApiCaller, CallSpec, run_smoke


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.workspaces")

    cfg = SlackObjectsConfig(bot_token="xoxb-fake", user_token="xoxp-fake", scim_token=None, default_rate_tier=RateTier.TIER_4)
    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    ws = Workspaces(cfg=cfg, client=client, api=api, logger=logger)
    bound = ws.with_workspace("T1")

    specs = [
        CallSpec("with_workspace()", lambda: ws.with_workspace("T1")),
        CallSpec("refresh()", lambda: bound.refresh()),
        CallSpec("get_workspace_info()", lambda: ws.get_workspace_info("T1")),
        CallSpec("list_workspaces()", lambda: ws.list_workspaces(force_refresh=True)),
        CallSpec("get_workspace_name()", lambda: ws.get_workspace_name("T1", force_refresh=True)),
        CallSpec("get_workspace_id()", lambda: ws.get_workspace_id("Workspace One", force_refresh=True)),
        CallSpec("get_workspace_from_name()", lambda: ws.get_workspace_from_name("Workspace One", force_refresh=True)),
        CallSpec("list_users(bound)", lambda: bound.list_users()),
        CallSpec("list_users(by id)", lambda: ws.list_users("T1")),
        CallSpec("list_admin_ids(bound)", lambda: bound.list_admin_ids()),
        CallSpec("list_admin_ids(by id)", lambda: ws.list_admin_ids("T1")),
    ]

    run_smoke("Workspaces smoke (all public methods)", specs)


if __name__ == "__main__":
    main()
