import time
from typing import Any, Optional

from slack_sdk.errors import SlackApiError

from .config import SlackObjectsConfig, RateTier
from .rate_limits import DEFAULT_RATE_POLICY, RateLimitPolicy


class SlackApiCaller:
    """
    Wrapper around Slack SDK client to handle rate limiting and API calls.

    Example: self.api.call(self.client, "users.lookupByEmail", email=email)
    """
    def __init__(self, cfg: SlackObjectsConfig, policy: RateLimitPolicy = DEFAULT_RATE_POLICY):
        self.cfg = cfg
        self.policy = policy

    def call(self, client, method: str, *, rate_tier: Optional[RateTier] = None, **kwargs) -> dict:
        tier = rate_tier or self.policy.tier_for(method) or self.cfg.default_rate_tier
        time.sleep(float(tier))

        try:
            resp = client.api_call(method, json=kwargs)
            # Normalize slack_sdk SlackResponse -> plain dict for the rest of the package
            return resp.data if hasattr(resp, "data") else resp
        except SlackApiError:
            raise
