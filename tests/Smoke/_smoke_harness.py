"""
Shared smoke-test harness for slack-objects object helpers.

- FakeWebClient: mimics slack_sdk.WebClient.api_call(method, json=...)
- FakeApiCaller: calls FakeWebClient.api_call with no sleeping
- FakeHttpSession: used by Files for url_private downloads
- FakeScimSession: used by IDP_groups for SCIM calls
- run_smoke: runs and reports call specs

Run any smoke test:
    python -m tests.Smoke.users_smoke_test
    python -m tests.Smoke.messages_smoke_test
    ...etc
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


class FakeWebClient:
    """
    Minimal stub for slack_sdk.WebClient.
    Your SlackApiCaller calls WebClient.api_call(method, json=payload), so we emulate that.
    """

    def api_call(self, method: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = json or {}

        # ---------------------------
        # Messages / chat.*
        # ---------------------------
        if method == "chat.update":
            return {"ok": True, "channel": payload.get("channel"), "ts": payload.get("ts"), "text": payload.get("text", "")}

        if method == "chat.delete":
            return {"ok": True, "channel": payload.get("channel"), "ts": payload.get("ts")}

        # conversations.history / replies pagination shape
        if method == "conversations.history":
            # Return two messages, one includes a file reference for Files.get_file_source_message test.
            return {
                "ok": True,
                "messages": [
                    {"ts": "1700000000.000100", "user": "U_FILE_OWNER", "text": "hello"},
                    {"ts": "1700000001.000200", "user": "U_FILE_OWNER", "text": "shared file", "files": [{"id": "F_TEST"}]},
                ],
                "response_metadata": {"next_cursor": ""},
            }

        if method == "conversations.replies":
            return {
                "ok": True,
                "messages": [
                    {"ts": payload.get("ts", "1700000000.000100"), "text": "parent"},
                    {"ts": "1700000000.000101", "text": "reply 1"},
                ],
                "response_metadata": {"next_cursor": ""},
            }

        # ---------------------------
        # Conversations / channels
        # ---------------------------
        if method == "conversations.info":
            cid = payload.get("channel", "C_TEST")
            return {
                "ok": True,
                "channel": {
                    "id": cid,
                    "name": "general",
                    "is_private": False,
                },
            }

        if method == "admin.conversations.search":
            # Matches Conversations.get_conversation_ids_from_name exact-name filtering
            q = payload.get("query", "")
            return {
                "ok": True,
                "conversations": [
                    {"id": "C_MATCH", "name": q},          # exact match
                    {"id": "C_OTHER", "name": f"{q}-x"},   # non-exact
                ],
                "next_cursor": "",
            }

        if method == "admin.conversations.archive":
            return {"ok": True}

        if method == "admin.conversations.setTeams":
            return {"ok": True}

        if method == "admin.conversations.restrictAccess.addGroup":
            return {"ok": True}

        if method == "discovery.conversations.members":
            # One page only
            return {"ok": True, "members": ["U1", "U2"], "offset": ""}

        # ---------------------------
        # Files
        # ---------------------------
        if method == "files.info":
            # Support Files.get_file_info pagination behavior
            cursor = payload.get("cursor")
            if cursor:
                return {"ok": True, "file": {"id": payload.get("file", "F_TEST")}, "response_metadata": {"next_cursor": ""}}

            return {
                "ok": True,
                "file": {
                    "id": payload.get("file", "F_TEST"),
                    "name": "example.txt",
                    "mimetype": "text/plain",
                    "pretty_type": "Text",
                    "url_private": "https://files.slack.fake/url_private/F_TEST",
                    "user": "U_FILE_OWNER",
                },
                "response_metadata": {"next_cursor": "CURSOR_1"},
            }

        if method == "files.delete":
            return {"ok": True}

        if method == "files.list":
            return {"ok": True, "files": [], "paging": {"count": 0}}

        if method == "files.uploadV2":
            # Files.upload_to_slack expects either resp["file"]["id"] or resp["files"][0]["id"]
            return {"ok": True, "file": {"id": "F_UPLOADED"}}

        # ---------------------------
        # Workspaces
        # ---------------------------
        if method == "team.info":
            tid = payload.get("team", "T_TEST")
            return {"ok": True, "team": {"id": tid, "name": "Test Workspace"}}

        if method == "admin.teams.list":
            return {
                "ok": True,
                "teams": [{"id": "T1", "name": "Workspace One"}, {"id": "T2", "name": "Workspace Two"}],
                "response_metadata": {"next_cursor": ""},
            }

        if method == "admin.users.list":
            return {"ok": True, "users": [{"id": "U1"}, {"id": "U2"}], "response_metadata": {"next_cursor": ""}}

        if method == "admin.teams.admins.list":
            return {"ok": True, "admin_ids": ["U_ADMIN_1", "U_ADMIN_2"], "response_metadata": {"next_cursor": ""}}

        # ---------------------------
        # Users
        # ---------------------------
        if method == "users.info":
            return {
                "ok": True,
                "user": {
                    "id": payload.get("user", "U_TEST"),
                    "real_name": "Test User",
                    "profile": {"display_name": "Testy"},
                    "is_restricted": False,
                    "is_ultra_restricted": False,
                    "deleted": False,
                },
            }

        if method == "users.lookupByEmail":
            if payload.get("email") == "found@example.com":
                return {"ok": True, "user": {"id": "U_FOUND"}}
            return {"ok": False, "error": "users_not_found"}

        if method == "users.profile.get":
            return {"ok": True, "profile": {"status_text": "hello"}}

        if method == "users.profile.set":
            return {"ok": True}

        # ---------------------------
        # Users discovery
        # ---------------------------
        if method == "discovery.user.conversations":
            return {
                "ok": True,
                "channels": [
                    {"id": "C_ACTIVE", "date_left": 0},
                    {"id": "C_LEFT", "date_left": 1700000000},
                ],
                "offset": "",
            }

        # Default: ok True
        return {"ok": True}


class FakeApiCaller:
    """Drop-in replacement for SlackApiCaller.call() that just forwards to client.api_call()."""

    def __init__(self, cfg: Any):
        self.cfg = cfg

    def call(self, client: Any, method: str, *, rate_tier: Any = None, **kwargs) -> Dict[str, Any]:
        return client.api_call(method, json=kwargs)


class FakeHttpSession:
    """Used by Files._http_get_private_url -> http_session.get()."""

    def get(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None):
        class Resp:
            ok = True
            status_code = 200
            text = "ok"
            content = b"hello from fake download\n"
        return Resp()


class FakeScimSession:
    """
    Used by IDP_groups._scim_request and Users._scim_request via scim_session.request().
    We simulate:
      - GET  Groups        (paginated list)
      - GET  Groups/{id}   (group detail / members)
      - POST Users         (create)
      - DELETE Users/{id}  (deactivate)
      - PATCH Users/{id}   (reactivate / update attribute / make guest)
    """

    def request(self, method: str, url: str, **kwargs):
        # kwargs may include: headers, params, json, data, timeout, etc.
        params = kwargs.get("params") or {}

        class Resp:
            def __init__(self, payload: Dict[str, Any], status: int = 200):
                self._payload = payload
                self.status_code = status
                self.ok = True
                self.text = "json"

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        method_upper = method.upper()

        # --- SCIM Users endpoints (used by Users SCIM methods) ---
        if "/Users" in url and "Groups" not in url:
            if method_upper == "GET":
                # scim_search_user_by_email / scim_search_user_by_username (filter)
                # or direct lookup Users/{id}
                if "filter" in (params or {}):
                    return Resp({"Resources": [{"id": "U1", "userName": "testuser"}], "totalResults": 1})
                # Direct GET Users/{id}
                return Resp({"id": "U1", "userName": "testuser", "active": True})

            if method_upper == "POST":
                # scim_create_user
                return Resp({"id": "U_SCIM_NEW", "userName": "testuser"}, 201)

            if method_upper == "DELETE":
                # scim_deactivate_user
                return Resp({}, 200)

            if method_upper == "PATCH":
                # scim_reactivate_user / scim_update_user_attribute / make_multi_channel_guest
                return Resp({"id": "U1", "active": True}, 200)

        # --- SCIM Groups endpoints (used by IDP_groups) ---
        # Group detail (IDP_groups.get_members / is_member)
        if "Groups/" in url:
            return Resp({"members": [{"value": "U1", "display": "User One"}, {"value": "U2", "display": "User Two"}]})

        # Group list
        # SCIM startIndex is 1-based; return all in one page here
        return Resp(
            {
                "Resources": [
                    {"id": "G1", "displayName": "Group One"},
                    {"id": "G2", "displayName": "Group Two"},
                ],
                "totalResults": 2,
                "startIndex": params.get("startIndex", 1),
            }
        )


@dataclass
class CallSpec:
    name: str
    fn: Callable[[], Any]


def run_smoke(title: str, specs: List[CallSpec]) -> None:
    print(f"\n==== {title} ====")
    failures: List[Tuple[str, Exception]] = []

    for spec in specs:
        try:
            spec.fn()
            print(f"✅ {spec.name}")
        except Exception as e:
            failures.append((spec.name, e))
            print(f"❌ {spec.name}: {type(e).__name__}: {e}")

    if failures:
        msg = "\n".join([f"- {name}: {type(e).__name__}: {e}" for name, e in failures])
        raise SystemExit(f"\nSmoke test failures:\n{msg}")

    print(f"✅ All {len(specs)} checks passed.")
