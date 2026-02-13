"""
Live integration tests for scim_create_user.

SELF-CONTAINED — creates users with unique emails and immediately
deactivates (deletes) them in teardown.
"""

from __future__ import annotations

import time
from typing import Optional

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScimCreateUser:
    """scim_create_user — creates a real user then cleans up."""

    def test_create_user_success(self, ctx, users):
        """Create a new user with a unique email, verify response, then deactivate."""
        ts = int(time.time())
        username = f"scim-test-{ts}"
        email = f"scim-test-{ts}@example.com"

        resp = users.scim_create_user(username=username, email=email)
        assert resp.ok, f"scim_create_user failed: {resp.data}"
        new_id = resp.data.get("id")
        assert new_id, f"No id in response: {resp.data}"
        _pause()

        # Teardown: deactivate the newly created user
        users.scim_deactivate_user(new_id)
        _pause()

    def test_create_user_duplicate_email(self, ctx, users):
        """Creating a user with an existing email should fail."""
        try:
            resp = users.scim_create_user(
                username="duplicate-test",
                email=ctx.active_member_email,
            )
            assert not resp.ok or resp.status_code == 409, (
                f"Expected failure for duplicate email, got: {resp.data}"
            )
        except requests.HTTPError as exc:
            assert exc.response.status_code == 409, f"Expected 409, got {exc.response.status_code}"
        _pause()

    def test_create_user_empty_username_raises(self, users):
        """Empty username should be caught (by Slack or locally)."""
        with pytest.raises((requests.HTTPError, ValueError, Exception)):
            users.scim_create_user(username="", email="empty-user@example.com")
        _pause()

    def test_create_user_empty_email_raises(self, users):
        """Empty email should be caught."""
        with pytest.raises((requests.HTTPError, ValueError, Exception)):
            users.scim_create_user(username="test-no-email", email="")
        _pause()