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

        try:
            resp = client.api_call(method, json=kwargs)
            data = resp.data if hasattr(resp, "data") else resp

            # Space out subsequent calls
            time.sleep(float(tier))
            return data

        except SlackApiError as e:
            # Handle rate limiting properly
            if e.response is not None and e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", tier))
                time.sleep(retry_after)
                return self.call(client, method, rate_tier=tier, **kwargs)

            raise
