import time
from typing import Optional

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
        # Respect cfg.default_rate_tier as the policy's fallback tier
        self.policy = policy.with_default(cfg.default_rate_tier)

    def call(self, client, method: str, *, rate_tier: Optional[RateTier] = None, use_json: bool = False, _retry_count: int = 0, **kwargs) -> dict:
        MAX_RETRIES = 5
        tier = rate_tier or self.policy.tier_for(method)

        try:
            if use_json:
                resp = client.api_call(method, json=kwargs)
            else:
                resp = client.api_call(method, params=kwargs)

            data = resp.data if hasattr(resp, "data") else resp
            time.sleep(float(tier))
            return data

        except SlackApiError as e:
            if e.response is not None and e.response.status_code == 429:
                if _retry_count >= MAX_RETRIES:
                    raise RuntimeError(f"Rate-limited {MAX_RETRIES} times on {method}; giving up.") from e
                try:
                    retry_after = int(e.response.headers.get("Retry-After", tier))
                except (ValueError, TypeError):
                    retry_after = int(float(tier))
                time.sleep(retry_after)
                return self.call(client, method, rate_tier=tier, use_json=use_json, _retry_count=_retry_count + 1, **kwargs)
            raise
