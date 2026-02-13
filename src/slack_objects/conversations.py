from __future__ import annotations

"""
slack_objects.conversations
==========================

Conversations (Channels) helper for the `slack-objects` package.

This module provides methods for working with Slack conversations (public channels, private channels,
and (in Grid) enterprise conversations), including:
- Fetching conversation attributes (`conversations.info`)
- Searching by name (`admin.conversations.search`)
- Archiving (`admin.conversations.archive`)
- Sharing/moving across workspaces (`admin.conversations.setTeams`)
- Restricting access via IdP group allowlists (`admin.conversations.restrictAccess.addGroup`)
- Reading history (`conversations.history`)
- Listing members via Discovery (`discovery.conversations.members`)

Design goals:
- Factory-friendly:
    slack = SlackObjectsClient(cfg)
    convos = slack.conversations()
    general = slack.conversations("C123")
- Modular:
    Only *endpoint wrapper* methods call self.api.call(...).
    Public methods call wrappers.
- Practical:
    conversations.info sometimes needs a user token to see private channels not joined by the bot.
    This class will attempt user token (if provided) and fallback to bot token.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


from .base import SlackObjectBase, safe_error_context
from .config import RateTier
from .messages import Messages

@dataclass
class Conversations(SlackObjectBase):
    """
    Conversations domain helper.

    Factory-style usage:
        slack = SlackObjectsClient(cfg)
        convos = slack.conversations()           # unbound
        general = slack.conversations("C123")    # bound to channel_id

    Notes:
    - channel_id is optional. Methods that need it require a passed channel_id or a bound instance.
    - attributes cache is populated via refresh().
    """
    channel_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    # ---------- factory helpers ----------

    def with_conversation(self, channel_id: str) -> "Conversations":
        """Return a new Conversations instance bound to channel_id, sharing cfg/client/logger/api."""
        return Conversations(cfg=self.cfg, client=self.client, logger=self.logger, api=self.api, channel_id=channel_id)

    # ---------- attribute lifecycle ----------

    def refresh(self, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Refresh cached attributes for the conversation via conversations.info.

        This is layered/modular: refresh() calls get_conversation_info(), which calls the wrapper.
        """
        if channel_id:
            self.channel_id = channel_id
        if not self.channel_id:
            raise ValueError("refresh() requires channel_id (passed or already set)")

        resp = self.get_conversation_info(self.channel_id)
        if not resp.get("ok"):
            raise RuntimeError(f"Conversations.get_conversation_info() failed: {safe_error_context(resp)}")

        self.attributes = resp.get("channel") or {}
        return self.attributes

    def _require_attributes(self) -> Dict[str, Any]:
        """Ensure attributes are loaded before helpers rely on them."""
        if self.attributes:
            return self.attributes
        if self.channel_id:
            return self.refresh()
        raise ValueError("Conversation attributes not loaded and no channel_id set (call refresh() or bind channel_id).")

    # ============================================================
    # Slack Web/Admin/Discovery API wrapper layer
    # ============================================================
    # Only these methods should call `self.api.call(...)` directly.

    def _conversations_info(self, channel_id: str, *, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Wrapper for conversations.info.

        If a user token exists in cfg, we try it first because bot tokens often cannot see
        private channels the bot is not a member of. This mirrors your PCbot behavior/fallback. :contentReference[oaicite:3]{index=3}
        """
        kwargs: Dict[str, Any] = {"channel": channel_id}

        # Token override handling:
        # - If explicit token provided: use it
        # - Else if cfg.user_token exists: try user token first, fallback to default client token
        if token:
            kwargs["token"] = token
            return self.api.call(self.client, "conversations.info", rate_tier=RateTier.TIER_3, **kwargs)

        if getattr(self.cfg, "user_token", None):
            # First attempt with user_token
            kwargs_user = dict(kwargs)
            kwargs_user["token"] = self.cfg.user_token
            resp = self.api.call(self.client, "conversations.info", rate_tier=RateTier.TIER_3, **kwargs_user)
            if resp.get("ok"):
                return resp

            # Fallback: bot token / default client token
            return self.api.call(self.client, "conversations.info", rate_tier=RateTier.TIER_3, **kwargs)

        # Default
        return self.api.call(self.client, "conversations.info", rate_tier=RateTier.TIER_3, **kwargs)

    def _conversations_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for conversations.history."""
        return self.api.call(self.client, "conversations.history", rate_tier=RateTier.TIER_3, **payload)

    def _conversations_replies(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for conversations.replies. Used to fetch thread replies for a parent message."""
        return self.api.call(self.client, "conversations.replies", rate_tier=RateTier.TIER_3, **payload)

    def _admin_conversations_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for admin.conversations.search (max limit appears to be 20 in legacy). :contentReference[oaicite:4]{index=4}"""
        return self.api.call(self.client, "admin.conversations.search", rate_tier=RateTier.TIER_2, **payload)

    def _admin_conversations_archive(self, channel_id: str) -> Dict[str, Any]:
        """Wrapper for admin.conversations.archive."""
        return self.api.call(
            self.client, "admin.conversations.archive", rate_tier=RateTier.TIER_2, channel_id=channel_id
        )

    def _admin_conversations_set_teams(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for admin.conversations.setTeams (share/move). :contentReference[oaicite:5]{index=5}"""
        return self.api.call(self.client, "admin.conversations.setTeams", rate_tier=RateTier.TIER_2, **payload)

    def _admin_conversations_restrict_access_add_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for admin.conversations.restrictAccess.addGroup. :contentReference[oaicite:6]{index=6}"""
        return self.api.call(
            self.client,
            "admin.conversations.restrictAccess.addGroup",
            rate_tier=RateTier.TIER_2,
            **payload,
        )

    def _discovery_conversations_members(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for discovery.conversations.members. :contentReference[oaicite:7]{index=7}"""
        return self.api.call(self.client, "discovery.conversations.members", rate_tier=RateTier.TIER_3, **payload)

    # ============================================================
    # Public methods (call wrappers above)
    # ============================================================

    def messages(self, channel_id: Optional[str] = None) -> Messages:
        """
        Return a Messages helper bound to a channel.

        Why this exists:
        - Legacy Conversations/Channels relied on Messages for history + threads.
        - Keeps Conversations focused on channel/admin/discovery operations.
        """
        cid = channel_id or self.channel_id
        if not cid:
            raise ValueError("messages() requires channel_id (passed or bound).")
        return Messages(cfg=self.cfg, client=self.client, logger=self.logger, api=self.api, channel_id=cid)

    def get_conversation_info(self, channel_id: str) -> Dict[str, Any]:
        """Public method for conversations.info (calls wrapper)."""
        return self._conversations_info(channel_id)

    def is_private(self) -> bool:
        """
        Returns True if the conversation is private.

        Uses cached attributes if available; otherwise raises unless bound (then refreshes).
        """
        attrs = self._require_attributes()
        return bool(attrs.get("is_private", False))

    def get_conversation_name(self, channel_id: str = "") -> str:
        """
        Returns conversation name for self (cached) or for the provided channel_id (fresh lookup).

        Mirrors legacy behavior: when channel_id is supplied, we fetch fresh attributes rather than
        trusting local cache. :contentReference[oaicite:8]{index=8}
        """
        if channel_id:
            info = self.get_conversation_info(channel_id)
            if info.get("ok") and info.get("channel") and "name" in info["channel"]:
                return str(info["channel"]["name"])
            raise RuntimeError(f"Could not get name for channel_id={channel_id}: {info}")

        attrs = self._require_attributes()
        if "name" in attrs:
            return str(attrs["name"])
        raise RuntimeError(f"No name found in cached attributes: {attrs}")

    def get_conversation_ids_from_name(
        self,
        channel_name: str,
        *,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
    ) -> List[str]:
        """
        Search for conversations by name and return matching IDs (exact name match).

        Uses admin.conversations.search (legacy approach). :contentReference[oaicite:9]{index=9}

        Notes:
        - Slack search is "contains" so we filter down to exact matches.
        - If workspace_id is provided, we scope the search (team_ids).
        - workspace_name resolution is intentionally omitted here to keep this class focused;
          do it via Workspaces helper (slack.workspaces()) and pass workspace_id.
        """
        if workspace_name and not workspace_id:
            raise ValueError("workspace_name resolution should be done via Workspaces; pass workspace_id instead.")

        limit = 20  # legacy note: admin.conversations.search max appears to be 20 :contentReference[oaicite:10]{index=10}
        payload: Dict[str, Any] = {"limit": limit, "query": channel_name}
        if workspace_id:
            payload["team_ids"] = workspace_id

        found_tmp: List[Dict[str, Any]] = []
        found: List[str] = []

        while True:
            resp = self._admin_conversations_search(payload)
            if not resp.get("ok"):
                # keep it explicit; scripts can catch and decide
                raise RuntimeError(f"admin.conversations.search failed: {resp}")

            found_tmp.extend(resp.get("conversations") or [])

            next_cursor = resp.get("next_cursor") or ""
            if not next_cursor:
                break
            payload["cursor"] = next_cursor

        for convo in found_tmp:
            if convo.get("name") == channel_name and convo.get("id"):
                found.append(convo["id"])

        return found

    def archive(self, channel_id: Optional[str] = None) -> bool:
        """
        Archive a conversation via admin.conversations.archive.

        Returns True if archived or already archived.
        """
        cid = channel_id or self.channel_id
        if not cid:
            raise ValueError("archive() requires channel_id (passed or bound)")

        resp = self._admin_conversations_archive(cid)
        if resp.get("ok"):
            return True

        # legacy behavior treated already_archived as success :contentReference[oaicite:11]{index=11}
        if resp.get("error") == "already_archived":
            return True

        return False

    def share_to_workspaces(
        self,
        target_ws_id: str,
        *,
        channel_id: Optional[str] = None,
        source_ws_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Share a conversation to additional workspaces via admin.conversations.setTeams.

        This mirrors your legacy `shareChannel` behavior. :contentReference[oaicite:12]{index=12}

        - If source_ws_id is provided: setTeams includes both source and target (team_id + target_team_ids)
        - Else: target_team_ids includes only target
        """
        cid = channel_id or self.channel_id
        if not cid:
            raise ValueError("share_to_workspaces() requires channel_id (passed or bound)")

        payload: Dict[str, Any] = {"channel_id": cid}

        if source_ws_id:
            payload["team_id"] = source_ws_id
            payload["target_team_ids"] = f"{source_ws_id},{target_ws_id}"
        else:
            payload["target_team_ids"] = target_ws_id

        return self._admin_conversations_set_teams(payload)

    def move_to_workspace(
        self,
        channel_id: str,
        source_ws_id: str,
        target_ws_id: str,
    ) -> Dict[str, Any]:
        """
        Move a conversation from one workspace to another via two-step setTeams.

        Matches your legacy `moveChannel` flow:
        1) setTeams with source + target
        2) setTeams with target only (removes from source) :contentReference[oaicite:13]{index=13}
        """
        # Step 1
        payload_1 = {"channel_id": channel_id, "target_team_ids": f"{source_ws_id},{target_ws_id}"}
        resp1 = self._admin_conversations_set_teams(payload_1)
        if not resp1.get("ok"):
            return resp1

        # Step 2
        payload_2 = {"channel_id": channel_id, "target_team_ids": target_ws_id}
        resp2 = self._admin_conversations_set_teams(payload_2)
        return resp2

    def restrict_access_add_group(
        self,
        *,
        channel_id: str,
        group_id: str,
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        """
        Add an IdP allowlist group to a (private) conversation.

        Wrapper around admin.conversations.restrictAccess.addGroup. :contentReference[oaicite:14]{index=14}

        workspace_id/team_id is required for some single-workspace conversations.
        """
        payload: Dict[str, Any] = {"channel_id": channel_id, "group_id": group_id}
        if workspace_id:
            payload["team_id"] = workspace_id
        return self._admin_conversations_restrict_access_add_group(payload)

    def get_members(
        self,
        *,
        channel_id: Optional[str] = None,
        workspace_id: str = "",
        include_members_who_left: bool = False,
    ) -> List[str]:
        """
        Return member IDs for a conversation via discovery.conversations.members.

        Mirrors legacy: supports team context for single-workspace conversations and optional
        include_member_left. :contentReference[oaicite:15]{index=15}
        """
        cid = channel_id or self.channel_id
        if not cid:
            raise ValueError("get_members() requires channel_id (passed or bound)")

        payload: Dict[str, Any] = {"channel": cid, "limit": 1000}
        if workspace_id:
            payload["team"] = workspace_id
        if include_members_who_left:
            payload["include_member_left"] = True

        members: List[str] = []
        page = 0

        while True:
            page += 1
            resp = self._discovery_conversations_members(payload)
            if not resp.get("ok"):
                raise RuntimeError(f"discovery.conversations.members failed on page {page}: {resp}")

            members.extend(resp.get("members") or [])

            offset = resp.get("offset")
            if offset:
                payload["offset"] = offset
            else:
                break

        return members

    def get_messages(
        self,
        *,
        channel_id: Optional[str] = None,
        include_all_metadata: bool = False,
        limit: Optional[int] = None,
        inclusive: bool = True,
        latest: Optional[str] = None,
        oldest: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch conversation history.

        Delegates to Messages.get_messages() so message logic stays centralized in messages.py.
        """
        return self.messages(channel_id).get_messages(
            channel_id=channel_id,  # harmless redundancy; Messages will resolve the same channel_id
            include_all_metadata=include_all_metadata,
            limit=limit,
            inclusive=inclusive,
            latest=latest,
            oldest=oldest,
        )

    def get_message_threads(
        self,
        *,
        channel_id: Optional[str] = None,
        thread_ts: str,
        limit: Optional[int] = None,
        latest: Optional[str] = None,
        oldest: Optional[str] = None,
        inclusive: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch thread replies for a parent message.

        Delegates to Messages.get_message_threads() so thread logic stays centralized in messages.py.
        """
        return self.messages(channel_id).get_message_threads(
            channel_id=channel_id,
            thread_ts=thread_ts,
            limit=limit,
            latest=latest,
            oldest=oldest,
            inclusive=inclusive,
        )
