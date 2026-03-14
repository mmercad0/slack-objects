"""
Live integration tests for scim_update_email.

MUTATING but REVERSIBLE — every email change is followed by a restore
to the original email in teardown.
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


def _scim_get_user(users: Users, user_id: str) -> Dict[str, Any]:
    resp = users._scim_request(path=f"Users/{user_id}", method="GET")
    assert resp.ok, f"SCIM GET Users/{user_id} failed: {resp.data}"
    return resp.data


def _get_primary_email(scim_data: Dict[str, Any]) -> str:
    """Extract the primary email from a SCIM user resource."""
    for email in scim_data.get("emails", []):
        if email.get("primary", False):
            return email.get("value", "")
    return ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScimUpdateEmail:
    """scim_update_email — identifier × type matrix."""

    # ----- active member -----

    def test_update_email_active_member(self, ctx, users):
        """Update primary email on an active member, verify, then restore."""
        original_data = _scim_get_user(users, ctx.active_member_id)
        original_email = _get_primary_email(original_data)
        assert original_email, "Could not determine original email"
        _pause()

        new_email = f"scim-test-{int(time.time())}@example.com"
        resp = users.scim_update_email(
            user_id=ctx.active_member_id,
            new_email=new_email,
        )
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        updated = _scim_get_user(users, ctx.active_member_id)
        assert _get_primary_email(updated) == new_email
        _pause()

        # Teardown: restore original email
        users.scim_update_email(
            user_id=ctx.active_member_id,
            new_email=original_email,
        )
        _pause()

    # ----- active admin -----

    def test_update_email_active_admin(self, ctx, users):
        """Update primary email on an admin, verify, then restore."""
        original_data = _scim_get_user(users, ctx.active_admin_id)
        original_email = _get_primary_email(original_data)
        assert original_email, "Could not determine original email"
        _pause()

        new_email = f"scim-admin-test-{int(time.time())}@example.com"
        resp = users.scim_update_email(
            user_id=ctx.active_admin_id,
            new_email=new_email,
        )
        assert resp.ok, f"Expected ok for admin: {resp.data}"
        _pause()

        # Teardown: restore
        users.scim_update_email(
            user_id=ctx.active_admin_id,
            new_email=original_email,
        )
        _pause()

    # ----- bound user_id (no explicit user_id) -----

    def test_update_email_bound_user(self, ctx, users):
        """Update email using bound user_id (no explicit user_id arg)."""
        bound = users.with_user(ctx.active_member_id)
        original_data = _scim_get_user(bound, ctx.active_member_id)
        original_email = _get_primary_email(original_data)
        assert original_email, "Could not determine original email"
        _pause()

        new_email = f"scim-bound-test-{int(time.time())}@example.com"
        resp = bound.scim_update_email(new_email=new_email)
        assert resp.ok, f"Expected ok for bound user: {resp.data}"
        _pause()

        # Teardown: restore
        bound.scim_update_email(new_email=original_email)
        _pause()

    # ----- deactivated user -----

    def test_update_email_deactivated_user(self, ctx, users):
        """Updating email on a deactivated user should fail or be a no-op."""
        try:
            resp = users.scim_update_email(
                user_id=ctx.deactivated_user_id,
                new_email="should-not-apply@example.com",
            )
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403, 404), (
                f"Unexpected status for deactivated user: {exc.response.status_code}"
            )
        _pause()