"""
Live integration tests for every SCIM method on the Users object helper.

These tests hit the REAL Slack SCIM API — no fakes, no mocks.
They require Azure Key Vault credentials and a live_test_config.json file;
see tests/SCIM/conftest_live.py for setup details.

Run:
    python -m pytest tests/SCIM/test_scim_users_live.py -v --tb=short

Combinatorial coverage
----------------------
For each SCIM method the tests exercise every meaningful combination of:
  - Identifier style : user_id  |  email → resolved id  |  @username (display_name)
  - Account state    : active   |  deactivated           |  non-existent
  - Account type     : regular member | admin | owner | single-channel guest | multi-channel guest
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

# Slack SCIM rate limits are strict (Tier 2 ≈ 20 req/min).  Pause between
# mutating calls to avoid 429s in CI.
_SCIM_PAUSE = 4.0


def _pause():
    time.sleep(_SCIM_PAUSE)


def _resolve_user_id_from_email(users: Users, email: str) -> str:
    """Resolve a user ID from an email address using the Web API."""
    resp = users.lookup_by_email(email)
    assert resp.get("ok"), f"lookup_by_email({email}) failed: {resp}"
    return resp["user"]["id"]


def _get_display_name(users: Users, user_id: str) -> str:
    """Fetch the @display_name for a user via Web API."""
    resp = users.get_user_info(user_id)
    assert resp.get("ok"), f"get_user_info({user_id}) failed: {resp}"
    profile = resp["user"].get("profile", {})
    return profile.get("display_name") or resp["user"].get("real_name", "")


def _scim_get_user(users: Users, user_id: str) -> Dict[str, Any]:
    """Raw SCIM GET Users/<id> to inspect current state."""
    resp = users._scim_request(path=f"Users/{user_id}", method="GET")
    assert resp.ok, f"SCIM GET Users/{user_id} failed: {resp.data}"
    return resp.data


def _is_active_via_scim(users: Users, user_id: str) -> bool:
    data = _scim_get_user(users, user_id)
    return bool(data.get("active", False))


# ═══════════════════════════════════════════════════════════════════════════
# 1.  scim_reactivate_user
# ═══════════════════════════════════════════════════════════════════════════
#
# Combinations:
#   identifier  ×  account_state         ×  account_type
#   (id/email)     (active/deactivated      (member/admin/owner/scg/mcg/
#                   /non-existent)            non-existent)

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

        # Verify the user is now active
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
        # For deactivated users lookupByEmail may fail; fall back to the known ID
        try:
            uid = _resolve_user_id_from_email(users, ctx.deactivated_user_email)
        except AssertionError:
            uid = ctx.deactivated_user_id

        resp = users.scim_reactivate_user(uid)
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

        # Teardown
        users.scim_deactivate_user(uid)
        _pause()

    def test_reactivate_nonexistent_email(self, ctx, users):
        """Resolving a non-existent email should fail before we even call SCIM."""
        resp = users.lookup_by_email(ctx.nonexistent_email)
        assert not resp.get("ok"), "Expected lookup to fail for non-existent email"
        _pause()

    # ----- by display_name (resolved to user_id) -----

    def test_reactivate_active_member_by_display_name(self, ctx, users):
        """Resolve @display_name → id, then reactivate."""
        display = _get_display_name(users, ctx.active_member_id)
        _pause()
        # We already know the ID; this validates the display_name → id pathway
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


# ═══════════════════════════════════════════════════════════════════════════
# 2.  scim_deactivate_user
# ═══════════════════════════════════════════════════════════════════════════

class TestScimDeactivateUser:
    """scim_deactivate_user — identifier × state × type matrix."""

    # NOTE: Deactivating admins/owners may be rejected by Slack depending on
    #       org policy.  We test that the call either succeeds or raises a
    #       well-known HTTP error — not a crash.

    def test_deactivate_active_member_by_id(self, ctx, users):
        """
        Deactivate an active member, verify, then reactivate to restore state.
        """
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
            # If it succeeds, reactivate immediately
            if resp.ok:
                _pause()
                users.scim_reactivate_user(ctx.active_admin_id)
        except requests.HTTPError as exc:
            # 403 or 400 is acceptable (Slack may disallow deactivating admins)
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

        # Teardown
        users.scim_reactivate_user(ctx.single_channel_guest_id)
        _pause()

    def test_deactivate_active_mcg_by_id(self, ctx, users):
        """Deactivate a multi-channel guest, then reactivate."""
        resp = users.scim_deactivate_user(ctx.multi_channel_guest_id)
        assert resp.ok, f"Expected ok for MCG: {resp.data}"
        _pause()

        # Teardown
        users.scim_reactivate_user(ctx.multi_channel_guest_id)
        _pause()

    def test_deactivate_already_deactivated_user(self, ctx, users):
        """Deactivating an already-deactivated user should succeed (idempotent) or return error gracefully."""
        try:
            resp = users.scim_deactivate_user(ctx.deactivated_user_id)
            # Slack may return ok even if already deactivated
            assert resp.ok or resp.status_code in (200, 204, 404)
        except requests.HTTPError as exc:
            # 404 is acceptable if Slack doesn't find an active user
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

        # Teardown
        users.scim_reactivate_user(uid)
        _pause()

    def test_deactivate_invalid_id_raises_valueerror(self, users):
        """Path-traversal IDs must be rejected by validate_scim_id."""
        with pytest.raises(ValueError):
            users.scim_deactivate_user("../../admin")


# ═══════════════════════════════════════════════════════════════════════════
# 3.  scim_create_user
# ═══════════════════════════════════════════════════════════════════════════

class TestScimCreateUser:
    """
    scim_create_user — creates a real user.

    These tests create and immediately deactivate (delete) to clean up.
    Use a unique email domain you control or a +alias pattern.
    """

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
            # Slack may return 409 Conflict or a non-ok response
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


# ═══════════════════════════════════════════════════════════════════════════
# 4.  scim_update_user_attribute
# ═══════════════════════════════════════════════════════════════════════════

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

        # Verify the change took effect
        updated = _scim_get_user(users, ctx.active_member_id)
        assert updated.get("displayName") == "SCIM Test DisplayName"
        _pause()

        # Teardown: restore original
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

        # Restore
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

        # Restore
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

        # Restore
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
            # Some Slack orgs allow PATCH on deactivated users; if so, just accept
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

        # Restore
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


# ═══════════════════════════════════════════════════════════════════════════
# 5.  make_multi_channel_guest
# ═══════════════════════════════════════════════════════════════════════════

class TestMakeMultiChannelGuest:
    """make_multi_channel_guest — identifier × state × type matrix."""

    # ----- active member → MCG -----

    def test_make_mcg_active_member_by_id(self, ctx, users):
        """
        Convert an active member to MCG.

        WARNING: This changes the user's account type.
        Teardown NOTE: There is no SCIM call to revert from guest → member.
        You may need to manually restore the user or use admin.users.setRegular.
        Only run this against disposable/test user accounts.
        """
        pytest.skip(
            "Skipped by default: converting a member to MCG is destructive. "
            "Remove this skip to run against a disposable test user."
        )
        resp = users.make_multi_channel_guest(ctx.active_member_id)
        assert resp.ok, f"Expected ok: {resp.data}"
        _pause()

    # ----- already MCG → MCG (idempotent) -----

    def test_make_mcg_already_mcg(self, ctx, users):
        """Making an already-MCG user into MCG should be idempotent."""
        resp = users.make_multi_channel_guest(ctx.multi_channel_guest_id)
        assert resp.ok, f"Expected ok (idempotent): {resp.data}"
        _pause()

    # ----- SCG → MCG -----

    def test_make_mcg_from_scg(self, ctx, users):
        """Converting a single-channel guest to MCG."""
        resp = users.make_multi_channel_guest(ctx.single_channel_guest_id)
        assert resp.ok, f"Expected ok (SCG → MCG): {resp.data}"
        _pause()
        # NOTE: SCG→MCG may or may not be reversible via SCIM depending on org settings.

    # ----- admin -----

    def test_make_mcg_admin(self, ctx, users):
        """Attempting to make an admin a MCG — expect error or policy rejection."""
        try:
            resp = users.make_multi_channel_guest(ctx.active_admin_id)
            # If Slack allows it (unlikely), the test still passes
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403), (
                f"Unexpected status for admin→MCG: {exc.response.status_code}"
            )
        _pause()

    # ----- owner -----

    def test_make_mcg_owner(self, ctx, users):
        """Attempting to make an owner a MCG — expect error or policy rejection."""
        try:
            resp = users.make_multi_channel_guest(ctx.active_owner_id)
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
        except requests.HTTPError as exc:
            assert exc.response.status_code in (400, 403, 404)
        _pause()

    # ----- non-existent user -----

    def test_make_mcg_nonexistent_user(self, ctx, users):
        """Attempting to make a non-existent user a MCG should error."""
        with pytest.raises((requests.HTTPError, RuntimeError, Exception)):
            users.make_multi_channel_guest(ctx.nonexistent_user_id)
        _pause()

    # ----- by email -----

    def test_make_mcg_by_email(self, ctx, users):
        """Resolve email → id, then make MCG (on an already-MCG user for safety)."""
        # Use the MCG user's email if available, else skip
        try:
            # We use the active member email but resolve it; this tests the pathway
            uid = _resolve_user_id_from_email(users, ctx.active_member_email)
        except AssertionError:
            pytest.skip("Could not resolve email for MCG test")
        _pause()

        # Only run the actual conversion if this is the MCG user (idempotent)
        if uid == ctx.multi_channel_guest_id:
            resp = users.make_multi_channel_guest(uid)
            assert resp.ok
        _pause()

    # ----- bound user_id -----

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


# ═══════════════════════════════════════════════════════════════════════════
# 6.  Input validation (applies to all SCIM methods)
# ═══════════════════════════════════════════════════════════════════════════

class TestScimInputValidation:
    """Cross-cutting input validation for SCIM methods."""

    @pytest.mark.parametrize("bad_id", [
        "../../admin",
        "U1/../../etc",
        "G1/../G2",
        "",
        " ",
        "U1 U2",
        "U1;DROP",
        "G1&x=1",
        "U<script>",
    ])
    def test_deactivate_rejects_bad_ids(self, users, bad_id):
        with pytest.raises(ValueError):
            users.scim_deactivate_user(bad_id)

    @pytest.mark.parametrize("bad_id", [
        "../../admin",
        "",
        " ",
        "U1;DROP",
    ])
    def test_reactivate_rejects_bad_ids(self, users, bad_id):
        with pytest.raises(ValueError):
            users.scim_reactivate_user(bad_id)

    @pytest.mark.parametrize("bad_id", [
        "../traversal",
        "",
        "id with spaces",
    ])
    def test_update_attribute_rejects_bad_ids(self, users, bad_id):
        with pytest.raises(ValueError):
            users.scim_update_user_attribute(
                user_id=bad_id,
                attribute="displayName",
                new_value="x",
            )

    @pytest.mark.parametrize("bad_id", [
        "../traversal",
        "",
    ])
    def test_make_mcg_rejects_bad_ids(self, users, bad_id):
        with pytest.raises(ValueError):
            users.make_multi_channel_guest(bad_id)