"""
Live integration tests for mutating Users Admin / Web API methods.

Covers: wipe_all_sessions, add_to_workspace, remove_from_workspace,
        add_to_conversation, remove_from_conversation, set_user_profile_field,
        invite_user, set_guest_expiration_date.

WARNING — these tests WILL modify user state, channel membership, or
profile fields.  They are gated behind disposable_* config values and
skip automatically when those are not set.

Run:
    python -m pytest tests/Users/test_users_admin_live.py -v --tb=short
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


def _skip_no_disposable_member(ctx: LiveTestContext):
    if not ctx.disposable_member_id:
        pytest.skip("disposable_member_id not set in live_test_config.json")


def _skip_no_disposable_guest(ctx: LiveTestContext):
    if not ctx.disposable_guest_id:
        pytest.skip("disposable_guest_id not set in live_test_config.json")


def _skip_no_channel(ctx: LiveTestContext):
    if not ctx.channel_id:
        pytest.skip("channel_id not set in live_test_config.json")


# ═══════════════════════════════════════════════════════════════════════════
# 1.  wipe_all_sessions (admin.users.session.reset)
# ═══════════════════════════════════════════════════════════════════════════

class TestWipeAllSessions:
    """wipe_all_sessions — session reset for different user types.

    WARNING: These tests WILL invalidate the target user's sessions.
    """

    def test_disposable_member(self, ctx, users):
        """Wiping sessions for a disposable member returns ok."""
        _skip_no_disposable_member(ctx)
        resp = users.wipe_all_sessions(ctx.disposable_member_id)
        assert resp["ok"] is True
        _pause()

    def test_bound_instance(self, ctx):
        """Wiping sessions on a bound disposable instance works."""
        _skip_no_disposable_member(ctx)
        bound = _get_ctx().slack.users(ctx.disposable_member_id)
        resp = bound.wipe_all_sessions()
        assert resp["ok"] is True
        _pause()

    def test_nonexistent_user(self, ctx, users):
        """Wiping sessions for a non-existent user should raise SlackApiError."""
        with pytest.raises(SlackApiError):
            users.wipe_all_sessions(ctx.nonexistent_user_id)
        _pause()

    def test_deactivated_user(self, ctx, users):
        """Wiping sessions for a deactivated user — behaviour varies by org."""
        try:
            resp = users.wipe_all_sessions(ctx.deactivated_user_id)
            assert resp["ok"] is True
        except SlackApiError:
            pass  # Some orgs reject session reset for deactivated users
        _pause()

    def test_no_user_id_raises(self, users):
        """Unbound instance with no arg raises ValueError."""
        with pytest.raises(ValueError, match="requires user_id"):
            users.wipe_all_sessions()


# ═══════════════════════════════════════════════════════════════════════════
# 2.  add_to_workspace / remove_from_workspace
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkspaceAssignment:
    """add_to_workspace / remove_from_workspace — workspace membership."""

    def test_add_disposable_member(self, ctx, users):
        """Adding a disposable member returns ok or already_in_team."""
        _skip_no_disposable_member(ctx)
        try:
            resp = users.add_to_workspace(ctx.disposable_member_id, ctx.team_id)
            assert resp["ok"] is True
        except SlackApiError as e:
            assert "already_in_team" in str(e) or "user_already_team_member" in str(e)
        _pause()

    def test_add_nonexistent_user(self, ctx, users):
        """Adding a non-existent user should raise SlackApiError."""
        with pytest.raises(SlackApiError):
            users.add_to_workspace(ctx.nonexistent_user_id, ctx.team_id)
        _pause()

    def test_remove_nonexistent_user(self, ctx, users):
        """Removing a non-existent user should raise SlackApiError."""
        with pytest.raises(SlackApiError):
            users.remove_from_workspace(ctx.nonexistent_user_id, ctx.team_id)
        _pause()

    def test_add_deactivated_user(self, ctx, users):
        """Adding a deactivated user should raise SlackApiError."""
        with pytest.raises(SlackApiError):
            users.add_to_workspace(ctx.deactivated_user_id, ctx.team_id)
        _pause()

    def test_add_active_member_already_in_team(self, ctx, users):
        """Adding an active member already in the workspace — ok or already_in_team."""
        try:
            resp = users.add_to_workspace(ctx.active_member_id, ctx.team_id)
            assert resp["ok"] is True
        except SlackApiError as e:
            assert "already_in_team" in str(e) or "user_already_team_member" in str(e)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 3.  add_to_conversation / remove_from_conversation
# ═══════════════════════════════════════════════════════════════════════════

class TestConversationMembership:
    """add_to_conversation / remove_from_conversation — channel membership."""

    def test_add_disposable_member(self, ctx, users):
        """Adding a disposable member to a channel returns ok or already_in_channel."""
        _skip_no_disposable_member(ctx)
        _skip_no_channel(ctx)
        try:
            resp = users.add_to_conversation([ctx.disposable_member_id], ctx.channel_id)
            assert resp["ok"] is True
        except SlackApiError as e:
            assert "already_in_channel" in str(e)
        _pause()

    def test_add_nonexistent_user(self, ctx, users):
        """Adding a non-existent user to a channel should raise SlackApiError."""
        _skip_no_channel(ctx)
        with pytest.raises(SlackApiError):
            users.add_to_conversation([ctx.nonexistent_user_id], ctx.channel_id)
        _pause()

    def test_remove_nonexistent_user(self, ctx, users):
        """Removing a non-existent user from a channel should raise SlackApiError."""
        _skip_no_channel(ctx)
        with pytest.raises(SlackApiError):
            users.remove_from_conversation(ctx.nonexistent_user_id, ctx.channel_id)
        _pause()

    def test_add_and_remove_roundtrip(self, ctx, users):
        """Round-trip: add then remove a disposable member from a channel."""
        _skip_no_disposable_member(ctx)
        _skip_no_channel(ctx)

        # Add
        try:
            users.add_to_conversation([ctx.disposable_member_id], ctx.channel_id)
        except SlackApiError as e:
            if "already_in_channel" not in str(e):
                raise
        _pause()

        # Remove
        resp = users.remove_from_conversation(ctx.disposable_member_id, ctx.channel_id)
        assert resp["ok"] is True
        _pause()

    def test_add_deactivated_user(self, ctx, users):
        """Adding a deactivated user to a channel should raise SlackApiError."""
        _skip_no_channel(ctx)
        with pytest.raises(SlackApiError):
            users.add_to_conversation([ctx.deactivated_user_id], ctx.channel_id)
        _pause()

    def test_add_multiple_users(self, ctx, users):
        """Adding multiple users at once should work."""
        _skip_no_disposable_member(ctx)
        _skip_no_channel(ctx)
        try:
            resp = users.add_to_conversation(
                [ctx.disposable_member_id, ctx.active_member_id],
                ctx.channel_id,
            )
            assert resp["ok"] is True
        except SlackApiError as e:
            # Acceptable if users are already in the channel
            assert "already_in_channel" in str(e) or "failed_user_ids" in str(e)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 4.  set_user_profile_field
# ═══════════════════════════════════════════════════════════════════════════

class TestSetUserProfileField:
    """set_user_profile_field — profile mutation using disposable users only."""

    def test_no_user_id_raises(self, users):
        """Unbound instance with no arg raises ValueError."""
        with pytest.raises(ValueError, match="requires user_id"):
            users.set_user_profile_field("status_text", "test")

    def test_nonexistent_user(self, ctx, users):
        """Setting a field on a non-existent user should raise SlackApiError."""
        with pytest.raises(SlackApiError):
            users.set_user_profile_field("status_text", "test", user_id=ctx.nonexistent_user_id)
        _pause()

    def test_set_and_restore_status_text(self, ctx, users):
        """Set status_text on a disposable member, then restore original."""
        _skip_no_disposable_member(ctx)

        # Read original
        profile_resp = users.get_user_profile(ctx.disposable_member_id)
        original = profile_resp.get("profile", {}).get("status_text", "")
        _pause()

        # Set new
        resp = users.set_user_profile_field("status_text", "live-test-status", user_id=ctx.disposable_member_id)
        assert resp["ok"] is True
        _pause()

        # Verify change
        updated = users.get_user_profile(ctx.disposable_member_id)
        assert updated["profile"]["status_text"] == "live-test-status"
        _pause()

        # Restore original
        users.set_user_profile_field("status_text", original, user_id=ctx.disposable_member_id)
        _pause()

    def test_set_profile_field_deactivated_user(self, ctx, users):
        """Setting a field on a deactivated user should raise SlackApiError."""
        with pytest.raises(SlackApiError):
            users.set_user_profile_field("status_text", "test", user_id=ctx.deactivated_user_id)
        _pause()

    def test_bound_instance(self, ctx):
        """Bound instance should work without passing user_id."""
        _skip_no_disposable_member(ctx)
        bound = _get_ctx().slack.users(ctx.disposable_member_id)

        profile_resp = bound.get_user_profile()
        original = profile_resp.get("profile", {}).get("status_text", "")
        _pause()

        resp = bound.set_user_profile_field("status_text", "bound-test")
        assert resp["ok"] is True
        _pause()

        # Restore
        bound.set_user_profile_field("status_text", original)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 5.  set_guest_expiration_date
# ═══════════════════════════════════════════════════════════════════════════

class TestSetGuestExpirationDate:
    """set_guest_expiration_date — guest expiration via admin.users.setExpiration."""

    def test_no_user_id_raises(self, users):
        """Unbound instance with no arg raises ValueError."""
        with pytest.raises(ValueError, match="requires user_id"):
            users.set_guest_expiration_date("2099-12-31")

    def test_disposable_guest(self, ctx, users):
        """Setting expiration on a disposable guest returns ok."""
        _skip_no_disposable_guest(ctx)
        resp = users.set_guest_expiration_date("2099-12-31", user_id=ctx.disposable_guest_id)
        assert resp["ok"] is True
        _pause()

    def test_nonexistent_user(self, ctx, users):
        """Setting expiration on a non-existent user should raise."""
        with pytest.raises((SlackApiError, RuntimeError)):
            users.set_guest_expiration_date("2099-12-31", user_id=ctx.nonexistent_user_id)
        _pause()

    def test_non_guest_user(self, ctx, users):
        """Setting expiration on a non-guest full member should raise."""
        with pytest.raises(SlackApiError):
            users.set_guest_expiration_date("2099-12-31", user_id=ctx.active_member_id)
        _pause()


# ═══════════════════════════════════════════════════════════════════════════
# 6.  invite_user (admin.users.invite)
# ═══════════════════════════════════════════════════════════════════════════

class TestInviteUser:
    """invite_user — basic validation and error cases.

    Actual invitations are NOT tested to avoid creating real accounts.
    """

    def test_invite_already_existing_email(self, ctx, users):
        """Inviting an already-existing email should raise SlackApiError."""
        _skip_no_channel(ctx)
        with pytest.raises(SlackApiError):
            users.invite_user(
                channel_ids=ctx.channel_id,
                email=ctx.active_member_email,
                team_id=ctx.team_id,
            )
        _pause()

    def test_invite_accepts_list_of_channels(self, ctx, users):
        """channel_ids as list should not raise a TypeError."""
        _skip_no_channel(ctx)
        with pytest.raises(SlackApiError):
            # Will fail because email exists, but proves list is serialized
            users.invite_user(
                channel_ids=[ctx.channel_id],
                email=ctx.active_member_email,
                team_id=ctx.team_id,
            )
        _pause()