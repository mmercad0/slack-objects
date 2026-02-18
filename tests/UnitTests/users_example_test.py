import logging
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from slack_objects.client import SlackObjectsClient
from slack_objects.config import SlackObjectsConfig, RateTier, USER_ID_RE
from slack_objects.api_caller import SlackApiCaller
from slack_objects.scim_base import ScimResponse


class FakeWebClient:
    def api_call(self, method: str, json: Optional[Dict[str, Any]] = None):
        payload = json or {}

        if method == "users.info":
            return {"ok": True, "user": {
                "id": payload.get("user", "U_TEST"),
                "real_name": "[External] Test User",
                "profile": {"display_name": "Testy"},
                "is_restricted": False,
                "is_ultra_restricted": False,
            }}

        if method == "users.lookupByEmail":
            if payload.get("email") == "found@example.com":
                return {"ok": True, "user": {"id": "UFOUND"}}
            return {"ok": False, "error": "users_not_found"}

        return {"ok": True}


class FakeApiCaller(SlackApiCaller):
    def __init__(self, cfg):
        self.cfg = cfg
        self.policy = None

    def call(self, client, method: str, *, rate_tier=None, **kwargs):
        # No sleeping, no SlackResponse normalization needed for this fake
        return client.api_call(method, json=kwargs)


def _make_users():
    """Helper: build a Users instance wired to fakes."""
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_3,
    )
    slack = SlackObjectsClient(cfg, logger=logging.getLogger("test"))
    slack.web_client = FakeWebClient()
    slack.api = FakeApiCaller(cfg)
    slack._users = None
    return slack.users()


# ═══════════════════════════════════════════════════════════════════════════
# Existing tests
# ═══════════════════════════════════════════════════════════════════════════

def test_factory_users_unbound_and_bound():
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        user_token="xoxp-fake",
        scim_token="xoxp-fake",
        default_rate_tier=RateTier.TIER_3,
    )

    slack = SlackObjectsClient(cfg, logger=logging.getLogger("test"))
    slack.web_client = FakeWebClient()
    slack.api = FakeApiCaller(cfg)
    slack._users = None

    users = slack.users()
    assert users.user_id is None

    bound = slack.users("U123")
    attrs = bound.refresh()
    assert attrs["id"] == "U123"
    assert bound.is_contingent_worker() is True

    uid = users.get_user_id_from_email("found@example.com")
    assert uid == "UFOUND"


def test_get_user_id_from_email_miss_returns_empty():
    """get_user_id_from_email returns '' when the email is not found."""
    users = _make_users()
    assert users.get_user_id_from_email("nobody@example.com") == ""


# ═══════════════════════════════════════════════════════════════════════════
# USER_ID_RE
# ═══════════════════════════════════════════════════════════════════════════

class TestUserIdRegex:
    """USER_ID_RE should match Slack user/bot ID patterns."""

    def test_valid_user_ids(self):
        for valid in ("U01ABC123", "U123", "UABC", "W0ABC123"):
            assert USER_ID_RE.match(valid), f"Expected match for {valid!r}"

    def test_rejects_lowercase(self):
        for invalid in ("u01abc", "Uabc", "w0abc"):
            assert not USER_ID_RE.match(invalid), f"Should not match {invalid!r}"

    def test_rejects_non_user_prefixes(self):
        for invalid in ("S123", "G456", "C789", "T000", ""):
            assert not USER_ID_RE.match(invalid), f"Should not match {invalid!r}"

    def test_rejects_special_chars(self):
        for invalid in ("U-123", "U_ABC", "U01/../../"):
            assert not USER_ID_RE.match(invalid), f"Should not match {invalid!r}"


# ═══════════════════════════════════════════════════════════════════════════
# _looks_like_user_id
# ═══════════════════════════════════════════════════════════════════════════

class TestLooksLikeUserId:
    """_looks_like_user_id delegates to USER_ID_RE."""

    def test_valid(self):
        users = _make_users()
        assert users._looks_like_user_id("U01ABC123") is True
        assert users._looks_like_user_id("W0ABC") is True

    def test_invalid(self):
        users = _make_users()
        assert users._looks_like_user_id("alice@example.com") is False
        assert users._looks_like_user_id("@alice") is False
        assert users._looks_like_user_id("S123") is False
        assert users._looks_like_user_id("") is False


# ═══════════════════════════════════════════════════════════════════════════
# _first_scim_user_id
# ═══════════════════════════════════════════════════════════════════════════

class TestFirstScimUserId:
    """_first_scim_user_id extracts the first resource ID from a SCIM list."""

    def test_with_resources(self):
        users = _make_users()
        resp = ScimResponse(ok=True, status_code=200, data={"Resources": [{"id": "U099"}]}, text="")
        assert users._first_scim_user_id(resp) == "U099"

    def test_empty_resources(self):
        users = _make_users()
        resp = ScimResponse(ok=True, status_code=200, data={"Resources": []}, text="")
        assert users._first_scim_user_id(resp) == ""

    def test_no_resources_key(self):
        users = _make_users()
        resp = ScimResponse(ok=True, status_code=200, data={}, text="")
        assert users._first_scim_user_id(resp) == ""


# ═══════════════════════════════════════════════════════════════════════════
# resolve_user_id
# ═══════════════════════════════════════════════════════════════════════════

