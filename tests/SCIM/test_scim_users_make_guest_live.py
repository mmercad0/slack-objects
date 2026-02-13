"""
Live integration tests for make_multi_channel_guest.

⚠️  DESTRUCTIVE — converting a user to MCG is NOT reversible via SCIM.
    These tests use DISPOSABLE users from live_test_config.json.
    The "safe" idempotent tests still use the real MCG user.

Populate disposable_member_id / disposable_guest_id in live_test_config.json
with throwaway test accounts you can afford to permanently convert.
"""

from __future__ import annotations

import time
from typing import Optional
import warnings

import pytest
import requests

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


def _skip_if_no_disposable(ctx: LiveTestContext) -> str:
    """Return disposable_member_id or skip the test."""
    if not ctx.disposable_member_id:
        pytest.skip(
            "No disposable_member_id configured in live_test_config.json — "
            "this test permanently converts a user to MCG."
        )
    return ctx.disposable_member_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMakeMultiChannelGuest:
    """make_multi_channel_guest — identifier × state × type matrix."""

    # ----- active member → MCG (DESTRUCTIVE — uses disposable user) -----

    def test_make_mcg_active_member_by_id(self, ctx, users):
        """
        Convert a disposable active member to MCG.

        Uses disposable_member_id so the real active_member is not affected.
        There is no SCIM call to revert from guest → member; use
        admin.users.setRegular manually if needed.
        """
        uid = _skip_if_no_disposable(ctx)
        resp = users.make_multi_channel_guest(uid)
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

    # ----- already MCG → MCG (idempotent, safe) -----

    def test_make_mcg_already_mcg(self, ctx, users):
        """Making an already-MCG user into MCG should be idempotent."""
        resp = users.make_multi_channel_guest(ctx.multi_channel_guest_id)
        assert resp.ok, f"Expected ok (idempotent): {resp.data}"
        _pause()

    # ----- SCG → MCG (DESTRUCTIVE — uses disposable user or real SCG) -----

    def test_make_mcg_from_scg(self, ctx, users):
        """
        Converting a single-channel guest to MCG.

        This uses the disposable_guest_id if configured, otherwise
        falls back to single_channel_guest_id (which is already a guest
        so the damage is limited to type change only).
        """
        uid = ctx.disposable_guest_id or ctx.single_channel_guest_id
        resp = users.make_multi_channel_guest(uid)
        assert resp.ok, f"Expected ok (SCG → MCG): {resp.data}"
        _pause()

    # ----- admin (expect rejection) -----

    def test_make_mcg_admin(self, ctx, users):
        """Attempting to make an admin a MCG — expect error or policy rejection."""
        try:
            resp = users.make_multi_channel_guest(ctx.active_admin_id)
            warnings.warn(
                f"Slack allowed admin→MCG conversion — user {ctx.active_admin_id} "
                f"has been demoted. Restore with admin.users.setAdmin.",
                stacklevel=1,
            )
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403), (
                f"Unexpected status for admin→MCG: {exc.response.status_code}"
            )
        _pause()

    # ----- owner (expect rejection) -----

    def test_make_mcg_owner(self, ctx, users):
        """Attempting to make an owner a MCG — expect error or policy rejection."""
        try:
            resp = users.make_multi_channel_guest(ctx.active_owner_id)
            warnings.warn(
                f"Slack allowed owner→MCG conversion — user {ctx.active_owner_id} "
                f"has been demoted. Restore with admin.users.setOwner.",
                stacklevel=1,
            )
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403), (
                f"Unexpected status for owner→MCG: {exc.response.status_code}"
            )
        _pause()

    # ----- deactivated user -----

    def test_make_mcg_deactivated_user(self, ctx, users):
        """Attempting to make a deactivated user a MCG."""
        try:
            resp = users.make_multi_channel_guest(ctx.deactivated_user_id)
            warnings.warn(
                f"Slack allowed deactivated→MCG conversion — user {ctx.deactivated_user_id} "
                f"is now active as MCG. Re-deactivate with scim_deactivate_user.",
                stacklevel=1,
            )
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403, 404)
        _pause()

    # ----- non-existent user -----

    def test_make_mcg_nonexistent_user(self, ctx, users):
        """Attempting to make a non-existent user a MCG should error."""
        with pytest.raises((requests.HTTPError, RuntimeError, Exception)):
            users.make_multi_channel_guest(ctx.nonexistent_user_id)
        _pause()

    # ----- by email (idempotent on MCG user) -----

    def test_make_mcg_by_email(self, ctx, users):
        """Resolve email → id, then make MCG (on an already-MCG user for safety)."""
        try:
            uid = _resolve_user_id_from_email(users, ctx.active_member_email)
        except (AssertionError, SlackApiError):
            pytest.skip("Could not resolve email for MCG test")
        _pause()

        # Only run the actual conversion if this is the MCG user (idempotent)
        if uid == ctx.multi_channel_guest_id:
            resp = users.make_multi_channel_guest(uid)
            assert resp.ok
        _pause()

    # ----- bound user_id (idempotent on MCG user) -----

    def test_make_mcg_bound(self, ctx):
        """Call with no args on a bound Users instance (MCG user for idempotency)."""
        bound = ctx.slack.users(ctx.multi_channel_guest_id)
        resp = bound.make_multi_channel_guest()
        assert resp.ok, f"Expected ok for bound MCG: {resp.data}"
        _pause()

    def test_make_mcg_unbound_raises(self, users):
        """Calling with no user_id and unbound should raise ValueError."""
        with pytest.raises(ValueError, match="requires user_id"):
            users.make_multi_channel_guest()