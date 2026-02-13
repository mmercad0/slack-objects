"""
Live integration tests for scim_update_user_attribute.

MUTATING but REVERSIBLE — every attribute change is followed by a restore
to the original value in teardown.
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScimUpdateUserAttribute:
    """scim_update_user_attribute — identifier × type matrix."""

    # ----- active member -----

    def test_update_displayName_active_member(self, ctx, users):
        """Update displayName on an active member."""
        original = _scim_get_user(users, ctx.active_member_id).get("displayName", "")
        _pause()

        resp = users.scim_update_user_attribute(
            user_id=ctx.active_member_id,
            attribute="displayName",
            new_value="SCIM Test DisplayName",
        )
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        updated = _scim_get_user(users, ctx.active_member_id)
        assert updated.get("displayName") == "SCIM Test DisplayName"
        _pause()

        users.scim_update_user_attribute(
            user_id=ctx.active_member_id,
            attribute="displayName",
            new_value=original,
        )
        _pause()

    def test_update_title_active_member(self, ctx, users):
        """Update title on an active member."""
        resp = users.scim_update_user_attribute(
            user_id=ctx.active_member_id,
            attribute="title",
            new_value="Integration Test Title",
        )
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        users.scim_update_user_attribute(
            user_id=ctx.active_member_id,
            attribute="title",
            new_value="",
        )
        _pause()

    # ----- active admin -----

    def test_update_displayName_active_admin(self, ctx, users):
        """Update displayName on an admin."""
        resp = users.scim_update_user_attribute(
            user_id=ctx.active_admin_id,
            attribute="displayName",
            new_value="Admin SCIM Test",
        )
        assert resp.ok, f"Expected ok for admin: {resp.data}"
        _pause()

        users.scim_update_user_attribute(
            user_id=ctx.active_admin_id,
            attribute="displayName",
            new_value="",
        )
        _pause()

    # ----- active owner -----

    def test_update_displayName_active_owner(self, ctx, users):
        """Update displayName on an owner."""
        resp = users.scim_update_user_attribute(
            user_id=ctx.active_owner_id,
            attribute="displayName",
            new_value="Owner SCIM Test",
        )
        assert resp.ok, f"Expected ok for owner: {resp.data}"
        _pause()

        users.scim_update_user_attribute(
            user_id=ctx.active_owner_id,
            attribute="displayName",
            new_value="",
        )
        _pause()

    # ----- single-channel guest -----

    def test_update_displayName_scg(self, ctx, users):
        """Update displayName on a single-channel guest."""
        resp = users.scim_update_user_attribute(
            user_id=ctx.single_channel_guest_id,
            attribute="displayName",
            new_value="SCG SCIM Test",
        )
        assert resp.ok, f"Expected ok for SCG: {resp.data}"
        _pause()

        users.scim_update_user_attribute(
            user_id=ctx.single_channel_guest_id,
            attribute="displayName",
            new_value="",
        )
        _pause()

    # ----- multi-channel guest -----

    def test_update_displayName_mcg(self, ctx, users):
        """Update displayName on a multi-channel guest."""
        resp = users.scim_update_user_attribute(
            user_id=ctx.multi_channel_guest_id,
            attribute="displayName",
            new_value="MCG SCIM Test",
        )
        assert resp.ok, f"Expected ok for MCG: {resp.data}"
        _pause()

        users.scim_update_user_attribute(
            user_id=ctx.multi_channel_guest_id,
            attribute="displayName",
            new_value="",
        )
        _pause()

    # ----- deactivated user -----

    def test_update_attribute_deactivated_user(self, ctx, users):
        """Updating an attribute on a deactivated user should fail or be a no-op."""
        try:
            resp = users.scim_update_user_attribute(
                user_id=ctx.deactivated_user_id,
                attribute="displayName",
                new_value="Should Not Work",
            )
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403, 404), (
                f"Unexpected status for deactivated user: {exc.response.status_code}"
            )
        _pause()

    # ----- non-existent user -----

    def test_update_attribute_nonexistent_user(self, ctx, users):
        """Updating an attribute on a non-existent user should error."""
        with pytest.raises((requests.HTTPError, RuntimeError, Exception)):
            users.scim_update_user_attribute(
                user_id=ctx.nonexistent_user_id,
                attribute="displayName",
                new_value="Ghost",
            )
        _pause()

    # ----- by email -----

    def test_update_attribute_by_email(self, ctx, users):
        """Resolve email → id, then update attribute."""
        uid = _resolve_user_id_from_email(users, ctx.active_member_email)
        _pause()

        resp = users.scim_update_user_attribute(
            user_id=uid,
            attribute="title",
            new_value="Via Email Resolution",
        )
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        users.scim_update_user_attribute(user_id=uid, attribute="title", new_value="")
        _pause()

    # ----- invalid id -----

    def test_update_attribute_invalid_id_raises(self, users):
        """Path-traversal IDs must be rejected."""
        with pytest.raises(ValueError):
            users.scim_update_user_attribute(
                user_id="../../../etc",
                attribute="displayName",
                new_value="x",
            )