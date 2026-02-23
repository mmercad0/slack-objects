"""
Live integration tests for Users classification helpers.

Covers: is_active, is_guest, is_contingent_worker.

These are READ-ONLY — each test refreshes user attributes then checks
the boolean classification.

Run:
    python -m pytest tests/Users/test_users_classification_live.py -v --tb=short
"""

from __future__ import annotations

import time
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


_API_PAUSE = 2.0


def _pause():
    time.sleep(_API_PAUSE)


def _bound(ctx: LiveTestContext, user_id: str) -> Users:
    """Return a Users instance bound to user_id with attributes loaded."""
    bound = _get_ctx().slack.users(user_id)
    bound.refresh()
    _pause()
    return bound


# ═══════════════════════════════════════════════════════════════════════════
# 1.  is_active
# ═══════════════════════════════════════════════════════════════════════════

class TestIsActive:
    """is_active — active/deleted detection for every user type."""

    def test_active_member(self, ctx):
        """Active member returns True."""
        assert _bound(ctx, ctx.active_member_id).is_active() is True

    def test_active_admin(self, ctx):
        """Active admin returns True."""
        assert _bound(ctx, ctx.active_admin_id).is_active() is True

    def test_active_owner(self, ctx):
        """Owner with no workspaces appears deleted in Web API (0-workspace quirk).

        The Web API ``users.info`` returns ``deleted: True`` for users removed
        from all workspaces even though they are still active at the org level.
        Use ``is_active_scim()`` to get the true org-level status.
        """
        bound = _bound(ctx, ctx.active_owner_id)
        assert bound.is_active() is False  # Web API quirk: no workspaces → deleted
        _pause()

        # Confirm the user is truly active at the org level
        assert bound.is_active_scim() is True

    def test_single_channel_guest(self, ctx):
        """Active SCG returns True."""
        assert _bound(ctx, ctx.single_channel_guest_id).is_active() is True

    def test_multi_channel_guest(self, ctx):
        """Active MCG returns True."""
        assert _bound(ctx, ctx.multi_channel_guest_id).is_active() is True

    def test_deactivated_user(self, ctx):
        """Deactivated user returns False."""
        assert _bound(ctx, ctx.deactivated_user_id).is_active() is False

    def test_unbound_no_attrs_raises(self, users):
        """Unbound instance with no attributes raises ValueError."""
        with pytest.raises(ValueError):
            users.is_active()

    def test_override_with_different_user_id(self, ctx):
        """Passing user_id to an already-bound instance fetches fresh data."""
        bound = _bound(ctx, ctx.active_member_id)
        # Override with a deactivated user — should return False
        assert bound.is_active(user_id=ctx.deactivated_user_id) is False
        _pause()
# ═══════════════════════════════════════════════════════════════════════════
# 2.  is_guest
# ═══════════════════════════════════════════════════════════════════════════

class TestIsGuest:
    """is_guest — guest detection for every user type."""

    def test_active_member_not_guest(self, ctx):
        """Full member returns False."""
        assert _bound(ctx, ctx.active_member_id).is_guest() is False

    def test_active_admin_not_guest(self, ctx):
        """Admin returns False."""
        assert _bound(ctx, ctx.active_admin_id).is_guest() is False

    def test_active_owner_not_guest(self, ctx):
        """Owner returns False."""
        assert _bound(ctx, ctx.active_owner_id).is_guest() is False

    def test_single_channel_guest_is_guest(self, ctx):
        """SCG returns True."""
        assert _bound(ctx, ctx.single_channel_guest_id).is_guest() is True

    def test_multi_channel_guest_is_guest(self, ctx):
        """MCG returns True."""
        assert _bound(ctx, ctx.multi_channel_guest_id).is_guest() is True

    def test_deactivated_user_returns_bool(self, ctx):
        """Deactivated user returns a bool (may or may not have been a guest)."""
        result = _bound(ctx, ctx.deactivated_user_id).is_guest()
        assert isinstance(result, bool)

    def test_unbound_no_attrs_raises(self, users):
        """Unbound instance with no attributes raises ValueError."""
        with pytest.raises(ValueError):
            users.is_guest()


# ═══════════════════════════════════════════════════════════════════════════
# 3.  is_contingent_worker
# ═══════════════════════════════════════════════════════════════════════════

class TestIsContingentWorker:
    """is_contingent_worker — [External] label heuristic for all user types."""

    def test_active_member(self, ctx):
        """Active member returns a bool."""
        assert isinstance(_bound(ctx, ctx.active_member_id).is_contingent_worker(), bool)

    def test_active_admin(self, ctx):
        """Admin returns a bool."""
        assert isinstance(_bound(ctx, ctx.active_admin_id).is_contingent_worker(), bool)

    def test_active_owner(self, ctx):
        """Owner returns a bool."""
        assert isinstance(_bound(ctx, ctx.active_owner_id).is_contingent_worker(), bool)

    def test_single_channel_guest(self, ctx):
        """SCG returns a bool."""
        assert isinstance(_bound(ctx, ctx.single_channel_guest_id).is_contingent_worker(), bool)

    def test_multi_channel_guest(self, ctx):
        """MCG returns a bool."""
        assert isinstance(_bound(ctx, ctx.multi_channel_guest_id).is_contingent_worker(), bool)

    def test_deactivated_user(self, ctx):
        """Deactivated user returns a bool."""
        assert isinstance(_bound(ctx, ctx.deactivated_user_id).is_contingent_worker(), bool)

    def test_unbound_no_attrs_raises(self, users):
        """Unbound instance with no attributes raises ValueError."""
        with pytest.raises(ValueError):
            users.is_contingent_worker()


# ═══════════════════════════════════════════════════════════════════════════
# 4.  is_active_scim
# ═══════════════════════════════════════════════════════════════════════════

class TestIsActiveScim:
    """is_active_scim — org-level active check via SCIM, not affected by 0-workspace quirk."""

    def test_active_member(self, ctx):
        """Active member returns True at org level."""
        bound = _get_ctx().slack.users(ctx.active_member_id)
        assert bound.is_active_scim() is True
        _pause()

    def test_active_admin(self, ctx):
        """Active admin returns True at org level."""
        bound = _get_ctx().slack.users(ctx.active_admin_id)
        assert bound.is_active_scim() is True
        _pause()

    def test_active_owner(self, ctx):
        """Active owner returns True at org level."""
        bound = _get_ctx().slack.users(ctx.active_owner_id)
        assert bound.is_active_scim() is True
        _pause()

    def test_single_channel_guest(self, ctx):
        """Active SCG returns True at org level."""
        bound = _get_ctx().slack.users(ctx.single_channel_guest_id)
        assert bound.is_active_scim() is True
        _pause()

    def test_multi_channel_guest(self, ctx):
        """Active MCG returns True at org level."""
        bound = _get_ctx().slack.users(ctx.multi_channel_guest_id)
        assert bound.is_active_scim() is True
        _pause()

    def test_deactivated_user(self, ctx):
        """Truly deactivated user returns False at org level."""
        bound = _get_ctx().slack.users(ctx.deactivated_user_id)
        assert bound.is_active_scim() is False
        _pause()

    def test_unbound_no_user_id_raises(self, users):
        """Unbound instance with no user_id raises ValueError."""
        with pytest.raises(ValueError, match="requires user_id"):
            users.is_active_scim()

    def test_explicit_user_id(self, ctx, users):
        """Passing user_id explicitly works on an unbound instance."""
        result = users.is_active_scim(user_id=ctx.active_member_id)
        assert result is True
        _pause()