from __future__ import annotations

import logging
import sys
import types
from datetime import datetime, timezone

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.users import Users

from tests.Smoke._smoke_harness import (
    FakeWebClient,
    FakeApiCaller,
    FakeScimSession,
    CallSpec,
    run_smoke,
)


def _install_pc_utils_datetime_stub() -> None:
    """
    Provide a minimal stub for:
        from PC_Utils.Datetime import Datetime

    so tests don't require PC_Utils to be installed.
    """
    pc_utils_mod = types.ModuleType("PC_Utils")
    pc_utils_datetime_mod = types.ModuleType("PC_Utils.Datetime")

    class Datetime:
        @staticmethod
        def date_to_epoch(date_str: str) -> int:
            # Simple YYYY-MM-DD parser; treat as UTC midnight
            dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return int(dt.timestamp())

    pc_utils_datetime_mod.Datetime = Datetime

    sys.modules["PC_Utils"] = pc_utils_mod
    sys.modules["PC_Utils.Datetime"] = pc_utils_datetime_mod


def _force_idp_groups_to_use_fake_scim_session() -> None:
    """
    Ensure any IDP_groups created inside Users.is_user_authorized uses FakeScimSession.
    Patching requests.Session alone can miss because the dataclass default_factory may already
    hold the original callable.
    """
    import slack_objects.idp_groups as idp_mod
    from tests.Smoke._smoke_harness import FakeScimSession

    original_init = idp_mod.IDP_groups.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.scim_session = FakeScimSession()

    idp_mod.IDP_groups.__init__ = patched_init  # type: ignore[assignment]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("smoke.users")

    # Install stubs before importing/calling methods that rely on them
    _install_pc_utils_datetime_stub()
    _force_idp_groups_to_use_fake_scim_session()

    # IMPORTANT: is_user_authorized() usually relies on config mappings.
    # Provide minimal example mappings that point to group IDs returned by FakeScimSession (G1/G2).
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_4,
    )

    # If your Users.is_user_authorized reads these dicts from cfg, add them here:
    # (Adjust attribute names to match your implementation if needed.)
    object.__setattr__(cfg, "auth_idp_groups_read_access", {"example_service": ["G1"]})
    object.__setattr__(cfg, "auth_idp_groups_write_access", {"example_service": ["G2"]})

    client = FakeWebClient()
    api = FakeApiCaller(cfg)

    users = Users(cfg=cfg, client=client, api=api, logger=logger)

    # Use a user_id that appears in FakeScimSession group membership (U1 or U2)
    bound = users.with_user("U1")

    # If Users exposes scim_session, use FakeScimSession too (covers SCIM methods)
    if hasattr(bound, "scim_session"):
        bound.scim_session = FakeScimSession()

    def _refresh_bound():
        bound.refresh()
        return True

    specs = [
        # Factory helpers
        CallSpec("with_user()", lambda: users.with_user("U1")),

        # Attribute lifecycle
        CallSpec("refresh()", lambda: bound.refresh()),
        CallSpec("get_user_info()", lambda: bound.get_user_info("U1")),

        # Lookup helpers
        CallSpec("lookup_by_email(found)", lambda: users.lookup_by_email("found@example.com")),
        CallSpec("get_user_id_from_email(found)", lambda: users.get_user_id_from_email("found@example.com")),
        CallSpec("get_user_id_from_email(miss)", lambda: users.get_user_id_from_email("missing@example.com")),

        # Profile helpers
        CallSpec("get_user_profile(bound)", lambda: bound.get_user_profile()),
        CallSpec("get_user_profile(by id)", lambda: users.get_user_profile("U1")),
        CallSpec("set_user_profile_field(bound)", lambda: bound.set_user_profile_field("status_text", "hello")),
        CallSpec("set_user_profile_field(by id)", lambda: users.set_user_profile_field("status_text", "hello", user_id="U1")),

        # Classification helpers (need attributes)
        CallSpec("is_contingent_worker()", lambda: (_refresh_bound(), bound.is_contingent_worker())),
        CallSpec("is_guest()", lambda: (_refresh_bound(), bound.is_guest())),
        CallSpec("is_active()", lambda: (_refresh_bound(), bound.is_active())),

        # Admin helpers
        CallSpec(
            "invite_user()",
            lambda: bound.invite_user(channel_ids=["C1", "C2"], email="new@example.com", team_id="T1"),
        ),
        CallSpec("wipe_all_sessions()", lambda: bound.wipe_all_sessions()),
        CallSpec("add_to_workspace()", lambda: bound.add_to_workspace("U1", "T1")),
        CallSpec("remove_from_workspace()", lambda: bound.remove_from_workspace("U1", "T1")),
        CallSpec("add_to_conversation()", lambda: bound.add_to_conversation(["U1"], "C1")),
        CallSpec("remove_from_conversation()", lambda: bound.remove_from_conversation("U1", "C1")),

        # Discovery helper
        CallSpec("get_channels(active_only)", lambda: bound.get_channels("U1", active_only=True)),
        CallSpec("get_channels(all)", lambda: bound.get_channels("U1", active_only=False)),

        # Authorization helper
        CallSpec(
            "is_user_authorized(read)",
            lambda: bound.is_user_authorized("example_service", "read"),
        ),
        CallSpec(
            "is_user_authorized(write)",
            lambda: bound.is_user_authorized("example_service", "write"),
        ),

        # Guest expiration - relies on PC_Utils.Datetime stub above
        CallSpec(
            "set_guest_expiration_date()",
            lambda: bound.set_guest_expiration_date("2030-01-01", workspace_id="T1"),
        ),

        # SCIM helpers (scim_version now comes from cfg, not a kwarg)
        CallSpec("scim_create_user()", lambda: bound.scim_create_user("testuser", "test@example.com")),
        CallSpec("scim_deactivate_user()", lambda: bound.scim_deactivate_user("U1")),
        CallSpec("scim_reactivate_user()", lambda: bound.scim_reactivate_user()),
        CallSpec(
            "scim_update_user_attribute()",
            lambda: bound.scim_update_user_attribute(user_id="U1", attribute="active", new_value=False),
        ),
        CallSpec("make_multi_channel_guest()", lambda: bound.make_multi_channel_guest()),

        # SCIM search primitives
        CallSpec("scim_search_user_by_email()", lambda: bound.scim_search_user_by_email("test@example.com")),
        CallSpec("scim_search_user_by_username()", lambda: bound.scim_search_user_by_username("testuser")),

        # Identifier resolution
        CallSpec("resolve_user_id(user_id)", lambda: bound.resolve_user_id("U1")),
    ]

    run_smoke("Users smoke (all public methods)", specs)


if __name__ == "__main__":
    main()
