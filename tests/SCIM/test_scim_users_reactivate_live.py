"""
Live integration tests for scim_reactivate_user.

These are READ-MOSTLY — reactivating an already-active user is a no-op.
The one truly mutating test (reactivating a deactivated user) has teardown
that re-deactivates to restore original state.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import pytest
import requests
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCIM_PAUSE = 4.0


def _pause():
    time.sleep(_SCIM_PAUSE)


def _resolve_user_id_from_email(users: Users, email: str) -> str:
    resp = users.lookup_by_email(email)
    assert resp.get("ok"), f"lookup_by_email({email}) failed: {resp}"
    return resp["user"]["id"]


def _get_display_name(users: Users, user_id: str) -> str:
    resp = users.get_user_info(user_id)
    assert resp.get("ok"), f"get_user_info({user_id}) failed: {resp}"
    profile = resp["user"].get("profile", {})
    return profile.get("display_name") or resp["user"].get("real_name", "")


def _scim_get_user(users: Users, user_id: str) -> Dict[str, Any]:
    resp = users._scim_request(path=f"Users/{user_id}", method="GET")
    assert resp.ok, f"SCIM GET Users/{user_id} failed: {resp.data}"
    return resp.data


def _is_active_via_scim(users: Users, user_id: str) -> bool:
    data = _scim_get_user(users, user_id)
    return bool(data.get("active", False))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScimReactivateUser:
    """scim_reactivate_user — exhaustive identifier × state × type matrix."""

    # ----- by user_id -----

    def test_reactivate_active_member_by_id(self, ctx, users):
        """Reactivating an already-active member should succeed (no-op)."""
        resp = users.scim_reactivate_user(ctx.active_member_id)
        assert resp.ok, f"Expected ok for active member: {resp.data}"
        _pause()

    def test_reactivate_active_admin_by_id(self, ctx, users):
        """Reactivating an already-active admin should succeed (no-op)."""
        resp = users.scim_reactivate_user(ctx.active_admin_id)
        assert resp.ok, f"Expected ok for active admin: {resp.data}"
        _pause()

    def test_reactivate_active_owner_by_id(self, ctx, users):
        """Reactivating an already-active owner should succeed (no-op)."""
        resp = users.scim_reactivate_user(ctx.active_owner_id)
        assert resp.ok, f"Expected ok for active owner: {resp.data}"
        _pause()

    def test_reactivate_active_scg_by_id(self, ctx, users):
        """Reactivating an already-active single-channel guest should succeed."""
        resp = users.scim_reactivate_user(ctx.single_channel_guest_id)
        assert resp.ok, f"Expected ok for active SCG: {resp.data}"
        _pause()

    def test_reactivate_active_mcg_by_id(self, ctx, users):
        """Reactivating an already-active multi-channel guest should succeed."""
        resp = users.scim_reactivate_user(ctx.multi_channel_guest_id)
        assert resp.ok, f"Expected ok for active MCG: {resp.data}"
        _pause()

    def test_reactivate_deactivated_user_by_id(self, ctx, users):
        """
        Reactivating a deactivated user should succeed.

        WARNING: This WILL reactivate the user in your org. The teardown
        re-deactivates to restore original state.
        """
        resp = users.scim_reactivate_user(ctx.deactivated_user_id)
        assert resp.ok, f"Expected ok for deactivated user: {resp.data}"
        _pause()

        assert _is_active_via_scim(users, ctx.deactivated_user_id), "User should be active after reactivation"
        _pause()

        # Teardown: re-deactivate to restore original state
        users.scim_deactivate_user(ctx.deactivated_user_id)
        _pause()

    def test_reactivate_nonexistent_user_by_id(self, ctx, users):
        """Reactivating a non-existent user ID should fail (404 or error)."""
        with pytest.raises((requests.HTTPError, RuntimeError, Exception)):
            users.scim_reactivate_user(ctx.nonexistent_user_id)
        _pause()

    # ----- by email (resolved to user_id) -----

    def test_reactivate_active_member_by_email(self, ctx, users):
        """Resolve email → id, then reactivate an already-active member."""
        uid = _resolve_user_id_from_email(users, ctx.active_member_email)
        resp = users.scim_reactivate_user(uid)
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

    def test_reactivate_deactivated_user_by_email(self, ctx, users):
        """Resolve email → id for a deactivated user, then reactivate + teardown."""
        try:
            uid = _resolve_user_id_from_email(users, ctx.deactivated_user_email)
        except (AssertionError, SlackApiError):
            uid = ctx.deactivated_user_id

        resp = users.scim_reactivate_user(uid)
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        # Teardown
        users.scim_deactivate_user(uid)
        _pause()

    def test_reactivate_nonexistent_email(self, ctx, users):
        """Resolving a non-existent email should fail before we even call SCIM."""
        with patch.object(users, "_scim_request", wraps=users._scim_request) as spy:
            with pytest.raises(SlackApiError, match="users_not_found"):
                users.lookup_by_email(ctx.nonexistent_email)
            spy.assert_not_called()
        _pause()

    # ----- by display_name (resolved to user_id) -----

    def test_reactivate_active_member_by_display_name(self, ctx, users):
        """Resolve @display_name → id, then reactivate."""
        display = _get_display_name(users, ctx.active_member_id)
        _pause()
        resp = users.scim_reactivate_user(ctx.active_member_id)
        assert resp.ok, f"Expected ok (via display_name path) for '{display}': {resp.data}"
        _pause()

    # ----- bound user_id (no argument) -----

    def test_reactivate_bound_active_member(self, ctx):
        """Calling scim_reactivate_user() with no args on a bound Users instance."""
        bound = ctx.slack.users(ctx.active_member_id)
        resp = bound.scim_reactivate_user()
        assert resp.ok, f"Expected ok for bound user: {resp.data}"
        _pause()

    def test_reactivate_bound_no_user_id_raises(self, users):
        """Calling scim_reactivate_user() with no user_id and unbound should raise ValueError."""
        with pytest.raises(ValueError, match="requires user_id"):
            users.scim_reactivate_user()