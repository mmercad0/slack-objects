from __future__ import annotations

"""
slack_objects.idp_groups
========================

IDP_groups helper for the `slack-objects` package.

Purpose
-------
Manage Identity Provider (IdP) groups synced into Slack via SCIM.
This module implements the following functionality:

- list groups (paginated)
- get members of a given group
- check whether a user is a member of a group

Design decisions
----------------
- SCIM REST calls are centralized in ScimMixin._scim_request(); all public methods call endpoint wrappers.
- Uses an injectable `requests.Session` (`scim_session`) so tests can pass a fake session.
- Keeps legacy output shapes: lists of dicts for groups and members.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from .base import SlackObjectBase
from .scim_base import ScimMixin, ScimResponse, validate_scim_id


@dataclass
class IDP_groups(ScimMixin, SlackObjectBase):
    """
    IdP (SCIM) groups helper.

    Factory usage:
        slack = SlackObjectsClient(cfg)
        idp = slack.idp_groups()          # unbound
        bound = slack.idp_groups("S123")  # bound to a group_id

    The SCIM session can be replaced for unit tests by passing scim_session argument.
    """
    group_id: Optional[str] = None
    scim_session: requests.Session = field(default_factory=requests.Session, repr=False)

    # ---------- factory ----------
    def with_group(self, group_id: str) -> "IDP_groups":
        """Return a new instance bound to a particular group_id, sharing cfg/client/logger/api."""
        return IDP_groups(
            cfg=self.cfg,
            client=self.client,
            logger=self.logger,
            api=self.api,
            group_id=group_id,
            scim_session=self.scim_session,
        )

    # ---------- endpoint wrappers (only these call _scim_request) ----------

    def _scim_groups_list(self, *, count: int = 1000, start_index: Optional[int] = None) -> Dict[str, Any]:
        """
        Wrapper for GET Groups (paginated).
        Accepts pagination params as query parameters according to Slack SCIM docs.
        """
        params: Dict[str, Any] = {"count": count}
        if start_index:
            params["startIndex"] = start_index
        return self._scim_request(path="Groups", method="GET", params=params).data

    def _scim_group_get(self, group_id: str) -> Dict[str, Any]:
        """Wrapper for GET Groups/{id}"""
        validate_scim_id(group_id, "group_id")
        return self._scim_request(path=f"Groups/{group_id}", method="GET").data

    # ---------- public helpers ----------

    def get_groups(self, fetch_count: int = 1000) -> List[Dict[str, str]]:
        """
        Return a list of IdP groups visible to the SCIM token.

        Legacy behavior: returns a list of maps containing only 'group id' and 'group name'.
        Pagination is respected; this method aggregates all pages.

        Raises:
            requests.HTTPError on non-2xx responses.
        """
        groups_out: List[Dict[str, str]] = []
        start_index = None
        total_results = None
        retrieved = 0

        while True:
            resp = self._scim_groups_list(count=fetch_count, start_index=start_index)

            # Slack SCIM returns 'Resources' (list) and 'totalResults' and 'startIndex' values.
            resources = resp.get("Resources", []) or []
            for grp in resources:
                groups_out.append({"group id": grp.get("id"), "group name": grp.get("displayName")})
                retrieved += 1

            total_results = resp.get("totalResults", total_results)
            # Calculate next page: SCIM uses startIndex + count
            if total_results is None:
                # If API doesn't give a total, break to avoid infinite loop
                break

            # Determine if we fetched all
            if retrieved >= int(total_results):
                break

            # Move cursor forward; SCIM startIndex is 1-based
            if start_index is None:
                start_index = fetch_count + 1
            else:
                start_index = start_index + fetch_count

        return groups_out

    def get_members(self, group_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Return the members of a group as a list of dicts `{'value': <user_id>, 'display': <name>}`.

        If `group_id` omitted, uses bound `self.group_id`. Raises ValueError if none provided.
        """
        gid = group_id or self.group_id
        if not gid:
            raise ValueError("get_members requires group_id (passed or bound)")

        resp = self._scim_group_get(gid)
        # In the legacy scripts, group members are at `members` in the response body
        return resp.get("members", [])

    def is_member(self, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        Return True if `user_id` is a member of `group_id`.
        Preserves legacy semantics (scans the members list).
        """
        members = self.get_members(group_id=group_id)
        for member in members:
            # member dicts historically had 'value' for id
            if member.get("value") == user_id:
                return True
        return False
