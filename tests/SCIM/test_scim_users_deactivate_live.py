"""
Live integration tests for scim_deactivate_user.

MUTATING but REVERSIBLE — every deactivation is followed by a reactivation
in teardown.  Note that deactivate/reactivate cycles strip workspace
assignments from users.

NOTE:   Deactivating admins/owners may be rejected by Slack depending on
        org policy. See note below in class TestScimDeactivateUser.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import pytest
import requests

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

class TestScimDeactivateUser:
    """scim_deactivate_user — identifier × state × type matrix."""

    # NOTE: Deactivating admins/owners may be rejected by Slack depending on
    #       org policy.  We test that the call either succeeds or raises a
    #       well-known HTTP error — not a crash.

    def test_deactivate_active_member_by_id(self, ctx, users):
        """Deactivate an active member, verify, then reactivate to restore state."""
        resp = users.scim_deactivate_user(ctx.active_member_id)
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        assert not _is_active_via_scim(users, ctx.active_member_id), "User should be inactive"
        _pause()

        # Teardown: reactivate
        users.scim_reactivate_user(ctx.active_member_id)
        _pause()

    def test_deactivate_active_admin_by_id(self, ctx, users):
        """Deactivating an admin may be blocked by org policy; expect ok or HTTPError."""
        try:
            resp = users.scim_deactivate_user(ctx.active_admin_id)
            if resp.ok:
                _pause()
                users.scim_reactivate_user(ctx.active_admin_id)
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403), f"Unexpected status: {exc.response.status_code}"
        _pause()

    def test_deactivate_active_owner_by_id(self, ctx, users):
        """Deactivating an owner is typically forbidden; expect HTTPError or ok."""
        try:
            resp = users.scim_deactivate_user(ctx.active_owner_id)
            if resp.ok:
                _pause()
                users.scim_reactivate_user(ctx.active_owner_id)
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403), f"Unexpected status: {exc.response.status_code}"
        _pause()

    def test_deactivate_active_scg_by_id(self, ctx, users):
        """Deactivate a single-channel guest, then reactivate."""
        resp = users.scim_deactivate_user(ctx.single_channel_guest_id)
        assert resp.ok, f"Expected ok for SCG: {resp.data}"
        _pause()

        users.scim_reactivate_user(ctx.single_channel_guest_id)
        _pause()

    def test_deactivate_active_mcg_by_id(self, ctx, users):
        """Deactivate a multi-channel guest, then reactivate."""
        resp = users.scim_deactivate_user(ctx.multi_channel_guest_id)
        assert resp.ok, f"Expected ok for MCG: {resp.data}"
        _pause()

        users.scim_reactivate_user(ctx.multi_channel_guest_id)
        _pause()

    def test_deactivate_already_deactivated_user(self, ctx, users):
        """Deactivating an already-deactivated user should succeed (idempotent) or return error gracefully."""
        try:
            resp = users.scim_deactivate_user(ctx.deactivated_user_id)
            assert resp.ok or resp.status_code in (200, 204, 404)
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 404), f"Unexpected: {exc.response.status_code}"
        _pause()

    def test_deactivate_nonexistent_user(self, ctx, users):
        """Deactivating a non-existent user should raise an HTTP error."""
        with pytest.raises((requests.HTTPError, RuntimeError, Exception)):
            users.scim_deactivate_user(ctx.nonexistent_user_id)
        _pause()

    def test_deactivate_member_by_email(self, ctx, users):
        """Resolve email → id, deactivate, verify, reactivate."""
        uid = _resolve_user_id_from_email(users, ctx.active_member_email)
        _pause()

        resp = users.scim_deactivate_user(uid)
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        assert not _is_active_via_scim(users, uid), "User should be inactive"
        _pause()

        users.scim_reactivate_user(uid)
        _pause()

    def test_deactivate_invalid_id_raises_valueerror(self, users):
        """Path-traversal IDs must be rejected by validate_scim_id."""
        with pytest.raises(ValueError):
            users.scim_deactivate_user("../../admin")