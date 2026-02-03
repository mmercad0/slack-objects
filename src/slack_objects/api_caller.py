import time
from typing import Any, Callable, Optional

from slack_sdk.errors import SlackApiError

from .config import SlackObjectsConfig, RateTier
from .rate_limits import DEFAULT_RATE_POLICY, RateLimitPolicy


class SlackApiCaller:
    """
    Wrapper around Slack SDK client to handle rate limiting and API calls.

    Example of use: self.api.call(self.client, "users.lookupByEmail", email=email)
    
    """
    def __init__(
        self,
        cfg: SlackObjectsConfig,
        policy: RateLimitPolicy = DEFAULT_RATE_POLICY,
    ):
        self.cfg = cfg
        self.policy = policy

    def call(self, client, method: str, *, rate_tier: Optional[RateTier] = None, **kwargs) -> Any:
        tier = rate_tier or self.policy.tier_for(method) or self.cfg.default_rate_tier
        time.sleep(float(tier))  # if RateTier is float Enum

        try:
            # slack_sdk WebClient exposes api_call for arbitrary methods
            return client.api_call(method, json=kwargs)
        except SlackApiError as e:
            # handle 429 backoff here, retry logic, etc.
            raise
