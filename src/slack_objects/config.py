import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

# Slack user/bot IDs: U or W followed by uppercase alphanumeric characters.
USER_ID_RE = re.compile(r"^[UW][A-Z0-9]+$")

# Lightweight email pattern (not RFC 5322, but catches obvious non-emails).
EMAIL_RE = re.compile(r"^[\w.\-]+@[\w.\-]+\.\w+$")


class RateTier(float, Enum):
	"""
	Slack API rate-tier backoff defaults (seconds). These are defined to conform to Slack Web API rate limits.
	https://docs.slack.dev/apis/web-api/rate-limits/
	"""

	TIER_1 = 60.0	# 1+ per minute
	TIER_2 = 3.0	# 20+ per minute
	TIER_3 = 1.2	# 50+ per minute
	TIER_4 = 0.6	# 100+ per minute
	TIER_D = 0.05	# 1200+ per minute


@dataclass(frozen=True)
class SlackObjectsConfig:
	"""
	Configuration settings for slack-objects.

	Tokens are optional at construction time.
	Individual methods will raise clear errors if a required token is missing.
	"""
	bot_token: Optional[str] = field(default=None, repr=False)
	user_token: Optional[str] = field(default=None, repr=False)
	scim_token: Optional[str] = field(default=None, repr=False)

	default_rate_tier: RateTier = RateTier.TIER_2

	auth_idp_groups_read_access: dict[str, list[str]] = field(default_factory=dict)
	auth_idp_groups_write_access: dict[str, list[str]] = field(default_factory=dict)

	# SCIM settings
	scim_base_url: str = "https://api.slack.com/scim"
	scim_version: str = "v2"

	# HTTP timeout for SCIM and file-download requests (seconds)
	http_timeout_seconds: int = 30

	def __repr__(self) -> str:
		""" Modifying the default dataclass __repr__ to mask token values for security. """
		def _mask(val: Optional[str]) -> str:
			return "***" if val else "None"
		return (
			f"SlackObjectsConfig("
			f"bot_token={_mask(self.bot_token)}, "
			f"user_token={_mask(self.user_token)}, "
			f"scim_token={_mask(self.scim_token)}, "
			f"default_rate_tier={self.default_rate_tier}, "
			f"auth_idp_groups_read_access={self.auth_idp_groups_read_access}, "
			f"auth_idp_groups_write_access={self.auth_idp_groups_write_access}, "
			f"scim_base_url={self.scim_base_url}, "
			f"scim_version={self.scim_version}, "
			f"http_timeout_seconds={self.http_timeout_seconds})"
		)