class TestResolveUserId:
    """resolve_user_id — identifier classification and fallback logic."""

    def test_user_id_verified(self):
        """User IDs are verified via users.info before returning."""
        users = _make_users()
        assert users.resolve_user_id("U01ABC123") == "U01ABC123"
        assert users.resolve_user_id("W0ABC") == "W0ABC"

    def test_user_id_not_found_raises(self):
        """Non-existent user ID raises LookupError."""
        users = _make_users()
        users.get_user_info = MagicMock(return_value={"ok": False, "error": "user_not_found"})
        with pytest.raises(LookupError, match="No user found for user ID"):
            users.resolve_user_id("U00GHOST")

    def test_email_active_user(self):
        """Active user email resolves via Web API (fast path)."""
        users = _make_users()
        assert users.resolve_user_id("found@example.com") == "UFOUND"

    def test_email_falls_back_to_scim(self):
        """Deactivated user email falls back to SCIM search."""
        users = _make_users()
        scim_resp = ScimResponse(ok=True, status_code=200, data={"Resources": [{"id": "UDEACTIVATED"}]}, text="")
        users.scim_search_user_by_email = MagicMock(return_value=scim_resp)

        assert users.resolve_user_id("deactivated@example.com") == "UDEACTIVATED"
        users.scim_search_user_by_email.assert_called_once_with("deactivated@example.com")

    def test_email_not_found_raises(self):
        """Email not found in Web API or SCIM raises LookupError."""
        users = _make_users()
        scim_resp = ScimResponse(ok=True, status_code=200, data={"Resources": []}, text="")
        users.scim_search_user_by_email = MagicMock(return_value=scim_resp)

        with pytest.raises(LookupError, match="No user found for email"):
            users.resolve_user_id("ghost@example.com")

    def test_at_username(self):
        """@username resolves via SCIM userName search."""
        users = _make_users()
        scim_resp = ScimResponse(ok=True, status_code=200, data={"Resources": [{"id": "UALICE"}]}, text="")
        users.scim_search_user_by_username = MagicMock(return_value=scim_resp)

        assert users.resolve_user_id("@alice") == "UALICE"
        users.scim_search_user_by_username.assert_called_once_with("alice")

    def test_at_username_not_found_raises(self):
        """@username not found raises LookupError."""
        users = _make_users()
        scim_resp = ScimResponse(ok=True, status_code=200, data={"Resources": []}, text="")
        users.scim_search_user_by_username = MagicMock(return_value=scim_resp)

        with pytest.raises(LookupError, match="No user found for username"):
            users.resolve_user_id("@ghost")

    def test_bare_username(self):
        """Bare string (not an ID, not an email) resolves via SCIM."""
        users = _make_users()
        scim_resp = ScimResponse(ok=True, status_code=200, data={"Resources": [{"id": "UBOB"}]}, text="")
        users.scim_search_user_by_username = MagicMock(return_value=scim_resp)

        assert users.resolve_user_id("bob") == "UBOB"

    def test_empty_raises(self):
        """Empty identifier raises ValueError."""
        users = _make_users()
        with pytest.raises(ValueError, match="must not be empty"):
            users.resolve_user_id("")

    def test_whitespace_only_raises(self):
        """Whitespace-only identifier raises ValueError."""
        users = _make_users()
        with pytest.raises(ValueError, match="must not be empty"):
            users.resolve_user_id("   ")

# ═══════════════════════════════════════════════════════════════════════════
# is_user_authorized
# ═══════════════════════════════════════════════════════════════════════════

class TestIsUserAuthorized:
    """is_user_authorized — IdP group-based authorization checks."""

    @staticmethod
    def _make_users_with_auth(*, read_access=None, write_access=None):
        """Build a Users instance with auth policy baked into the frozen config."""
        cfg = SlackObjectsConfig(
            bot_token="xoxb-fake",
            user_token="xoxp-fake",
            scim_token="xoxp-fake",
            default_rate_tier=RateTier.TIER_3,
            auth_idp_groups_read_access=read_access or {},
            auth_idp_groups_write_access=write_access or {},
        )
        slack = SlackObjectsClient(cfg, logger=logging.getLogger("test"))
        slack.web_client = FakeWebClient()
        slack.api = FakeApiCaller(cfg)
        slack._users = None
        return slack.users()

    def test_unbound_raises(self):
        """Unbound instance (no user_id) should raise ValueError."""
        users = _make_users()
        with pytest.raises(ValueError, match="requires a bound user_id"):
            users.is_user_authorized("some_service")

    def test_no_groups_configured_returns_false(self):
        """Service with no configured groups returns False."""
        users = _make_users()
        users.user_id = "U123"
        assert users.is_user_authorized("nonexistent_service") is False

    def test_read_level_checks_read_groups(self):
        """auth_level='read' should consult auth_idp_groups_read_access."""
        users = self._make_users_with_auth(read_access={"my_svc": ["G001"]})
        users.user_id = "U123"

        from unittest.mock import patch
        with patch("slack_objects.idp_groups.IDP_groups") as MockIDP:
            MockIDP.return_value.is_member.return_value = True
            assert users.is_user_authorized("my_svc", auth_level="read") is True
            MockIDP.return_value.is_member.assert_called_once_with(user_id="U123", group_id="G001")

    def test_write_level_checks_write_groups(self):
        """auth_level='write' should consult auth_idp_groups_write_access."""
        users = self._make_users_with_auth(write_access={"my_svc": ["G002"]})
        users.user_id = "U123"

        from unittest.mock import patch
        with patch("slack_objects.idp_groups.IDP_groups") as MockIDP:
            MockIDP.return_value.is_member.return_value = False
            assert users.is_user_authorized("my_svc", auth_level="write") is False

    def test_returns_true_on_first_matching_group(self):
        """Should return True as soon as any group matches (short-circuit)."""
        users = self._make_users_with_auth(read_access={"my_svc": ["G001", "G002"]})
        users.user_id = "U123"

        from unittest.mock import patch
        with patch("slack_objects.idp_groups.IDP_groups") as MockIDP:
            MockIDP.return_value.is_member.side_effect = [False, True]
            assert users.is_user_authorized("my_svc") is True
            assert MockIDP.return_value.is_member.call_count == 2
