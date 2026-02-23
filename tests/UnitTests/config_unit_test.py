# tests/UnitTests/config_unit_test.py
"""
Unit tests for SlackObjectsConfig, RateTier, and ID/email regexes.
"""

import pytest

from slack_objects.config import (
    SlackObjectsConfig,
    RateTier,
    USER_ID_RE,
    CONVERSATION_ID_RE,
    EMAIL_RE,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1.  RateTier enum
# ═══════════════════════════════════════════════════════════════════════════

class TestRateTier:
    """RateTier values and float behavior."""

    def test_tier_values(self):
        assert float(RateTier.TIER_1) == 60.0
        assert float(RateTier.TIER_2) == 3.0
        assert float(RateTier.TIER_3) == 1.2
        assert float(RateTier.TIER_4) == 0.6
        assert float(RateTier.TIER_D) == 0.05

    def test_tier_is_float(self):
        """RateTier members are usable as plain floats."""
        assert isinstance(RateTier.TIER_3, float)
        assert RateTier.TIER_4 + 0.4 == pytest.approx(1.0)

    def test_all_members_present(self):
        names = {m.name for m in RateTier}
        assert names == {"TIER_1", "TIER_2", "TIER_3", "TIER_4", "TIER_D"}


# ═══════════════════════════════════════════════════════════════════════════
# 2.  Regex patterns
# ═══════════════════════════════════════════════════════════════════════════

class TestUserIdRegex:
    """USER_ID_RE — U or W followed by uppercase alphanumeric."""

    @pytest.mark.parametrize("valid", ["U12345", "UABC", "W0DEF123"])
    def test_valid_ids(self, valid):
        assert USER_ID_RE.match(valid)

    @pytest.mark.parametrize("invalid", ["", "u12345", "C12345", "U", "U123 45", "U123-AB"])
    def test_invalid_ids(self, invalid):
        assert not USER_ID_RE.match(invalid)


class TestConversationIdRegex:
    """CONVERSATION_ID_RE — C, G, or D followed by uppercase alphanumeric."""

    @pytest.mark.parametrize("valid", ["C12345", "GABC", "D0DEF123"])
    def test_valid_ids(self, valid):
        assert CONVERSATION_ID_RE.match(valid)

    @pytest.mark.parametrize("invalid", ["", "c12345", "U12345", "C", "C123 45"])
    def test_invalid_ids(self, invalid):
        assert not CONVERSATION_ID_RE.match(invalid)


class TestEmailRegex:
    """EMAIL_RE — lightweight email validation."""

    @pytest.mark.parametrize("valid", ["user@example.com", "a.b-c@sub.domain.org"])
    def test_valid_emails(self, valid):
        assert EMAIL_RE.match(valid)

    @pytest.mark.parametrize("invalid", ["", "noatsign", "@no-local.com", "user@", "user@.com"])
    def test_invalid_emails(self, invalid):
        assert not EMAIL_RE.match(invalid)


# ═══════════════════════════════════════════════════════════════════════════
# 3.  SlackObjectsConfig
# ═══════════════════════════════════════════════════════════════════════════

class TestSlackObjectsConfig:
    """SlackObjectsConfig defaults, immutability, and repr masking."""

    def test_defaults(self):
        cfg = SlackObjectsConfig()
        assert cfg.bot_token is None
        assert cfg.user_token is None
        assert cfg.scim_token is None
        assert cfg.default_rate_tier is RateTier.TIER_2
        assert cfg.scim_version == "v2"
        assert cfg.http_timeout_seconds == 30

    def test_frozen_raises_on_mutation(self):
        cfg = SlackObjectsConfig(bot_token="xoxb-test")
        with pytest.raises(AttributeError):
            cfg.bot_token = "xoxb-other"

    def test_repr_masks_tokens(self):
        cfg = SlackObjectsConfig(bot_token="xoxb-secret", user_token="xoxp-secret")
        text = repr(cfg)
        assert "xoxb-secret" not in text
        assert "xoxp-secret" not in text
        assert "***" in text

    def test_repr_shows_none_for_missing_tokens(self):
        cfg = SlackObjectsConfig()
        text = repr(cfg)
        assert "bot_token=None" in text

    def test_custom_values(self):
        cfg = SlackObjectsConfig(
            bot_token="xoxb-1",
            scim_base_url="https://custom.slack.com/scim",
            scim_version="v1",
            default_rate_tier=RateTier.TIER_4,
            http_timeout_seconds=60,
        )
        assert cfg.scim_base_url == "https://custom.slack.com/scim"
        assert cfg.scim_version == "v1"
        assert cfg.default_rate_tier is RateTier.TIER_4
        assert cfg.http_timeout_seconds == 60