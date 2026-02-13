from __future__ import annotations

"""
slack_objects.files
==================

Files helper for the `slack-objects` package.

Design goals (mirrors Users):
- Factory-friendly:
    files = slack.files()
    f = slack.files("F123")
- Modular internals:
    public methods call *wrapper methods*; wrapper methods are the only place that call Slack APIs.
- Testable:
    file downloads use an injectable requests.Session.

This module provides file-centric behaviors:
- Load file metadata (files.info)
- Download text file content (via url_private)
- Upload content (files.uploadV2)
- Delete/list files
- Identify the message where a file was shared (via a Conversations/Channels-like helper)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union

import requests

from .base import SlackObjectBase
from .config import RateTier


@dataclass
class Files(SlackObjectBase):
    """
    Files domain helper.

    Factory-style usage:
        slack = SlackObjectsClient(cfg)
        files = slack.files()           # unbound
        f = slack.files("F123")         # bound to file_id

    Notes:
    - file_id is optional
    - attributes are loaded lazily via refresh()
    - file_content is only populated if you call get_text_content() or refresh(..., get_content=True)
    """
    file_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    # File content, only for supported types (currently text/*)
    file_content: Optional[Union[str, bytes]] = None

    # When locating where a file was shared, store the matching message here
    source_message: Optional[Dict[str, Any]] = None

    # Optional requests session (handy for unit tests and connection pooling)
    http_session: requests.Session = field(default_factory=requests.Session, repr=False)

    # ---------- factory helpers ----------

    def with_file(self, file_id: str) -> "Files":
        """Return a new Files instance bound to file_id, sharing cfg/client/logger/api."""
        return Files(
            cfg=self.cfg,
            client=self.client,
            logger=self.logger,
            api=self.api,
            file_id=file_id,
            http_session=self.http_session,
        )

    # ---------- attribute lifecycle ----------

    def refresh(self, file_id: Optional[str] = None, *, get_content: bool = False) -> Dict[str, Any]:
        """
        Refresh attributes for file_id (or self.file_id) using files.info.
        If get_content=True and mimetype is text/*, also fetch the file content.
        """
        if file_id:
            self.file_id = file_id
        if not self.file_id:
            raise ValueError("refresh() requires file_id (passed or already set)")

        resp = self.get_file_info(self.file_id)
        if not resp.get("ok"):
            raise RuntimeError(f"Files.get_file_info() failed: {resp}")

        # Slack returns file info under 'file'
        self.attributes = resp.get("file") or {}

        if get_content and self._is_text_file():
            self.get_text_content()

        return self.attributes

    def _require_attributes(self) -> Dict[str, Any]:
        """Ensure file attributes are loaded before accessing fields like url_private/mimetype."""
        if self.attributes:
            return self.attributes
        if self.file_id:
            return self.refresh()
        raise ValueError("File attributes not loaded and no file_id set (call refresh() or bind file_id).")

    def _is_text_file(self) -> bool:
        attrs = self._require_attributes()
        return "text/" in str(attrs.get("mimetype", ""))

    # ============================================================
    # Slack Web API wrapper layer
    # ============================================================
    # Only these methods should call `self.api.call(...)` directly.

    def _files_info(self, file_id: str, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Wrapper for files.info."""
        payload: Dict[str, Any] = {"file": file_id}
        if cursor:
            payload["cursor"] = cursor
        return self.api.call(self.client, "files.info", rate_tier=RateTier.TIER_4, **payload)

    def _files_delete(self, file_id: str) -> Dict[str, Any]:
        """Wrapper for files.delete."""
        return self.api.call(self.client, "files.delete", rate_tier=RateTier.TIER_3, file=file_id)

    def _files_list(self, **kwargs) -> Dict[str, Any]:
        """Wrapper for files.list (thin pass-through)."""
        return self.api.call(self.client, "files.list", rate_tier=RateTier.TIER_3, **kwargs)

    def _files_upload_v2(self, **kwargs) -> Dict[str, Any]:
        """
        Wrapper for files.uploadV2.
        Slack SDK method name is typically `files.uploadV2` as an API method string.
        """
        return self.api.call(self.client, "files.uploadV2", rate_tier=RateTier.TIER_3, **kwargs)

    # ============================================================
    # HTTP wrapper layer (for url_private download)
    # ============================================================

    def _http_get_private_url(self, url: str) -> requests.Response:
        """
        Download url_private content.

        Slack file downloads require Authorization: Bearer <bot_token> (or a token that can read the file).
        We use cfg.bot_token by default.
        """
        token = getattr(self.cfg, "bot_token", None)
        if not token:
            raise ValueError("Downloading url_private requires cfg.bot_token")

        headers = {"Authorization": f"Bearer {token}"}
        timeout = getattr(self.cfg, "http_timeout_seconds", 30)
        return self.http_session.get(url, headers=headers, timeout=timeout)

    # ============================================================
    # Public Slack Web API methods (call wrappers above)
    # ============================================================

    def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """
        Public method for files.info.
        Supports pagination via cursor if Slack includes response_metadata.next_cursor.
        Legacy class looped through pages for comments; we keep that behavior.
        """
        combined_file: Dict[str, Any] = {}
        cursor: Optional[str] = None

        while True:
            resp = self._files_info(file_id, cursor=cursor)
            if not resp.get("ok"):
                return resp

            file_obj = resp.get("file") or {}
            combined_file.update(file_obj)  # merge paginated data (comments, etc.)

            meta = resp.get("response_metadata") or {}
            next_cursor = (meta.get("next_cursor") or "").strip()
            if next_cursor:
                cursor = next_cursor
            else:
                break

        return {"ok": True, "file": combined_file}

    def delete_file(self, file_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete a file by id (defaults to bound self.file_id)."""
        fid = file_id or self.file_id
        if not fid:
            raise ValueError("delete_file requires file_id (passed or bound)")
        return self._files_delete(fid)

    def list_files(self, **kwargs) -> Dict[str, Any]:
        """
        List files using files.list.

        This is intentionally a dict return so callers can inspect paging / metadata.
        """
        return self._files_list(**kwargs)

    def upload_to_slack(
        self,
        *,
        title: str,
        channel: str = "",
        thread_ts: str = "",
        filename: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload file content to Slack via files.uploadV2.

        Behavior (legacy-inspired):
        - Uses self.file_content if `content` is not passed.
        - Uses attributes['name'] as filename if filename not passed and available.
        - If upload succeeds, updates self.file_id from response.

        Note: Slack supports also uploading via `file` parameter (multipart). Here we use `content`.
        """
        # Decide content source
        upload_content = content if content is not None else self.file_content
        if upload_content is None:
            raise ValueError("upload_to_slack requires content (pass content=... or set self.file_content).")

        # Decide filename
        if filename is None:
            filename = str((self.attributes or {}).get("name") or "slack_objects_upload.txt")

        payload: Dict[str, Any] = {
            "content": upload_content,
            "filename": filename,
            "title": title,
        }
        if channel:
            payload["channel"] = channel
        if thread_ts:
            payload["thread_ts"] = thread_ts

        resp = self._files_upload_v2(**payload)

        # Update bound file id if Slack returns it
        if resp.get("ok"):
            # files.uploadV2 can return either file or files list depending on usage
            if "file" in resp and isinstance(resp["file"], dict) and resp["file"].get("id"):
                self.file_id = resp["file"]["id"]
            elif "files" in resp and isinstance(resp["files"], list) and resp["files"]:
                first = resp["files"][0]
                if isinstance(first, dict) and first.get("id"):
                    self.file_id = first["id"]

        return resp

    def get_text_content(self) -> str:
        """
        Download and store file content for text/* files using url_private.

        Stores decoded text in self.file_content and returns it.
        """
        attrs = self._require_attributes()
        mimetype = str(attrs.get("mimetype", ""))

        if "text/" not in mimetype:
            pretty_type = attrs.get("pretty_type", "unknown")
            name = attrs.get("name", self.file_id or "unknown")
            raise ValueError(
                f"get_text_content is only for text/* mimetypes; got '{mimetype}' ({pretty_type}) for file '{name}'."
            )

        url = attrs.get("url_private")
        if not url:
            raise ValueError("File attributes do not include url_private; cannot download content.")

        resp = self._http_get_private_url(url)
        if not resp.ok:
            raise RuntimeError(f"Failed to download file content (HTTP {resp.status_code}): {resp.text[:200]}")

        text = resp.content.decode("utf-8")
        self.file_content = text
        return text

    def get_file_source_message(
        self,
        *,
        conversation,
        file_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the most recent message in a conversation where a file was shared.

        Parameters:
        - conversation: an object with `.channel_id` and a `get_messages(channel_id, limit=...)` method.
        - file_id: defaults to bound self.file_id
        - user_id: defaults to file uploader (attributes['user']) if attributes are loaded
        - limit: how many recent messages to scan (legacy default ~5)

        Side effects:
        - Sets self.source_message if found
        - Returns the message dict if found, else None

        This method calls:
            conversation.get_messages(channel_id=..., limit=...)

        Note:
        - `get_messages` uses keyword-only arguments.
        """
        fid = file_id or self.file_id
        if not fid:
            raise ValueError("get_file_source_message requires file_id (passed or bound)")

        # Best-effort user match: if not provided, try to use file uploader id
        uid = user_id
        if uid is None and self.attributes:
            uid = self.attributes.get("user")

        messages = conversation.get_messages(channel_id=conversation.channel_id, limit=limit)

        for msg in messages:
            files = msg.get("files")
            if not files:
                continue
            if uid and msg.get("user") != uid:
                continue
            if any(isinstance(f, dict) and f.get("id") == fid for f in files):
                self.source_message = msg
                return msg

        return None
