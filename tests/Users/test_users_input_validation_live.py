"""
Live integration tests for Users input validation.

SAFE — these tests verify that missing/invalid arguments are rejected
locally before any network call is made.  No Slack API calls are issued.

Run:
    python -m pytest tests/Users/test_users_input_validation_live.py -v --tb=short
"""

from __future__ import annotations

from typing import Optional

import pytest

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


# ═══════════════════════════════════════════════════════════════════════════
# Unbound instance — methods requiring user_id
# ═══════════════════════════════════════════════════════════════════════════

class TestUnboundUserIdRequired:
    """Methods that require user_id should raise ValueError on unbound instances."""

    def test_refresh_no_user_id(self, users):
        with pytest.raises(ValueError, match="requires user_id"):
            users.refresh()

    def test_get_user_profile_no_arg(self, users):
        with pytest.raises(ValueError, match="requires user_id"):
            users.get_user_profile()

    def test_set_user_profile_field_no_arg(self, users):
        with pytest.raises(ValueError, match="requires user_id"):
            users.set_user_profile_field("status_text", "test")

    def test_wipe_all_sessions_no_arg(self, users):
        with pytest.raises(ValueError, match="requires user_id"):
            users.wipe_all_sessions()

    def test_set_guest_expiration_date_no_arg(self, users):
        with pytest.raises(ValueError, match="requires user_id"):
            users.set_guest_expiration_date("2099-12-31")


# ═══════════════════════════════════════════════════════════════════════════
# Unbound instance — classification helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestUnboundClassificationHelpers:
    """Classification helpers require loaded attributes; unbound should raise."""

    def test_is_active_no_attrs(self, users):
        with pytest.raises(ValueError):
            users.is_active()

    def test_is_guest_no_attrs(self, users):
        with pytest.raises(ValueError):
            users.is_guest()

    def test_is_contingent_worker_no_attrs(self, users):
        with pytest.raises(ValueError):
            users.is_contingent_worker()


# ═══════════════════════════════════════════════════════════════════════════
# is_user_authorized — requires bound user_id
# ═══════════════════════════════════════════════════════════════════════════

class TestIsUserAuthorizedValidation:
    """is_user_authorized requires a bound user_id."""

    def test_unbound_raises(self, users):
        with pytest.raises(ValueError, match="requires a bound user_id"):
            users.is_user_authorized("some_service")

    def test_unknown_service_returns_false(self, ctx):
        """Service not configured in auth_idp_groups_* should return False."""
        bound = _get_ctx().slack.users(ctx.active_member_id)
        assert bound.is_user_authorized("nonexistent_service_xyz") is False

    def test_read_and_write_levels(self, ctx):
        """Both auth_level='read' and 'write' should return bool for unknown services."""
        bound = _get_ctx().slack.users(ctx.active_member_id)
        assert bound.is_user_authorized("fake_svc", auth_level="read") is False
        assert bound.is_user_authorized("fake_svc", auth_level="write") is False


# ═══════════════════════════════════════════════════════════════════════════
# _require_attributes — lazy loading
# ═══════════════════════════════════════════════════════════════════════════

class TestRequireAttributes:
    """_require_attributes should auto-refresh when bound, raise when unbound."""

    def test_auto_refresh_when_bound(self, ctx):
        """Bound user with no attrs yet should auto-refresh on first access."""
        bound = _get_ctx().slack.users(ctx.active_member_id)
        assert not bound.attributes  # no attrs yet
        attrs = bound._require_attributes()
        assert attrs["id"] == ctx.active_member_id

    def test_raises_when_fully_unbound(self, users):
        """Unbound, no user_id, no attrs should raise ValueError."""
        with pytest.raises(ValueError, match="not loaded"):
            users._require_attributes()


# ═══════════════════════════════════════════════════════════════════════════
# resolve_user_id — input validation (no API calls for these)
# ═══════════════════════════════════════════════════════════════════════════

class TestResolveUserIdValidation:
    """resolve_user_id should reject empty/blank identifiers locally."""

    def test_empty_raises(self, users):
        with pytest.raises(ValueError, match="must not be empty"):
            users.resolve_user_id("")

    def test_whitespace_raises(self, users):
        with pytest.raises(ValueError, match="must not be empty"):
            users.resolve_user_id("   ")

    def test_user_id_passthrough(self, ctx, users):
        """Known user ID is returned as-is without an API call."""
        assert users.resolve_user_id(ctx.active_member_id) == ctx.active_member_id