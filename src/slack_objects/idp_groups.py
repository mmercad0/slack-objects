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
- get a single group's full SCIM record (name, members, metadata)
- get members of a given group
- check whether a user is a member of a group

Design decisions
----------------
- SCIM REST calls are centralized in ScimMixin._scim_request(); all public methods call endpoint wrappers.
- Uses an injectable `requests.Session` (`scim_session`) so tests can pass a fake session.
- Keeps legacy output shapes: lists of dicts for groups and members.
- ``get_group()`` is the single read path for GET Groups/{id}; ``get_members()``,
  ``is_member()`` and the ``display_name``/``members`` properties all compose on it
  so the endpoint is only ever called from one place.
- Attributes are loaded lazily (like ``Users``): binding a group_id does no network I/O,
  the fetch happens on first property access or on ``refresh()``.
- This module is SCIM-only. For Slack-native usergroups, see ``usergroups.py``.
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

    Binding a group_id performs no API call. `attributes` are loaded lazily via
    `_require_attributes()` on first property access, so a single GET Groups/{id}
    serves both the name and the members:

        group = slack.idp_groups("S123")
        name = group.display_name   # triggers the fetch
        members = group.members     # served from the same cached response

    The SCIM session can be replaced for unit tests by passing scim_session argument.
    """
    group_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
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

    # ---------- identifier resolution ----------

    def _resolve_group_id(self, group_id: Optional[str] = None) -> str:
        """Resolve group_id from argument or bound instance value."""
        gid = group_id or self.group_id
        if not gid:
            raise ValueError("group_id is required (passed or bound)")
        return gid

    # ---------- lazily loaded attributes ----------

    def refresh(self, group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Refresh cached attributes for group_id (or self.group_id) using GET Groups/{id}.

        Layered like ``Users.refresh()``: it calls the public ``get_group()``, which
        calls the endpoint wrapper.
        """
        if group_id:
            self.group_id = group_id
        if not self.group_id:
            raise ValueError("refresh() requires group_id (passed or already set)")

        self.attributes = self.get_group(self.group_id)
        return self.attributes

    def _require_attributes(self) -> Dict[str, Any]:
        """Ensure attributes are loaded (via refresh) before using helpers that read group fields."""
        if self.attributes:
            return self.attributes
        if self.group_id:
            return self.refresh()
        raise ValueError("Group attributes not loaded and no group_id set (call refresh() or bind a group_id).")

    @property
    def display_name(self) -> str:
        """The group's SCIM ``displayName`` (loaded lazily)."""
        return self._require_attributes().get("displayName", "")

    @property
    def members(self) -> List[Dict[str, str]]:
        """The group's members as ``{'value': <user id>, 'display': <name>}`` dicts (loaded lazily)."""
        return self._require_attributes().get("members", []) or []

    # ---------- endpoint wrappers (only these call _scim_request) ----------

    def _scim_groups_list(self, *, count: int = 1000, start_index: Optional[int] = None) -> ScimResponse:
        """
        Wrapper for GET Groups (paginated).
        Accepts pagination params as query parameters according to Slack SCIM docs.
        """
        params: Dict[str, Any] = {"count": count}   # Number or records to return at a time. Maximum is 1000 https://api.slack.com/changelog/2019-06-have-scim-will-paginate#what
        if start_index is not None:
            params["startIndex"] = start_index
        return self._scim_request(path="Groups", method="GET", params=params)   # https://docs.slack.dev/reference/scim-api/#get-groups

    def _scim_group_get(self, group_id: str, *, count: Optional[int] = None, start_index: Optional[int] = None) -> ScimResponse:
        """
        Wrapper for GET Groups/{id}.

        count/start_index page over the group's *members* sub-list, which matters for
        groups larger than the server-side page size.
        """
        validate_scim_id(group_id, "group_id")
        params: Dict[str, Any] = {}
        if count is not None:
            params["count"] = count
        if start_index is not None:
            params["startIndex"] = start_index
        # Pass params only when set, so the default call is byte-for-byte the legacy request.
        return self._scim_request(path=f"Groups/{group_id}", method="GET", params=params or None)      # https://docs.slack.dev/reference/scim-api/#get-groups-id

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
            scim_resp = self._scim_groups_list(count=fetch_count, start_index=start_index)
            resp = scim_resp.data

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

    def get_group(self, group_id: Optional[str] = None, *, fetch_count: int = 1000) -> Dict[str, Any]:
        """
        Return the full SCIM record for a single group (GET Groups/{id}).

        One call yields both ``displayName`` and ``members``, so callers that need
        the name do not have to pay for a second request. The complete payload is
        returned (``id``, ``displayName``, ``members``, ``meta``, ``schemas``, ...) so
        new SCIM fields are reachable without adding a method here.

        When the response reports a ``totalResults`` larger than the members returned,
        the remaining member pages are fetched and merged, so large groups are not
        silently truncated.

        Raises:
            requests.HTTPError on non-2xx responses.
        """
        gid = self._resolve_group_id(group_id)

        # First request sends no pagination params, so it is identical to the legacy call.
        # Copy so callers mutating the result cannot corrupt our cached attributes.
        group = dict(self._scim_group_get(gid).data)
        members: List[Dict[str, str]] = list(group.get("members") or [])

        # totalResults is only present when the server actually paged the members;
        # when it is absent the single response is complete and we skip the loop.
        total_results = group.get("totalResults")
        if total_results is not None:
            while len(members) < int(total_results):
                # SCIM startIndex is 1-based, and the server chooses the first page size,
                # so derive the cursor from what we already have rather than from fetch_count.
                start_index = len(members) + 1
                page_members = self._scim_group_get(gid, count=fetch_count, start_index=start_index).data.get("members") or []
                # An empty page means the server has nothing more; stop rather than loop forever.
                if not page_members:
                    break
                members.extend(page_members)

        group["members"] = members
        return group

    def get_members(self, group_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Return group members via SCIM (GET Groups/{id}) as a list of dicts `{'value': <user_id>, 'display': <name>}`.

        Composes on ``get_group()``; the cached attributes are reused when they already
        describe the requested group, so property access and this method share one call.

        This module is SCIM-only. For Slack-native usergroups, see
        ``Usergroups.get_members()`` in ``usergroups.py``.
        """
        gid = self._resolve_group_id(group_id)
        if self.attributes and self.attributes.get("id") == gid:
            return self.attributes.get("members", []) or []
        return self.get_group(gid).get("members", []) or []

    def is_member(self, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        Return True if ``user_id`` is a member of ``group_id`` (via SCIM).

        Higher-level convenience that composes on ``get_members()``.
        Preserves legacy semantics (scans the members list).

        Each call fetches the group unless its attributes are already cached, so when
        testing many users bind the group once (or hoist ``get_members()`` out of the loop).
        """
        members = self.get_members(group_id=group_id)
        for member in members:
            # member dicts historically had 'value' for id
            if member.get("value") == user_id:
                return True
        return False
