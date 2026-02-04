from enum import Enum
from dataclasses import dataclass
from typing import Optional

class RateTier(float, Enum):
	"""
	Slack API rate-tier backoff defaults (seconds). These are defined to conform to Slack Web API rate limits.
	https://docs.slack.dev/apis/web-api/rate-limits/
	"""

	TIER_1 = 60.0	# 1+ per minute
	TIER_2 = 3.0	# 20+ per minute
	TIER_3 = 1.2	# 50+ per minute
	TIER_4 = 0.6	# 100+ per minute


@dataclass(frozen=True)
class SlackObjectsConfig:
	"""
	Configuration settings for slack-objects.

	Tokens are optional at construction time.
	Individual methods will raise clear errors if a required token is missing.
	"""
	bot_token: Optional[str] = None
	user_token: Optional[str] = None
	scim_token: Optional[str] = None

	default_rate_tier: RateTier = RateTier.TIER_2