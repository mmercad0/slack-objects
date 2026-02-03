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

import json
import time
import requests

from .base import SlackObjectBase
from .config import RateTier


@dataclass
class ScimResponse:
    """
    Simple structured response for SCIM requests.

    SCIM responses are not Slack Web API responses (no `ok` boolean), so returning a consistent
    wrapper makes scripts/tests easier to write.
    """
    ok: bool
    status_code: int
    data: Dict[str, Any]
    text: str


@dataclass
class Users(SlackObjectBase):
    """
    Users domain helper.

    Factory-style usage:
        slack = SlackObjectsClient(cfg)
        users = slack.users()           # unbound
        alice = slack.users("U123")     # bound to user_id

    Notes:
    - `user_id` is optional. If you call methods that need a user, they will require a bound
      user_id or a passed user_id.
    - `attributes` are cached after `refresh()`; many helpers read from this cache.
    """
    user_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Heuristic label used historically to identify contingent workers
    cw_label: str = "[External]"

    # Optional requests session (handy for unit tests and connection pooling)
    scim_session: requests.Session = field(default_factory=requests.Session, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()

        # Eagerly load attributes if we have a user_id
        if self.user_id:
            # will raise RuntimeError if users.info fails
            self.refresh()


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
            raise RuntimeError(f"Users.get_user_info() failed: {resp}")

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

    def _discovery_user_conversations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for discovery.user.conversations."""
        return self.api.call(self.client, "discovery.user.conversations", rate_tier=RateTier.TIER_3, **payload)

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
    # SCIM (requests) - already modular via _scim_request
    # ============================================================

    def _scim_base_url(self, scim_version: str) -> str:
        """Return SCIM base URL, allowing config override."""
        if scim_version == "v2" and getattr(self.cfg, "scim_base_url_v2", None):
            return self.cfg.scim_base_url_v2.rstrip("/") + "/"
        if scim_version == "v1" and getattr(self.cfg, "scim_base_url_v1", None):
            return self.cfg.scim_base_url_v1.rstrip("/") + "/"
        return f"https://api.slack.com/scim/{scim_version}/"

    def _scim_request(
        self,
        *,
        path: str,
        method: str,
        payload: Optional[Dict[str, Any]] = None,
        scim_version: str = "v1",
        token: Optional[str] = None,
    ) -> ScimResponse:
        """
        Perform a SCIM REST request and return a structured response.

        Note: SCIM rate limiting is separate from Slack Web API rate limiting; we keep a small,
        conservative sleep here. If you later unify SCIM throttling with SlackApiCaller, you can
        remove this sleep.
        """
        tok = token or getattr(self.cfg, "scim_token", None)
        if not tok:
            raise ValueError("SCIM request requires cfg.scim_token (or token override)")

        # Simple pacing to avoid bursts (tweak as needed)
        time.sleep(float(RateTier.TIER_2))

        url = self._scim_base_url(scim_version) + path.lstrip("/")
        headers = {
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json; charset=utf-8",
        }

        resp = self.scim_session.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=json.dumps(payload) if payload is not None else None,
            timeout=getattr(self.cfg, "http_timeout_seconds", 30),
        )

        text = resp.text or ""
        try:
            data = resp.json() if text else {}
        except Exception:
            data = {}

        ok = resp.ok and (data.get("Errors") is None)
        return ScimResponse(ok=ok, status_code=resp.status_code, data=data, text=text)

    def scim_create_user(self, username: str, email: str, scim_version: str = "v1") -> ScimResponse:
        """SCIM POST Users"""
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

        return self._scim_request(path="Users", method="POST", payload=payload, scim_version=scim_version)

    def scim_deactivate_user(self, user_id: str, scim_version: str = "v1") -> ScimResponse:
        """SCIM DELETE Users/<id>"""
        return self._scim_request(path=f"Users/{user_id}", method="DELETE", scim_version=scim_version)

    def scim_update_user_attribute(
        self,
        *,
        user_id: str,
        attribute: str,
        new_value: Any,
        scim_version: str = "v2",
    ) -> ScimResponse:
        """SCIM PATCH Users/<id>"""
        if scim_version == "v2":
            payload = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "replace", "path": attribute, "value": new_value}],
            }
        elif scim_version == "v1":
            payload = {"schemas": ["urn:scim:schemas:core:1.0"], attribute: new_value}
        else:
            raise NotImplementedError(f"Invalid SCIM version: {scim_version}")

        return self._scim_request(path=f"Users/{user_id}", method="PATCH", payload=payload, scim_version=scim_version)

    def make_multi_channel_guest(self, user_id: Optional[str] = None, scim_version: str = "v1") -> ScimResponse:
        """Convert a user to a multi-channel guest via SCIM PATCH."""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("make_multi_channel_guest requires user_id (passed or bound)")

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

        return self._scim_request(path=f"Users/{uid}", method="PATCH", payload=payload, scim_version=scim_version)
