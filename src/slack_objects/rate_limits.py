from dataclasses import dataclass, replace
from typing import Mapping

from .config import RateTier


@dataclass(frozen=True)
class RateLimitPolicy:
    # exact method overrides (most specific)
    method_overrides: Mapping[str, RateTier]

    # prefix rules (less specific)
    prefix_rules: Mapping[str, RateTier]

    # fallback
    default: RateTier = RateTier.TIER_3

    def with_default(self, tier: RateTier) -> "RateLimitPolicy":
        """Return a copy of this policy with a different fallback tier."""
        return replace(self, default=tier)

    def tier_for(self, method: str) -> RateTier:
        # 1) exact match wins
        if method in self.method_overrides:
            return self.method_overrides[method]

        # 2) longest prefix match wins
        best = None
        for prefix, tier in self.prefix_rules.items():
            if method.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
                best = (prefix, tier)
        if best:
            return best[1]

        # 3) default
        return self.default


DEFAULT_RATE_POLICY = RateLimitPolicy(
    method_overrides={
        # add only the truly special cases
        "conversations.history": RateTier.TIER_3,
        "files.upload": RateTier.TIER_2,
    },
    prefix_rules={
        "admin.": RateTier.TIER_1,
        "scim.": RateTier.TIER_2,          # if you represent SCIM calls similarly
        "conversations.": RateTier.TIER_3,
        "chat.": RateTier.TIER_3,
        "files.": RateTier.TIER_2,
        "users.": RateTier.TIER_2,
        "team.": RateTier.TIER_2,
    },
    default=RateTier.TIER_3,
)
