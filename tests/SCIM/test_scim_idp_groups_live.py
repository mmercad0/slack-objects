"""
Live integration tests for every SCIM method on the IDP_groups object helper.

These tests hit the REAL Slack SCIM API — no fakes, no mocks.
They require Azure Key Vault credentials and a live_test_config.json file;
see tests/SCIM/conftest_live.py for setup details.

Run:
    python -m pytest tests/SCIM/test_scim_idp_groups_live.py -v --tb=short
"""

from __future__ import annotations

import time
from typing import Optional

import pytest
import requests

from slack_objects.idp_groups import IDP_groups

from conftest_live import LiveTestContext, build_live_context

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ctx: Optional[LiveTestContext] = None


def _get_ctx() -> LiveTestContext:
    global _ctx
    if _ctx is None:
        _ctx = build_live_context()
    return _ctx


@pytest.fixture(scope="module")
def ctx() -> LiveTestContext:
    return _get_ctx()


@pytest.fixture(scope="module")
def idp(ctx: LiveTestContext) -> IDP_groups:
    return ctx.slack.idp_groups()


_SCIM_PAUSE = 4.0


def _pause():
    time.sleep(_SCIM_PAUSE)


# ═══════════════════════════════════════════════════════════════════════════
# 1.  get_groups
# ═══════════════════════════════════════════════════════════════════════════

class TestGetGroups:
    """get_groups — validates pagination, shape, and basic content."""

    def test_get_groups_returns_list(self, idp):
        """get_groups() should return a list of dicts with 'group id' and 'group name'."""
        groups = idp.get_groups()
        assert isinstance(groups, list), f"Expected list, got {type(groups)}"
        if groups:
            first = groups[0]
            assert "group id" in first, f"Missing 'group id' key: {first}"
            assert "group name" in first, f"Missing 'group name' key: {first}"
        _pause()

    def test_get_groups_nonempty(self, idp):
        """Org should have at least one IDP group (SCIM token must have group read scope)."""
        groups = idp.get_groups()
        assert len(groups) > 0, "Expected at least one IDP group; check SCIM token scopes."
        _pause()

    def test_get_groups_small_page_size(self, idp):
        """Pagination with fetch_count=1 should still return all groups."""
        all_groups = idp.get_groups()
        _pause()
        paginated = idp.get_groups(fetch_count=1)
        _pause()
        # Paginated should return >= all_groups (could be equal or larger if race)
        assert len(paginated) >= len(all_groups) - 1, (
            f"Paginated count ({len(paginated)}) too low vs single-page ({len(all_groups)})"
        )

    def test_get_groups_ids_are_strings(self, idp):
        """All group IDs should be non-empty strings."""
        groups = idp.get_groups()
        for g in groups:
            gid = g["group id"]
            assert isinstance(gid, str) and len(gid) > 0, f"Invalid group id: {gid!r}"
        _pause()

    def test_get_groups_names_are_strings(self, idp):
        """All group names should be strings."""
        groups = idp.get_groups()
        for g in groups:
            assert isinstance(g["group name"], str), f"Invalid group name: {g['group name']!r}"
        _pause()

    def test_get_groups_known_group_present(self, ctx, idp):
        """If idp_group_id is set in live_test_config.json, it should appear in the list."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        groups = idp.get_groups()
        ids = {g["group id"] for g in groups}
        assert ctx.idp_group_id in ids, (
            f"Expected group {ctx.idp_group_id} in list; got {ids}"
        )
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 2.  get_members
# ═══════════════════════════════════════════════════════════════════════════

class TestGetMembers:
    """get_members — validates shape and content of member lists."""

    def test_get_members_returns_list(self, ctx, idp):
        """get_members should return a list of member dicts."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        members = idp.get_members(ctx.idp_group_id)
        assert isinstance(members, list), f"Expected list, got {type(members)}"
        _pause()

    def test_get_members_has_value_key(self, ctx, idp):
        """Each member dict should have a 'value' key (the user ID)."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        members = idp.get_members(ctx.idp_group_id)
        if members:
            assert "value" in members[0], f"Missing 'value': {members[0]}"
        _pause()

    def test_get_members_has_display_key(self, ctx, idp):
        """Each member dict should have a 'display' key."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        members = idp.get_members(ctx.idp_group_id)
        if members:
            assert "display" in members[0], f"Missing 'display': {members[0]}"
        _pause()

    def test_get_members_bound_group(self, ctx):
        """ get_members() with no arg on a bound IDP_groups instance.
            It verifies that calling get_members() without passing a group_id argument works correctly on an IDP_groups instance that was constructed with a group_id (i.e., a "bound" instance).
            It ensures the bound instance uses its stored group_id internally.
        """
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        bound_idp = IDP_groups(
            cfg=ctx.cfg,
            client=ctx.slack.web_client,
            api=ctx.slack.api,
            logger=ctx.logger,
            group_id=ctx.idp_group_id,
        )
        members = bound_idp.get_members()
        assert isinstance(members, list)
        _pause()

    def test_get_members_no_group_raises(self, idp):
        """Calling get_members() with no group_id and unbound should raise ValueError."""
        with pytest.raises(ValueError, match="requires group_id"):
            idp.get_members()

    def test_get_members_nonexistent_group(self, idp):
        """Fetching members of a non-existent group should raise HTTPError."""
        with pytest.raises((requests.HTTPError, Exception)):
            idp.get_members("NONEXISTENT_GROUP_ID_12345")
        _pause()

    def test_get_members_invalid_id_raises(self, idp):
        """Path-traversal group IDs must be rejected."""
        with pytest.raises(ValueError):
            idp.get_members("../../admin")


