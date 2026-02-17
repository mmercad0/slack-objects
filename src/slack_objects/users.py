from __future__ import annotations

"""
slack_objects.users
==================

Users helper for the `slack-objects` package.

Goals:
- Factory-friendly: `users = slack.users()` or `users = slack.users("U123")`
- Modular internals: public methods call *wrapper methods*; wrapper methods are the only place
  that directly call Slack Web/Admin APIs (via SlackApiCaller) or SCIM (via requests).
- Testable: wrapper methods are easy to fake/mocking; SCIM uses an injectable requests.Session.

This module intentionally covers only user-related operations and helpers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence, Union, List

import requests
from slack_sdk.errors import SlackApiError

from .base import SlackObjectBase, safe_error_context
from .config import RateTier, USER_ID_RE
from .scim_base import ScimMixin, ScimResponse, validate_scim_id

@dataclass
class Users(ScimMixin, SlackObjectBase):
    """
    Users domain helper.

    Factory-style usage:
        slack = SlackObjectsClient(cfg)
        users = slack.users()           # unbound
        alice = slack.users("U123")     # bound to user_id

    Notes:
    - `user_id` is optional. If you call methods that need a user, they will require a bound
      user_id or a passed user_id.
    - `attributes` are loaded lazily via `_require_attributes()` on first access; many helpers read from this cache.
    """
    user_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Heuristic label used historically to identify contingent workers
    cw_label: str = "[External]"

    # Optional requests session (handy for unit tests and connection pooling)
    scim_session: requests.Session = field(default_factory=requests.Session, repr=False)


    # ---------- factory helpers ----------

    def with_user(self, user_id: str) -> "Users":
        """
        Return a new Users instance bound to user_id, sharing cfg/client/logger/api.
        """
        return Users(
            cfg=self.cfg,
            client=self.client,
            logger=self.logger,
            api=self.api,
            user_id=user_id,
            scim_session=self.scim_session,
        )

    # ---------- attribute lifecycle ----------

    def refresh(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Refresh attributes for user_id (or self.user_id) using users.info.

        This method is intentionally layered: it calls `get_user_info()`, which calls the
        underlying endpoint wrapper.
        """
        if user_id:
            self.user_id = user_id
        if not self.user_id:
            raise ValueError("refresh() requires user_id (passed or already set)")

        resp = self.get_user_info(self.user_id)
        if not resp.get("ok"):
            raise RuntimeError(f"Users.get_user_info() failed: {safe_error_context(resp)}")

        self.attributes = resp.get("user") or {}
        return self.attributes

    def _require_attributes(self) -> Dict[str, Any]:
        """
        Ensure attributes are loaded (via refresh) before using helpers that rely on profile fields.
        """
        if self.attributes:
            return self.attributes
        if self.user_id:
            return self.refresh()
        raise ValueError("User attributes not loaded and no user_id set (call refresh() or bind a user_id).")

    # ============================================================
    # Slack Web/Admin API wrapper layer
    # ============================================================
    # Only these methods should call `self.api.call(...)` directly.
    # Everything else should call these wrappers.

    def _users_info(self, user_id: str) -> Dict[str, Any]:
        """Wrapper for users.info."""
        return self.api.call(self.client, "users.info", rate_tier=RateTier.TIER_4, user=user_id)

    def _users_lookup_by_email(self, email: str) -> Dict[str, Any]:
        """Wrapper for users.lookupByEmail."""
        return self.api.call(self.client, "users.lookupByEmail", rate_tier=RateTier.TIER_3, email=email)

    def _users_profile_get(self, user_id: str) -> Dict[str, Any]:
        """Wrapper for users.profile.get."""
        return self.api.call(self.client, "users.profile.get", rate_tier=RateTier.TIER_4, user=user_id)

    def _users_profile_set_name_value(self, user_id: str, field_id: str, new_value: str) -> Dict[str, Any]:
        """
        Wrapper for users.profile.set using legacy name/value style.

        Note: Slack's recommended pattern can also be "profile": {...}. If you switch later,
        you only need to update this wrapper.
        """
        return self.api.call(
            self.client,
            "users.profile.set",
            rate_tier=RateTier.TIER_3,
            user=user_id,
            name=field_id,
            value=new_value,
        )

    def _admin_users_invite(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for admin.users.invite."""
        return self.api.call(self.client, "admin.users.invite", rate_tier=RateTier.TIER_2, **payload)

    def _admin_users_session_reset(self, user_id: str) -> Dict[str, Any]:
        """Wrapper for admin.users.session.reset."""
        return self.api.call(self.client, "admin.users.session.reset", rate_tier=RateTier.TIER_2, user_id=user_id)

    def _admin_users_assign(self, user_id: str, team_id: str) -> Dict[str, Any]:
        """Wrapper for admin.users.assign."""
        return self.api.call(self.client, "admin.users.assign", rate_tier=RateTier.TIER_2, user_id=user_id, team_id=team_id)

    def _admin_users_remove(self, user_id: str, team_id: str) -> Dict[str, Any]:
        """Wrapper for admin.users.remove."""
        return self.api.call(self.client, "admin.users.remove", rate_tier=RateTier.TIER_2, user_id=user_id, team_id=team_id)

    def _admin_conversations_invite(self, user_ids: Sequence[str], channel_id: str) -> Dict[str, Any]:
        """Wrapper for admin.conversations.invite."""
        return self.api.call(
            self.client,
            "admin.conversations.invite",
            rate_tier=RateTier.TIER_2,
            user_ids=list(user_ids),
            channel_id=channel_id,
        )

    def _conversations_kick(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Wrapper for conversations.kick."""
        return self.api.call(self.client, "conversations.kick", rate_tier=RateTier.TIER_3, user=user_id, channel=channel_id)

    def _admin_users_set_expiration(self, *, user_id: str, expiration_ts: int, workspace_id: str = "") -> Dict[str, Any]:
        """Wrapper for admin.users.setExpiration."""
        payload: Dict[str, Any] = {
            "expiration_ts": expiration_ts,
            "user_id": user_id,
        }
        if workspace_id:
            payload["team_id"] = workspace_id

        return self.api.call(
            self.client,
            "admin.users.setExpiration",
            rate_tier=RateTier.TIER_2,
            **payload,
        )

    def _discovery_user_conversations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for discovery.user.conversations."""
        return self.api.call(self.client, "discovery.user.conversations", rate_tier=RateTier.TIER_D, **payload)

    # ============================================================
    # Public Slack Web/Admin methods (call wrappers above)
    # ============================================================

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Public method for users.info (calls wrapper)."""
        return self._users_info(user_id)

    def lookup_by_email(self, email: str) -> Dict[str, Any]:
        """Public method for users.lookupByEmail (calls wrapper)."""
        return self._users_lookup_by_email(email)

    def get_user_id_from_email(self, email: str) -> str:
        """
        Convenience wrapper that returns only the Slack user ID for an email.

        Legacy behavior returned '' on miss; keep that for compatibility.
        """
        resp = self.lookup_by_email(email)
        if resp.get("ok"):
            return (resp.get("user") or {}).get("id", "") or ""
        return ""

    def get_user_profile(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch user profile (users.profile.get)."""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("get_user_profile requires user_id (passed or bound)")
        return self._users_profile_get(uid)

    def set_user_profile_field(self, field_id: str, new_value: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Update a single profile field using the legacy name/value style (users.profile.set)."""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("set_user_profile_field requires user_id (passed or bound)")
        return self._users_profile_set_name_value(uid, field_id, new_value)

    # ---------- classification helpers ----------

    def is_contingent_worker(self) -> bool:
        """Return True if the user's name/display_name contains the CW label."""
        attrs = self._require_attributes()
        real_name = str(attrs.get("real_name", ""))
        display_name = str((attrs.get("profile") or {}).get("display_name", ""))
        return (self.cw_label in real_name) or (self.cw_label in display_name)

    def is_guest(self) -> bool:
        """Return True for restricted or ultra-restricted guest accounts."""
        attrs = self._require_attributes()
        return bool(attrs.get("is_restricted") or attrs.get("is_ultra_restricted"))

    def is_active(self) -> bool:
        """Return True if the user account is not deactivated (deleted)."""
        attrs = self._require_attributes()
        return not bool(attrs.get("deleted", False))

    # ---------- auth helpers ----------

    def is_user_authorized(self, service_name: str, auth_level: str = "read") -> bool:
        """
        Determine whether the bound user is authorized for a service.

        Authorization is based on IdP group membership, using policy defined in cfg.

        Expected config shape:
            cfg.auth_idp_groups_read_access:  dict[str, list[str]]
            cfg.auth_idp_groups_write_access: dict[str, list[str]]

        This method intentionally delegates all membership checks to IDP_groups.
        """
        if not self.user_id:
            raise ValueError("is_user_authorized requires a bound user_id")

        # Resolve policy
        if auth_level == "write":
            group_ids = getattr(self.cfg, "auth_idp_groups_write_access", {}).get(service_name, [])
        else:
            group_ids = getattr(self.cfg, "auth_idp_groups_read_access", {}).get(service_name, [])

        if not group_ids:
            return False

        # Lazy import to avoid circular dependencies
        from .idp_groups import IDP_groups

        idp = IDP_groups(
            cfg=self.cfg,
            client=self.client,
            logger=self.logger,
            api=self.api,
        )

        for group_id in group_ids:
            if idp.is_member(user_id=self.user_id, group_id=group_id):
                return True

        return False


    # ---------- admin api helpers ----------

    def invite_user(
        self,
        *,
        channel_ids: Union[str, Sequence[str]],
        email: str,
        team_id: str,
        email_password_policy_enabled: bool = False,
    ) -> Dict[str, Any]:
        """
        admin.users.invite

        Accepts either "C1,C2" or ["C1", "C2"].

        If cfg.user_token exists, we pass it explicitly in the payload (matches your legacy intent).
        """
        channel_ids_str = ",".join(channel_ids) if isinstance(channel_ids, (list, tuple, set)) else channel_ids

        payload: Dict[str, Any] = {
            "channel_ids": channel_ids_str,
            "email": email,
            "team_id": team_id,
            "email_password_policy_enabled": email_password_policy_enabled,
        }

        if getattr(self.cfg, "user_token", None):
            payload["token"] = self.cfg.user_token

        return self._admin_users_invite(payload)

    def wipe_all_sessions(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """admin.users.session.reset"""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("wipe_all_sessions requires user_id (passed or bound)")
        return self._admin_users_session_reset(uid)

    def add_to_workspace(self, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """admin.users.assign"""
        return self._admin_users_assign(user_id=user_id, team_id=workspace_id)

    def remove_from_workspace(self, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """admin.users.remove"""
        return self._admin_users_remove(user_id=user_id, team_id=workspace_id)

    def add_to_conversation(self, user_ids: Sequence[str], channel_id: str) -> Dict[str, Any]:
        """admin.conversations.invite"""
        return self._admin_conversations_invite(user_ids=user_ids, channel_id=channel_id)

    def remove_from_conversation(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """conversations.kick"""
        return self._conversations_kick(user_id=user_id, channel_id=channel_id)

    def set_guest_expiration_date(self, expiration_date: str, user_id: Optional[str] = None, workspace_id: str = "") -> Dict[str, Any]:
        """
        Set the expiration date for a guest user (admin.users.setExpiration).

        Args:
            expiration_date: A date string accepted by PC_Utils.Datetime.Datetime.date_to_epoch(). Default is %Y-%m-%d
            user_id: Optional override; if omitted, uses the bound self.user_id
            workspace_id: Optional team/workspace ID for multi-workspace orgs
        """
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("set_guest_expiration_date requires user_id (passed or bound)")

        # Lazy import: keeps slack-objects importable even if PC_Utils isn't installed,
        # as long as this method isn't called.
        from PC_Utils.Datetime import Datetime

        expiration_ts = Datetime.date_to_epoch(expiration_date)
        return self._admin_users_set_expiration(user_id=uid, expiration_ts=expiration_ts, workspace_id=workspace_id)


    # ---------- discovery helper ----------

    def get_channels(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        discovery.user.conversations, paginated by offset.

        Returns:
            - If errors occur: a list of error dicts (legacy behavior preserved)
            - Else: list of channels (active_only controls whether it filters to channels with date_left == 0)
        """
        current_channels: List[Dict[str, Any]] = []
        all_channels: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        payload: Dict[str, Any] = {"user": user_id, "limit": 1000}

        while True:
            resp = self._discovery_user_conversations(payload)

            if not resp.get("ok"):
                errors.append({"message": resp.get("error", "unknown_error"), "payload": dict(payload)})
                break

            channels = resp.get("channels") or []
            for ch in channels:
                all_channels.append(ch)
                if ch.get("date_left", 0) == 0:
                    current_channels.append(ch)

            offset = resp.get("offset")
            if offset:
                payload["offset"] = offset
            else:
                break

        if errors:
            return errors  # preserve legacy behavior

        return current_channels if active_only else all_channels

    # ============================================================
    # SCIM public methods (use inherited ScimMixin._scim_request)
    # ============================================================

    # ---------- SCIM search primitives ----------

    def scim_search_user_by_email(self, email: str) -> ScimResponse:
        """
        SCIM GET Users with filter: emails.value eq "<email>".

        Returns active AND deactivated users — unlike the Web API's
        users.lookupByEmail which only returns active users.
        """
        return self._scim_request(
            path="Users",
            method="GET",
            params={"filter": f'emails.value eq "{email}"'},
        )

    def scim_search_user_by_username(self, username: str) -> ScimResponse:
        """
        SCIM GET Users with filter: userName eq "<username>".

        Returns active AND deactivated users.
        """
        return self._scim_request(
            path="Users",
            method="GET",
            params={"filter": f'userName eq "{username}"'},
        )

    # ---------- identifier resolution ----------

    @staticmethod
    def _looks_like_user_id(value: str) -> bool:
        """Return True if *value* matches the Slack user/bot ID pattern (U… or W…)."""
        return bool(USER_ID_RE.match(value))

    @staticmethod
    def _first_scim_user_id(scim_resp: ScimResponse) -> str:
        """
        Extract the user ID from the first resource in a SCIM list response.

        Returns ``""`` when no resources are present.
        """
        resources = scim_resp.data.get("Resources") or []
        if resources:
            return resources[0].get("id", "")
        return ""

    def resolve_user_id(self, identifier: str) -> str:
        """
        Resolve a flexible user identifier to a Slack user ID.

        Accepts any of:
        - A Slack user ID (e.g. ``"U01ABC123"``)
        - An email address (e.g. ``"alice@example.com"``)
        - A ``@username`` handle (e.g. ``"@alice"``)

        Resolution strategy:
        1. If the identifier matches the Slack user ID pattern (``^[UW][A-Z0-9]+$``),
           return it as-is.
        2. If it contains ``@`` and looks like an email, try the Web API
           ``users.lookupByEmail`` first (fast, but only finds active users).
           On miss or SlackApiError, fall back to SCIM email filter search.
        3. If it starts with ``@``, strip the prefix and search SCIM by ``userName``.
        4. Otherwise treat it as a bare username and search SCIM.

        Returns:
            The Slack user ID string.

        Raises:
            LookupError: when no matching user can be found via any strategy.
            ValueError: when *identifier* is empty.
        """
        if not identifier or not identifier.strip():
            raise ValueError("identifier must not be empty")

        identifier = identifier.strip()

        # ── 1. Slack user ID ──────────────────────────────────────
        if self._looks_like_user_id(identifier):
            return identifier

        # ── 2. Email address ──────────────────────────────────────
        if "@" in identifier and not identifier.startswith("@"):
            # Fast path: Web API (active users only)
            try:
                uid = self.get_user_id_from_email(identifier)
                if uid:
                    return uid
            except SlackApiError:
                pass  # expected for deactivated / not-found users

            # Slow path: SCIM (active + deactivated)
            self.logger.info("Web API miss for %s — falling back to SCIM search", identifier)
            uid = self._first_scim_user_id(self.scim_search_user_by_email(identifier))
            if uid:
                return uid

            raise LookupError(f"No user found for email: {identifier}")

        # ── 3. @username handle ───────────────────────────────────
        if identifier.startswith("@"):
            username = identifier.lstrip("@")
            uid = self._first_scim_user_id(self.scim_search_user_by_username(username))
            if uid:
                return uid

            raise LookupError(f"No user found for username: @{username}")

        # ── 4. Bare string — try as username via SCIM ─────────────
        uid = self._first_scim_user_id(self.scim_search_user_by_username(identifier))
        if uid:
            return uid

        raise LookupError(f"No user found for identifier: {identifier}")

    # ---------- SCIM CRUD ----------

    def scim_create_user(self, username: str, email: str) -> ScimResponse:
        """SCIM POST Users"""
        scim_version = self.cfg.scim_version
        if scim_version == "v2":
            payload: Dict[str, Any] = {
                "schemas": [
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:extension:slack:profile:2.0:User",
                ],
                "userName": username,
                "emails": [{"value": email}],
            }
        elif scim_version == "v1":
            payload = {
                "schemas": [
                    "urn:scim:schemas:core:1.0",
                    "urn:scim:schemas:extension:enterprise:1.0",
                    "urn:scim:schemas:extension:slack:profile:1.0",
                ],
                "userName": username,
                "emails": [{"value": email}],
            }
        else:
            raise NotImplementedError(f"Invalid SCIM version: {scim_version}")

        return self._scim_request(path="Users", method="POST", payload=payload)

    def scim_deactivate_user(self, user_id: str) -> ScimResponse:
        """SCIM DELETE Users/<id>"""
        validate_scim_id(user_id, "user_id")
        return self._scim_request(path=f"Users/{user_id}", method="DELETE")

    def scim_reactivate_user(self, user_id: Optional[str] = None) -> ScimResponse:
        """Reactivate a deactivated user via SCIM PATCH Users/<id>."""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("scim_reactivate_user requires user_id (passed or bound)")
        validate_scim_id(uid, "user_id")

        scim_version = self.cfg.scim_version
        if scim_version == "v2":
            payload: Dict[str, Any] = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "replace", "path": "active", "value": True}],
            }
        elif scim_version == "v1":
            payload = {
                "schemas": ["urn:scim:schemas:core:1.0"],
                "active": True,
            }
        else:
            raise NotImplementedError(f"Invalid SCIM version: {scim_version}")

        return self._scim_request(path=f"Users/{uid}", method="PATCH", payload=payload)

    def scim_update_user_attribute(
        self,
        *,
        user_id: str,
        attribute: str,
        new_value: Any,
    ) -> ScimResponse:
        """SCIM PATCH Users/<id>"""
        validate_scim_id(user_id, "user_id")

        scim_version = self.cfg.scim_version
        if scim_version == "v2":
            payload = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "replace", "path": attribute, "value": new_value}],
            }
        elif scim_version == "v1":
            payload = {"schemas": ["urn:scim:schemas:core:1.0"], attribute: new_value}
        else:
            raise NotImplementedError(f"Invalid SCIM version: {scim_version}")

        return self._scim_request(path=f"Users/{user_id}", method="PATCH", payload=payload)

    def make_multi_channel_guest(self, user_id: Optional[str] = None) -> ScimResponse:
        """Convert a user to a multi-channel guest via SCIM PATCH."""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("make_multi_channel_guest requires user_id (passed or bound)")
        validate_scim_id(uid, "user_id")

        scim_version = self.cfg.scim_version
        if scim_version == "v2":
            payload = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "path": "urn:ietf:params:scim:schemas:extension:slack:guest:2.0:User",
                        "op": "add",
                        "value": {"type": "multi"},
                    }
                ],
            }
        elif scim_version == "v1":
            payload = {
                "schemas": [
                    "urn:scim:schemas:core:1.0",
                    "urn:scim:schemas:extension:enterprise:1.0",
                    "urn:scim:schemas:extension:slack:guest:1.0",
                ],
                "urn:scim:schemas:extension:slack:guest:1.0": {"type": "multi"},
            }
        else:
            raise NotImplementedError(f"Invalid SCIM version: {scim_version}")

        return self._scim_request(path=f"Users/{uid}", method="PATCH", payload=payload)
