"""
Live integration tests for read-only Users Web API methods.

Covers: get_user_info, lookup_by_email, get_user_id_from_email,
        get_user_profile, get_channels, refresh, with_user.

These are READ-ONLY — no user state is modified.

Run:
    python -m pytest tests/Users/test_users_read_live.py -v --tb=short
"""

from __future__ import annotations

import time
from typing import Optional

import pytest
from slack_sdk.errors import SlackApiError

from slack_objects.users import Users

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
def users(ctx: LiveTestContext) -> Users:
    return ctx.slack.users()


_API_PAUSE = 2.0


def _pause():
    time.sleep(_API_PAUSE)


# ═══════════════════════════════════════════════════════════════════════════
# 1.  get_user_info
# ═══════════════════════════════════════════════════════════════════════════

class TestGetUserInfo:
    """get_user_info — validates shape and response for every user type/state."""

    def test_active_member(self, ctx, users):
        """Active member returns ok with correct id."""
        resp = users.get_user_info(ctx.active_member_id)
        assert resp["ok"] is True
        assert resp["user"]["id"] == ctx.active_member_id
        _pause()

    def test_active_admin(self, ctx, users):
        """Active admin returns ok with is_admin=True."""
        resp = users.get_user_info(ctx.active_admin_id)
        assert resp["ok"] is True
        assert resp["user"]["id"] == ctx.active_admin_id
        assert resp["user"].get("is_admin") is True
        _pause()

    def test_active_owner(self, ctx, users):
        """Active owner returns ok with is_owner=True."""
        resp = users.get_user_info(ctx.active_owner_id)
        assert resp["ok"] is True
        assert resp["user"]["id"] == ctx.active_owner_id
        assert resp["user"].get("is_owner") is True
        _pause()

    def test_single_channel_guest(self, ctx, users):
        """SCG returns ok with is_ultra_restricted=True."""
        resp = users.get_user_info(ctx.single_channel_guest_id)
        assert resp["ok"] is True
        assert resp["user"]["id"] == ctx.single_channel_guest_id
        assert resp["user"].get("is_ultra_restricted") is True
        _pause()

    def test_multi_channel_guest(self, ctx, users):
        """MCG returns ok with is_restricted=True."""
        resp = users.get_user_info(ctx.multi_channel_guest_id)
        assert resp["ok"] is True
        assert resp["user"]["id"] == ctx.multi_channel_guest_id
        assert resp["user"].get("is_restricted") is True
        _pause()

    def test_deactivated_user(self, ctx, users):
        """Deactivated user returns ok with deleted=True."""
        resp = users.get_user_info(ctx.deactivated_user_id)
        assert resp["ok"] is True
        assert resp["user"]["id"] == ctx.deactivated_user_id
        assert resp["user"].get("deleted") is True
        _pause()

    def test_nonexistent_user(self, ctx, users):
        """Non-existent user should raise SlackApiError (user_not_found)."""
        with pytest.raises(SlackApiError, match="user_not_found"):
            users.get_user_info(ctx.nonexistent_user_id)
        _pause()

    def test_response_has_profile_dict(self, ctx, users):
        """Response should include a nested profile dict."""
        resp = users.get_user_info(ctx.active_member_id)
        assert isinstance(resp["user"].get("profile"), dict)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 2.  lookup_by_email
# ═══════════════════════════════════════════════════════════════════════════

class TestLookupByEmail:
    """lookup_by_email — email-to-user resolution across types/states."""

    def test_active_member_email(self, ctx, users):
        """Active member email resolves to correct user id."""
        resp = users.lookup_by_email(ctx.active_member_email)
        assert resp["ok"] is True
        assert resp["user"]["id"] == ctx.active_member_id
        _pause()

    def test_active_member_response_has_profile(self, ctx, users):
        """Successful lookup includes profile data."""
        resp = users.lookup_by_email(ctx.active_member_email)
        assert "profile" in resp.get("user", {})
        _pause()

    def test_deactivated_email(self, ctx, users):
        """Deactivated user email should raise SlackApiError (users_not_found)."""
        with pytest.raises(SlackApiError, match="users_not_found"):
            users.lookup_by_email(ctx.deactivated_user_email)
        _pause()

    def test_nonexistent_email(self, ctx, users):
        """Non-existent email should raise SlackApiError (users_not_found)."""
        with pytest.raises(SlackApiError, match="users_not_found"):
            users.lookup_by_email(ctx.nonexistent_email)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 3.  get_user_id_from_email
# ═══════════════════════════════════════════════════════════════════════════