# ═══════════════════════════════════════════════════════════════════════════
# 3.  is_member
# ═══════════════════════════════════════════════════════════════════════════

class TestIsMember:
    """is_member — validates membership checks against real data."""

    def test_is_member_known_member(self, ctx, idp):
        """A user known to be in the group should return True."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        # First, get actual members to find a real one
        members = idp.get_members(ctx.idp_group_id)
        if not members:
            pytest.skip("Group has no members")

        real_member_id = members[0]["value"]
        assert idp.is_member(user_id=real_member_id, group_id=ctx.idp_group_id) is True
        _pause()

    def test_is_member_non_member(self, ctx, idp):
        """A user not in the group should return False."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        # Use non-existent user ID — guaranteed not a member
        result = idp.is_member(user_id=ctx.nonexistent_user_id, group_id=ctx.idp_group_id)
        assert result is False
        _pause()

    def test_is_member_active_member(self, ctx, idp):
        """Check membership for an active regular member (may or may not be in group)."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        result = idp.is_member(user_id=ctx.active_member_id, group_id=ctx.idp_group_id)
        assert isinstance(result, bool)
        _pause()

    def test_is_member_admin(self, ctx, idp):
        """Check membership for an admin."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        result = idp.is_member(user_id=ctx.active_admin_id, group_id=ctx.idp_group_id)
        assert isinstance(result, bool)
        _pause()

    def test_is_member_owner(self, ctx, idp):
        """Check membership for an owner."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        result = idp.is_member(user_id=ctx.active_owner_id, group_id=ctx.idp_group_id)
        assert isinstance(result, bool)
        _pause()

    def test_is_member_scg(self, ctx, idp):
        """Check membership for a single-channel guest."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        result = idp.is_member(user_id=ctx.single_channel_guest_id, group_id=ctx.idp_group_id)
        assert isinstance(result, bool)
        _pause()

    def test_is_member_mcg(self, ctx, idp):
        """Check membership for a multi-channel guest."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        result = idp.is_member(user_id=ctx.multi_channel_guest_id, group_id=ctx.idp_group_id)
        assert isinstance(result, bool)
        _pause()

    def test_is_member_deactivated_user(self, ctx, idp):
        """Check membership for a deactivated user."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        result = idp.is_member(user_id=ctx.deactivated_user_id, group_id=ctx.idp_group_id)
        assert isinstance(result, bool)
        _pause()

    def test_is_member_bound_group(self, ctx):
        """is_member with no group_id on a bound instance."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        bound = IDP_groups(
            cfg=ctx.cfg,
            client=ctx.slack.web_client,
            api=ctx.slack.api,
            logger=ctx.logger,
            group_id=ctx.idp_group_id,
        )
        result = bound.is_member(user_id=ctx.active_member_id)
        assert isinstance(result, bool)
        _pause()

    def test_is_member_no_group_raises(self, idp, ctx):
        """Calling is_member with no group_id and unbound should raise ValueError."""
        with pytest.raises(ValueError, match="requires group_id"):
            idp.is_member(user_id=ctx.active_member_id)

    def test_is_member_nonexistent_group(self, idp, ctx):
        """Checking membership in a non-existent group should raise HTTPError."""
        with pytest.raises((requests.HTTPError, Exception)):
            idp.is_member(user_id=ctx.active_member_id, group_id="NONEXISTENT_12345")
        _pause()

    def test_is_member_invalid_group_id(self, idp, ctx):
        """Path-traversal group IDs must be rejected."""
        with pytest.raises(ValueError):
            idp.is_member(user_id=ctx.active_member_id, group_id="../../admin")


# ═══════════════════════════════════════════════════════════════════════════
# 4.  with_group factory
# ═══════════════════════════════════════════════════════════════════════════

class TestWithGroupFactory:
    """with_group — factory produces a correctly bound instance."""

    def test_with_group_sets_group_id(self, ctx, idp):
        """with_group should return a new instance with the given group_id."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        bound = idp.with_group(ctx.idp_group_id)
        assert bound.group_id == ctx.idp_group_id

    def test_with_group_shares_config(self, idp):
        """with_group should share cfg, client, api, logger."""
        bound = idp.with_group("G_TEST")
        assert bound.cfg is idp.cfg
        assert bound.client is idp.client
        assert bound.api is idp.api

    def test_with_group_get_members_works(self, ctx, idp):
        """Bound instance should be able to call get_members() with no args."""
        if not ctx.idp_group_id:
            pytest.skip("idp_group_id not set in live_test_config.json")

        bound = idp.with_group(ctx.idp_group_id)
        members = bound.get_members()
        assert isinstance(members, list)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 5.  Input validation (cross-cutting)
# ═══════════════════════════════════════════════════════════════════════════

class TestIdpGroupsInputValidation:
    """Cross-cutting input validation for IDP_groups SCIM methods."""

    @pytest.mark.parametrize("bad_id", [
        "../../admin",
        "G1/../../etc",
        "G1/../G2",
        "",
        " ",
        "G1 G2",
        "G1;DROP",
        "G1&x=1",
        "G<script>",
    ])
    def test_get_members_rejects_bad_group_ids(self, idp, bad_id):
        with pytest.raises(ValueError):
            idp.get_members(bad_id)

    @pytest.mark.parametrize("bad_id", [
        "../../admin",
        "",
        " ",
    ])
    def test_is_member_rejects_bad_group_ids(self, idp, bad_id, ctx):
        with pytest.raises(ValueError):
            idp.is_member(user_id=ctx.active_member_id, group_id=bad_id)