from __future__ import annotations

"""
slack_objects.messages
=====================

Messages helper for the `slack-objects` package.

Merged from two legacy implementations:

- PCbot legacy: chat.update + replace_message_block logic :contentReference[oaicite:2]{index=2}
- SlackAdmin legacy: chat.delete + getMessageThreads via conversations.replies pagination :contentReference[oaicite:3]{index=3}

Design goals:
- Factory-friendly:
    slack = SlackObjectsClient(cfg)
    msgs = slack.messages()                      # unbound
    msgs_c = slack.messages(channel_id="C123")   # bound to channel
    msg = slack.messages(channel_id="C123", ts="1700.12")   # bound to message
- Modular:
    Only endpoint wrapper methods call self.api.call(...)
- Practical:
    Provide common message operations: update/delete, thread replies, and block replacement.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import SlackObjectBase
from .config import RateTier


@dataclass
class Messages(SlackObjectBase):
    """
    Messages domain helper.

    Optional bindings:
    - channel_id: for channel-scoped message operations
    - ts: message timestamp (for update/delete/thread replies)
    - message: cached message payload (used by replace_message_block if blocks not provided)
    """
    channel_id: Optional[str] = None
    ts: Optional[str] = None
    message: Optional[Dict[str, Any]] = None

    # --------------------
    # Factory helpers
    # --------------------

    def with_channel(self, channel_id: str) -> "Messages":
        """Return a new Messages instance bound to channel_id, sharing cfg/client/logger/api."""
        return Messages(cfg=self.cfg, client=self.client, logger=self.logger, api=self.api, channel_id=channel_id)

    def with_message(self, channel_id: str, ts: str, message: Optional[Dict[str, Any]] = None) -> "Messages":
        """Return a new Messages instance bound to (channel_id, ts), optionally caching message payload."""
        return Messages(
            cfg=self.cfg,
            client=self.client,
            logger=self.logger,
            api=self.api,
            channel_id=channel_id,
            ts=ts,
            message=message,
        )

    # ============================================================
    # Endpoint wrapper layer (ONLY these call self.api.call directly)
    # ============================================================

    def _chat_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for chat.update."""
        return self.api.call(self.client, "chat.update", rate_tier=RateTier.TIER_3, **payload)

    def _chat_delete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for chat.delete."""
        return self.api.call(self.client, "chat.delete", rate_tier=RateTier.TIER_3, **payload)

    def _conversations_replies(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for conversations.replies (thread replies)."""
        return self.api.call(self.client, "conversations.replies", rate_tier=RateTier.TIER_3, **payload)

    def _conversations_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for conversations.history (channel history)."""
        return self.api.call(self.client, "conversations.history", rate_tier=RateTier.TIER_3, **payload)

    # ============================================================
    # Public operations
    # ============================================================

    def update_message(
        self,
        *,
        channel_id: Optional[str] = None,
        ts: Optional[str] = None,
        as_user: bool = True,
        text: str = "",
        blocks: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing message (chat.update).

        Merged from your PCbot legacy update_message method. :contentReference[oaicite:4]{index=4}

        Args:
            channel_id: channel containing the message (defaults to bound channel_id)
            ts: timestamp of the message (defaults to bound ts)
            as_user: Slack param; legacy default was True
            text: optional new text
            blocks: optional block kit payload
            attachments: optional attachments payload

        Returns:
            Slack Web API response dict.
        """
        cid = channel_id or self.channel_id
        mts = ts or self.ts
        if not cid or not mts:
            raise ValueError("update_message requires channel_id and ts (passed or bound).")

        payload: Dict[str, Any] = {"channel": cid, "ts": mts, "as_user": as_user}
        if text:
            payload["text"] = text
        if blocks is not None:
            payload["blocks"] = blocks
        if attachments is not None:
            payload["attachments"] = attachments

        resp = self._chat_update(payload)
        if not resp.get("ok"):
            self.logger.error("chat.update failed: %s", resp)
        return resp

    def delete_message(self, *, channel_id: Optional[str] = None, ts: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a message (chat.delete).

        Merged from your SlackAdmin legacy deleteMessage. :contentReference[oaicite:5]{index=5}
        """
        cid = channel_id or self.channel_id
        mts = ts or self.ts
        if not cid or not mts:
            raise ValueError("delete_message requires channel_id and ts (passed or bound).")

        resp = self._chat_delete({"channel": cid, "ts": mts})
        if not resp.get("ok"):
            self.logger.error("chat.delete failed: %s", resp)
        return resp

    def get_message_threads(
        self,
        *,
        channel_id: Optional[str] = None,
        thread_ts: Optional[str] = None,
        limit: Optional[int] = None,
        inclusive: bool = True,
        latest: Optional[str] = None,
        oldest: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch thread replies for a parent message (conversations.replies), with pagination.

        This is the refactor of your SlackAdmin legacy getMessageThreads. :contentReference[oaicite:6]{index=6}

        Note: Slack returns the parent message as the first element in `messages`.
        """
        cid = channel_id or self.channel_id
        tts = thread_ts or self.ts
        if not cid or not tts:
            raise ValueError("get_message_threads requires channel_id and thread_ts (passed or bound).")

        payload: Dict[str, Any] = {"channel": cid, "ts": tts, "inclusive": inclusive}
        if limit is not None:
            payload["limit"] = limit
        if latest:
            payload["latest"] = latest
        if oldest:
            payload["oldest"] = oldest

        replies: List[Dict[str, Any]] = []
        while True:
            resp = self._conversations_replies(payload)
            if not resp.get("ok"):
                raise RuntimeError(f"conversations.replies failed: {resp}")

            batch = resp.get("messages") or []
            replies.extend(batch)

            if limit is not None and len(replies) >= limit:
                return replies[:limit]

            cursor = ((resp.get("response_metadata") or {}).get("next_cursor")) or ""
            if not cursor:
                break
            payload["cursor"] = cursor

        return replies

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
        Fetch channel history (conversations.history) with pagination.

        This mirrors the functionality your legacy *Conversations/Channels* helpers had, but
        putting it here makes Conversations.py cleaner: Conversations delegates to Messages
        for anything message/history/thread related.
        """
        cid = channel_id or self.channel_id
        if not cid:
            raise ValueError("get_messages requires channel_id (passed or bound).")

        payload: Dict[str, Any] = {
            "channel": cid,
            "include_all_metadata": include_all_metadata,
            "inclusive": inclusive,
        }
        if limit is not None:
            payload["limit"] = limit
        if latest:
            payload["latest"] = latest
        if oldest:
            payload["oldest"] = oldest

        out: List[Dict[str, Any]] = []
        while True:
            resp = self._conversations_history(payload)
            if not resp.get("ok"):
                raise RuntimeError(f"conversations.history failed: {resp}")

            batch = resp.get("messages") or []
            out.extend(batch)

            if limit is not None and len(out) >= limit:
                return out[:limit]

            cursor = ((resp.get("response_metadata") or {}).get("next_cursor")) or ""
            if not cursor:
                break
            payload["cursor"] = cursor

        return out

    def replace_message_block(
        self,
        *,
        blocks: Optional[List[Dict[str, Any]]] = None,
        block_type: str = "",
        block_id: str = "",
        text: str = "",
        new_block: Optional[Dict[str, Any]] = None,
        new_block_id: str = "",
        channel_id: Optional[str] = None,
        ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Replace the first matching block (by type or block_id) and update the message.

        Ported/refactored from your PCbot legacy replace_message_block. :contentReference[oaicite:7]{index=7}

        Notes:
        - If blocks is omitted, it uses self.message["blocks"] if available.
        - If neither block_type nor block_id is supplied, this raises.
        """
        cid = channel_id or self.channel_id
        mts = ts or self.ts
        if not cid or not mts:
            raise ValueError("replace_message_block requires channel_id and ts (passed or bound).")

        if blocks is None:
            if not self.message or "blocks" not in self.message:
                raise ValueError("No blocks provided and no cached message.blocks available.")
            blocks = list(self.message["blocks"])

        # Default behavior from legacy: blank text means "remove" area by replacing with a space section.
        if not text:
            text = " "

        if new_block is None:
            new_block = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            }

        if new_block_id:
            new_block["block_id"] = new_block_id

        # Determine match key
        key = ""
        target = ""
        if block_type:
            key = "type"
            target = block_type
        if block_id:
            key = "block_id"
            target = block_id

        if not key:
            raise ValueError("replace_message_block requires block_type or block_id.")

        # Replace first match
        replaced = False
        for i, b in enumerate(blocks):
            if b.get(key) == target:
                blocks[i] = new_block
                replaced = True
                break

        if not replaced:
            self.logger.info("No block matched %s=%r; no update performed.", key, target)
            return {"ok": False, "error": "block_not_found", "key": key, "target": target}

        # Update message with modified blocks
        return self.update_message(channel_id=cid, ts=mts, blocks=blocks)
