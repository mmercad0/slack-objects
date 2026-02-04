from __future__ import annotations

"""
slack_objects.workspaces
=======================

Workspaces helper for the `slack-objects` package.

Merged/refactored from two legacy implementations:
- A "single-workspace" helper that fetches attributes via `team.info` (PCbot) :contentReference[oaicite:2]{index=2}
- A "grid admin" helper that lists workspaces and can list workspace users/admins via admin endpoints :contentReference[oaicite:3]{index=3}

Design goals:
- Factory-friendly: `workspaces = slack.workspaces()` or `ws = slack.workspaces("T123")`
- Modularity: public methods call wrapper methods; wrappers are the only place that directly call Slack API
- Usability: supports both "work with one workspace" and "work with many workspaces in a grid"
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import SlackObjectBase
from .config import RateTier


@dataclass
class Workspaces(SlackObjectBase):
    """
    Workspaces domain helper.

    Factory-style usage:
        slack = SlackObjectsClient(cfg)
        workspaces = slack.workspaces()             # unbound (grid/listing helpers)
        ws = slack.workspaces("T12345678")          # bound to workspace_id

    Notes:
    - `workspace_id` is optional. Methods that require a workspace will enforce it.
    - `workspaces_cache` is an optional cached list of workspaces (from admin.teams.list).
      This enables fast name<->id lookups without re-fetching each time.
    """
    workspace_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Cache of workspaces returned by admin.teams.list (list of dicts with at least id/name)
    workspaces_cache: List[Dict[str, Any]] = field(default_factory=list)

    # ---------- factory helpers ----------

    def with_workspace(self, workspace_id: str) -> "Workspaces":
        """Return a new Workspaces instance bound to workspace_id, sharing cfg/client/logger/api."""
        return Workspaces(
            cfg=self.cfg,
            client=self.client,
            logger=self.logger,
            api=self.api,
            workspace_id=workspace_id,
            workspaces_cache=self.workspaces_cache,
        )

    # ---------- attribute lifecycle ----------

    def refresh(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Refresh attributes for workspace_id (or self.workspace_id) using team.info.

        This method is intentionally layered: it calls `get_workspace_info()`.
        """
        if workspace_id:
            self.workspace_id = workspace_id
        if not self.workspace_id:
            raise ValueError("refresh() requires workspace_id (passed or already set)")

        resp = self.get_workspace_info(self.workspace_id)
        if not resp.get("ok"):
            raise RuntimeError(f"Workspaces.get_workspace_info() failed: {resp}")

        # `team.info` returns `team` on success in the legacy version :contentReference[oaicite:4]{index=4}
        self.attributes = resp.get("team") or {}
        return self.attributes

    def _require_workspace_id(self, workspace_id: Optional[str] = None) -> str:
        """Return a workspace_id or raise, used by methods that require one."""
        wid = workspace_id or self.workspace_id
        if not wid:
            raise ValueError("This operation requires a workspace_id (passed or bound).")
        return wid

    # ============================================================
    # Slack API wrapper layer
    # ============================================================
    # Only these methods should call `self.api.call(...)` directly.

    def _team_info(self, workspace_id: str) -> Dict[str, Any]:
        """Wrapper for team.info (fetch a workspace's metadata)."""
        return self.api.call(self.client, "team.info", rate_tier=RateTier.TIER_3, team=workspace_id)

    def _admin_teams_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for admin.teams.list (Grid: list workspaces)."""
        return self.api.call(self.client, "admin.teams.list", rate_tier=RateTier.TIER_3, **payload)

    def _admin_users_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for admin.users.list (list users in a workspace)."""
        return self.api.call(self.client, "admin.users.list", rate_tier=RateTier.TIER_4, **payload)

    def _admin_teams_admins_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for admin.teams.admins.list (list admin IDs for a workspace)."""
        return self.api.call(self.client, "admin.teams.admins.list", rate_tier=RateTier.TIER_3, **payload)

    # ============================================================
    # Public API (calls wrappers above)
    # ============================================================

    def get_workspace_info(self, workspace_id: str) -> Dict[str, Any]:
        """Public method for team.info."""
        return self._team_info(workspace_id)

    def list_workspaces(self, *, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Return a list of workspaces in the Enterprise Grid (admin.teams.list), paginated.

        This replaces the legacy constructor-side fetching of all workspaces :contentReference[oaicite:5]{index=5}.
        Results are cached in `workspaces_cache` unless `force_refresh=True`.
        """
        if self.workspaces_cache and not force_refresh:
            return self.workspaces_cache

        workspaces: List[Dict[str, Any]] = []
        payload: Dict[str, Any] = {}

        while True:
            resp = self._admin_teams_list(payload)
            if not resp.get("ok"):
                raise RuntimeError(f"admin.teams.list failed: {resp}")

            teams = resp.get("teams") or []
            workspaces.extend(teams)

            # Slack commonly returns cursor pagination via response_metadata.next_cursor
            meta = resp.get("response_metadata") or {}
            cursor = meta.get("next_cursor") or ""
            if cursor:
                payload["cursor"] = cursor
            else:
                break

        self.workspaces_cache = workspaces
        return workspaces

    # ----- name/id resolution helpers (from legacy SlackAdmin) -----

    def get_workspace_name(self, workspace_id: str, *, force_refresh: bool = False) -> str:
        """
        Resolve a workspace ID -> workspace name using the cached list from admin.teams.list.

        Legacy behavior raised if not found :contentReference[oaicite:6]{index=6}.
        """
        workspaces = self.list_workspaces(force_refresh=force_refresh)
        for ws in workspaces:
            if ws.get("id") == workspace_id:
                name = ws.get("name")
                if name:
                    return str(name)

        raise ValueError(
            f"Could not find a workspace with id '{workspace_id}'. "
            "Check the id/token scopes and ensure you are targeting the correct Grid."
        )

    def get_workspace_id(self, workspace_name: str, *, force_refresh: bool = False) -> str:
        """
        Resolve a workspace name -> workspace ID using the cached list from admin.teams.list.

        Legacy behavior raised if not found :contentReference[oaicite:7]{index=7}.
        """
        workspaces = self.list_workspaces(force_refresh=force_refresh)
        target = workspace_name.strip().lower()

        for ws in workspaces:
            if str(ws.get("name", "")).strip().lower() == target:
                wid = ws.get("id")
                if wid:
                    return str(wid)

        raise ValueError(
            f"Could not find a workspace with name '{workspace_name}'. "
            "Check the name/token scopes and ensure you are targeting the correct Grid."
        )

    def get_workspace_from_name(self, workspace_name: str, *, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Return the workspace dict that matches the provided name.

        Legacy behavior raised if not found :contentReference[oaicite:8]{index=8}.
        """
        workspaces = self.list_workspaces(force_refresh=force_refresh)
        target = workspace_name.strip().lower()

        for ws in workspaces:
            if str(ws.get("name", "")).strip().lower() == target:
                return ws

        raise ValueError(
            f"Could not find a workspace with name '{workspace_name}'. "
            "Check the name/token scopes and ensure you are targeting the correct Grid."
        )

    # ----- workspace membership helpers (from legacy SlackAdmin) -----

    def list_users(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return a list of users in a workspace via admin.users.list (paginated).

        This matches the legacy behavior of returning `data['users']` across pages :contentReference[oaicite:9]{index=9}.
        """
        wid = self._require_workspace_id(workspace_id)

        payload: Dict[str, Any] = {"team_id": wid}
        users: List[Dict[str, Any]] = []

        while True:
            resp = self._admin_users_list(payload)
            if not resp.get("ok"):
                raise RuntimeError(f"admin.users.list failed: {resp}")

            users.extend(resp.get("users") or [])

            meta = resp.get("response_metadata") or {}
            cursor = meta.get("next_cursor") or ""
            if cursor:
                payload["cursor"] = cursor
            else:
                break

        return users

    def list_admin_ids(self, workspace_id: Optional[str] = None) -> List[str]:
        """
        Return a list of admin user IDs for a workspace via admin.teams.admins.list (paginated).

        Legacy version returned list_of_admins (IDs) :contentReference[oaicite:10]{index=10}.
        """
        wid = self._require_workspace_id(workspace_id)

        payload: Dict[str, Any] = {"team_id": wid}
        admin_ids: List[str] = []

        while True:
            resp = self._admin_teams_admins_list(payload)
            if not resp.get("ok"):
                raise RuntimeError(f"admin.teams.admins.list failed: {resp}")

            admin_ids.extend([str(x) for x in (resp.get("admin_ids") or [])])

            meta = resp.get("response_metadata") or {}
            cursor = meta.get("next_cursor") or ""
            if cursor:
                payload["cursor"] = cursor
            else:
                break

        return admin_ids
