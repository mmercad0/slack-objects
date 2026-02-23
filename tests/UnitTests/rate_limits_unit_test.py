# tests/UnitTests/rate_limits_unit_test.py
"""
Unit tests for RateLimitPolicy resolution logic and DEFAULT_RATE_POLICY.
"""

import pytest

from slack_objects.config import RateTier
from slack_objects.rate_limits import RateLimitPolicy, DEFAULT_RATE_POLICY


# ═══════════════════════════════════════════════════════════════════════════
# 1.  tier_for resolution
# ═══════════════════════════════════════════════════════════════════════════

class TestTierFor:
    """tier_for — exact match → longest prefix → default fallback."""

    @pytest.fixture()
    def policy(self) -> RateLimitPolicy:
        return RateLimitPolicy(
            method_overrides={
                "files.upload": RateTier.TIER_2,
                "admin.conversations.archive": RateTier.TIER_1,
            },
            prefix_rules={
                "admin.": RateTier.TIER_1,
                "admin.conversations.": RateTier.TIER_2,
                "chat.": RateTier.TIER_3,
            },
            default=RateTier.TIER_4,
        )

    def test_exact_match_wins(self, policy):
        """Exact override takes priority over prefix."""
        assert policy.tier_for("files.upload") is RateTier.TIER_2

    def test_exact_match_over_prefix(self, policy):
        """Exact override beats a matching prefix rule."""
        assert policy.tier_for("admin.conversations.archive") is RateTier.TIER_1

    def test_longest_prefix_wins(self, policy):
        """When no exact match, longest matching prefix wins."""
        # "admin.conversations.search" matches both "admin." and "admin.conversations."
        assert policy.tier_for("admin.conversations.search") is RateTier.TIER_2

    def test_shorter_prefix(self, policy):
        """A method matching only the shorter prefix gets that tier."""
        assert policy.tier_for("admin.teams.list") is RateTier.TIER_1

    def test_prefix_match(self, policy):
        assert policy.tier_for("chat.postMessage") is RateTier.TIER_3

    def test_default_fallback(self, policy):
        """Unknown method falls through to the default tier."""
        assert policy.tier_for("unknown.method") is RateTier.TIER_4


# ═══════════════════════════════════════════════════════════════════════════
# 2.  with_default
# ═══════════════════════════════════════════════════════════════════════════

class TestWithDefault:
    """with_default — returns a new policy; original is unchanged."""

    def test_returns_new_policy(self):
        original = RateLimitPolicy(
            method_overrides={}, prefix_rules={}, default=RateTier.TIER_3,
        )
        updated = original.with_default(RateTier.TIER_1)

        assert updated.default is RateTier.TIER_1
        assert original.default is RateTier.TIER_3  # untouched

    def test_preserves_rules(self):
        original = RateLimitPolicy(
            method_overrides={"a.b": RateTier.TIER_D},
            prefix_rules={"a.": RateTier.TIER_4},
            default=RateTier.TIER_3,
        )
        updated = original.with_default(RateTier.TIER_1)

        assert updated.tier_for("a.b") is RateTier.TIER_D
        assert updated.tier_for("a.other") is RateTier.TIER_4
        assert updated.tier_for("z.unknown") is RateTier.TIER_1


# ═══════════════════════════════════════════════════════════════════════════
# 3.  DEFAULT_RATE_POLICY spot-checks
# ═══════════════════════════════════════════════════════════════════════════

class TestDefaultRatePolicy:
    """Verify well-known entries in DEFAULT_RATE_POLICY."""

    def test_exact_override_conversations_history(self):
        assert DEFAULT_RATE_POLICY.tier_for("conversations.history") is RateTier.TIER_3

    def test_exact_override_files_upload(self):
        assert DEFAULT_RATE_POLICY.tier_for("files.upload") is RateTier.TIER_2

    def test_prefix_admin(self):
        assert DEFAULT_RATE_POLICY.tier_for("admin.teams.list") is RateTier.TIER_1

    def test_prefix_users(self):
        assert DEFAULT_RATE_POLICY.tier_for("users.info") is RateTier.TIER_2

    def test_fallback(self):
        assert DEFAULT_RATE_POLICY.tier_for("totally.unknown") is RateTier.TIER_3

    def test_frozen(self):
        """DEFAULT_RATE_POLICY is a frozen dataclass — no mutation."""
        with pytest.raises(AttributeError):
            DEFAULT_RATE_POLICY.default = RateTier.TIER_D