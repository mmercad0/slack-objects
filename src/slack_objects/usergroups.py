from __future__ import annotations

"""
slack_objects.usergroups
========================

Usergroups helper for the `slack-objects` package.

Purpose
-------
Manage Slack-native user groups via the Web API (usergroups.*).
These are distinct from IdP (SCIM) groups managed in ``idp_groups.py``.

Design decisions
----------------
- Only calls the Slack Web API via SlackApiCaller; no SCIM dependency.
- Keeps the same output shape as IDP_groups members
  (``[{'value': <user_id>, 'display': ''}]``) so callers can swap sources.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import SlackObjectBase
from .config import RateTier


@dataclass
class Usergroups(SlackObjectBase):
    """
    Slack-native usergroups helper.

    Factory usage:
        slack = SlackObjectsClient(cfg)
        ug = slack.usergroups()              # unbound
        bound = slack.usergroups("S0614TZR7") # bound to a usergroup_id
    """
    usergroup_id: Optional[str] = None

    # ---------- factory ----------

    def with_usergroup(self, usergroup_id: str) -> "Usergroups":
        """Return a new instance bound to a particular usergroup_id, sharing cfg/client/logger/api."""
        return Usergroups(
            cfg=self.cfg,
            client=self.client,
            logger=self.logger,
            api=self.api,
            usergroup_id=usergroup_id,
        )

    # ---------- identifier resolution ----------

    def _resolve_usergroup_id(self, usergroup_id: Optional[str] = None) -> str:
        """Resolve usergroup_id from argument or bound instance value."""
        ugid = usergroup_id or self.usergroup_id
        if not ugid:
            raise ValueError("usergroup_id is required (passed or bound)")
        return ugid

    # ---------- endpoint wrappers (only these call self.api.call) ----------

    def _usergroups_list(self, **kwargs: Any) -> Dict[str, Any]:
        """Wrapper for usergroups.list."""
        if self.cfg.team_id:
            kwargs.setdefault("team_id", self.cfg.team_id)
        return self.api.call(self.client, "usergroups.list", rate_tier=RateTier.TIER_2, **kwargs)

    def _usergroups_users_list(self, usergroup_id: str) -> Dict[str, Any]:
        """Wrapper for usergroups.users.list."""
        kwargs: Dict[str, Any] = {"usergroup": usergroup_id}
        if self.cfg.team_id:
            kwargs["team_id"] = self.cfg.team_id
        return self.api.call(self.client, "usergroups.users.list", rate_tier=RateTier.TIER_2, **kwargs)

    # ---------- public helpers ----------

    def get_usergroups(self) -> List[Dict[str, Any]]:
        """Return all usergroups visible to the bot token (usergroups.list)."""
        resp = self._usergroups_list()
        return resp.get("usergroups", [])

    def get_members(self, usergroup_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Return members of a Slack usergroup via the Web API (usergroups.users.list).

        Returns the same shape as ``IDP_groups.get_members_scim()`` —
        ``[{'value': <user_id>, 'display': ''}]`` — so callers can swap
        sources without changing downstream code.

        Requires the ``usergroups:read`` bot scope.
        For org-wide tokens, ``cfg.team_id`` must be set.
        """
        ugid = self._resolve_usergroup_id(usergroup_id)
        resp = self._usergroups_users_list(ugid)
        users = resp.get("users", [])
        return [{"value": uid, "display": ""} for uid in users]

    def is_member(self, user_id: str, usergroup_id: Optional[str] = None) -> bool:
        """Return True if ``user_id`` is a member of the usergroup."""
        members = self.get_members(usergroup_id=usergroup_id)
        for member in members:
            if member.get("value") == user_id:
                return True
        return False