class TestGetUserIdFromEmail:
    """get_user_id_from_email — convenience wrapper, all user types/states."""

    def test_active_member_returns_id(self, ctx, users):
        """Active member email returns matching user ID."""
        uid = users.get_user_id_from_email(ctx.active_member_email)
        assert uid == ctx.active_member_id
        _pause()

    def test_active_member_return_type(self, ctx, users):
        """Return type is always str."""
        uid = users.get_user_id_from_email(ctx.active_member_email)
        assert isinstance(uid, str)
        assert len(uid) > 0
        _pause()

    def test_deactivated_email_returns_empty(self, ctx, users):
        """Deactivated email returns empty string (legacy compat)."""
        uid = users.get_user_id_from_email(ctx.deactivated_user_email)
        assert uid == ""
        _pause()

    def test_nonexistent_email_returns_empty(self, ctx, users):
        """Non-existent email returns empty string (legacy compat)."""
        uid = users.get_user_id_from_email(ctx.nonexistent_email)
        assert uid == ""
        _pause()

    def test_nonexistent_return_type(self, ctx, users):
        """Return type is str even on miss."""
        uid = users.get_user_id_from_email(ctx.nonexistent_email)
        assert isinstance(uid, str)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 4.  get_user_profile
# ═══════════════════════════════════════════════════════════════════════════

class TestGetUserProfile:
    """get_user_profile — profile retrieval for every user type/state."""

    def test_active_member(self, ctx, users):
        """Profile of active member returns ok with profile dict."""
        resp = users.get_user_profile(ctx.active_member_id)
        assert resp["ok"] is True
        assert "profile" in resp
        _pause()

    def test_active_admin(self, ctx, users):
        """Profile of admin returns ok."""
        resp = users.get_user_profile(ctx.active_admin_id)
        assert resp["ok"] is True
        _pause()

    def test_active_owner(self, ctx, users):
        """Profile of owner returns ok."""
        resp = users.get_user_profile(ctx.active_owner_id)
        assert resp["ok"] is True
        _pause()

    def test_single_channel_guest(self, ctx, users):
        """Profile of SCG returns ok."""
        resp = users.get_user_profile(ctx.single_channel_guest_id)
        assert resp["ok"] is True
        _pause()

    def test_multi_channel_guest(self, ctx, users):
        """Profile of MCG returns ok."""
        resp = users.get_user_profile(ctx.multi_channel_guest_id)
        assert resp["ok"] is True
        _pause()

    def test_deactivated_user(self, ctx, users):
        """Profile of deactivated user should still return ok."""
        resp = users.get_user_profile(ctx.deactivated_user_id)
        assert resp["ok"] is True
        _pause()

    def test_nonexistent_user(self, ctx, users):
        """Profile of non-existent user should raise SlackApiError."""
        with pytest.raises(SlackApiError, match="user_not_found"):
            users.get_user_profile(ctx.nonexistent_user_id)
        _pause()

    def test_no_user_id_raises(self, users):
        """Unbound instance with no arg should raise ValueError."""
        with pytest.raises(ValueError, match="requires user_id"):
            users.get_user_profile()

    def test_bound_instance(self, ctx):
        """Bound instance should work without passing user_id."""
        bound = _get_ctx().slack.users(ctx.active_member_id)
        resp = bound.get_user_profile()
        assert resp["ok"] is True
        _pause()

    def test_profile_has_email(self, ctx, users):
        """Active user profile should contain email field."""
        resp = users.get_user_profile(ctx.active_member_id)
        profile = resp.get("profile", {})
        assert "email" in profile, f"Missing 'email' in profile keys: {list(profile.keys())}"
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 5.  get_channels (discovery.user.conversations)
# ═══════════════════════════════════════════════════════════════════════════

class TestGetChannels:
    """get_channels — channel listing for different user types."""

    def test_active_member(self, ctx, users):
        """Active member should return a list."""
        result = users.get_channels(ctx.active_member_id)
        assert isinstance(result, list)
        _pause()

    def test_active_admin(self, ctx, users):
        """Admin should return a list."""
        result = users.get_channels(ctx.active_admin_id)
        assert isinstance(result, list)
        _pause()

    def test_active_owner(self, ctx, users):
        """Owner should return a list."""
        result = users.get_channels(ctx.active_owner_id)
        assert isinstance(result, list)
        _pause()

    def test_single_channel_guest(self, ctx, users):
        """SCG should return a list (likely one channel)."""
        result = users.get_channels(ctx.single_channel_guest_id)
        assert isinstance(result, list)
        _pause()

    def test_multi_channel_guest(self, ctx, users):
        """MCG should return a list."""
        result = users.get_channels(ctx.multi_channel_guest_id)
        assert isinstance(result, list)
        _pause()

    def test_deactivated_user(self, ctx, users):
        """Deactivated user should return a list (may be empty or contain errors)."""
        result = users.get_channels(ctx.deactivated_user_id)
        assert isinstance(result, list)
        _pause()

    def test_nonexistent_user(self, ctx, users):
        """Non-existent user should return an error list (legacy behavior)."""
        result = users.get_channels(ctx.nonexistent_user_id)
        assert isinstance(result, list)
        _pause()

    def test_active_only_true_subset_of_all(self, ctx, users):
        """active_only=True should return ≤ active_only=False."""
        active = users.get_channels(ctx.active_member_id, active_only=True)
        _pause()
        all_ch = users.get_channels(ctx.active_member_id, active_only=False)
        _pause()
        assert len(active) <= len(all_ch), (
            f"active_only ({len(active)}) should be ≤ all ({len(all_ch)})"
        )

    def test_active_only_false_returns_list(self, ctx, users):
        """active_only=False should still return a list."""
        result = users.get_channels(ctx.active_member_id, active_only=False)
        assert isinstance(result, list)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 6.  refresh
