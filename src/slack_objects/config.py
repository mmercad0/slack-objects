from enum import Enum
from dataclasses import dataclass

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
	Configuration settings for Slack objects.
	"""
	bot_token: str
	user_token: str
	scim_token: str

	default_rate_tier: RateTier = RateTier.TIER_2