# ═══════════════════════════════════════════════════════════════════════════

class TestRefresh:
    """refresh — attribute loading lifecycle for every user type/state."""

    def test_active_member(self, ctx):
        """Refreshing active member populates attributes with correct id."""
        bound = _get_ctx().slack.users(ctx.active_member_id)
        attrs = bound.refresh()
        assert isinstance(attrs, dict)
        assert attrs["id"] == ctx.active_member_id
        _pause()

    def test_active_admin(self, ctx):
        """Refreshing admin sets is_admin=True."""
        bound = _get_ctx().slack.users(ctx.active_admin_id)
        attrs = bound.refresh()
        assert attrs.get("is_admin") is True
        _pause()

    def test_active_owner(self, ctx):
        """Refreshing owner sets is_owner=True."""
        bound = _get_ctx().slack.users(ctx.active_owner_id)
        attrs = bound.refresh()
        assert attrs.get("is_owner") is True
        _pause()

    def test_single_channel_guest(self, ctx):
        """Refreshing SCG sets is_ultra_restricted=True."""
        bound = _get_ctx().slack.users(ctx.single_channel_guest_id)
        attrs = bound.refresh()
        assert attrs.get("is_ultra_restricted") is True
        _pause()

    def test_multi_channel_guest(self, ctx):
        """Refreshing MCG sets is_restricted=True."""
        bound = _get_ctx().slack.users(ctx.multi_channel_guest_id)
        attrs = bound.refresh()
        assert attrs.get("is_restricted") is True
        _pause()

    def test_deactivated_user(self, ctx):
        """Refreshing deactivated user sets deleted=True."""
        bound = _get_ctx().slack.users(ctx.deactivated_user_id)
        attrs = bound.refresh()
        assert attrs.get("deleted") is True
        _pause()

    def test_nonexistent_user_raises(self, ctx):
        """Refreshing non-existent user raises RuntimeError."""
        bound = _get_ctx().slack.users(ctx.nonexistent_user_id)
        with pytest.raises((RuntimeError, SlackApiError)):
            bound.refresh()
        _pause()

    def test_no_user_id_raises(self):
        """Calling refresh() with no user_id raises ValueError."""
        unbound = _get_ctx().slack.users()
        with pytest.raises(ValueError, match="requires user_id"):
            unbound.refresh()

    def test_explicit_user_id_override(self, ctx):
        """Passing user_id to refresh overrides and populates attributes."""
        unbound = _get_ctx().slack.users()
        attrs = unbound.refresh(user_id=ctx.active_member_id)
        assert attrs["id"] == ctx.active_member_id
        _pause()

    def test_stores_attributes(self, ctx):
        """After refresh, bound.attributes is populated."""
        bound = _get_ctx().slack.users(ctx.active_member_id)
        bound.refresh()
        assert bound.attributes
        assert bound.attributes["id"] == ctx.active_member_id
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 7.  with_user factory
# ═══════════════════════════════════════════════════════════════════════════

class TestWithUserFactory:
    """with_user — factory produces correctly bound instances."""

    def test_sets_user_id(self, ctx, users):
        """with_user returns a new instance bound to the given user_id."""
        bound = users.with_user(ctx.active_member_id)
        assert bound.user_id == ctx.active_member_id

    def test_shares_config(self, users):
        """with_user shares cfg, client, api, logger."""
        bound = users.with_user("U_TEST")
        assert bound.cfg is users.cfg
        assert bound.client is users.client
        assert bound.api is users.api
        assert bound.logger is users.logger

    def test_shares_scim_session(self, users):
        """with_user shares the scim_session."""
        bound = users.with_user("U_TEST")
        assert bound.scim_session is users.scim_session

    def test_does_not_mutate_original(self, users):
        """Original instance remains unbound after with_user."""
        original_uid = users.user_id
        _ = users.with_user("U_TEST")
        assert users.user_id == original_uid

    def test_bound_can_refresh(self, ctx, users):
        """Bound instance can call refresh successfully."""
        bound = users.with_user(ctx.active_member_id)
        attrs = bound.refresh()
        assert attrs["id"] == ctx.active_member_id
        _pause()