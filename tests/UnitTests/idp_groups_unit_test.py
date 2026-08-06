# tests/UnitTests/idp_groups_unit_test.py
"""
Unit-test harness for IDP_groups.

This file is designed to:
1) Demonstrate intended factory-style usage:
      slack = SlackObjectsClient(cfg)
      idp = slack.idp_groups()
      bound = slack.idp_groups("S123")
2) Provide deterministic tests with NO network by mocking a requests.Session.

Run options:
- pytest:
    pytest -q tests/UnitTests/idp_groups_unit_test.py
- plain python (runs a minimal smoke test):
    python tests/UnitTests/idp_groups_unit_test.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import json
import logging

import requests
from slack_objects.rate_limits import RateLimitPolicy


# -----------------------------
# Fakes / Test doubles
# -----------------------------

class FakeResponse:
    """Minimal requests.Response-like object for our fake session."""
    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise requests.HTTPError(f"HTTP {self.status_code}: {self.text}")


class FakeScimSession(requests.Session):
    """
    Fake SCIM Session that returns canned responses.

    `routes` keys are (method, url) tuples.
    Values are (status_code, payload).
    """
    def __init__(self, routes: Dict[Tuple[str, str], Tuple[int, Dict[str, Any]]]):
        super().__init__()
        self.routes = routes
        self.calls = []  # (method, url, params, json)

    def request(self, method: str, url: str, **kwargs):
        method_u = method.upper()
        params = kwargs.get("params")
        payload = kwargs.get("json")
        self.calls.append((method_u, url, params, payload))

        key = (method_u, url)
        if key not in self.routes:
            return FakeResponse(404, {"error": "not_found", "method": method_u, "url": url})
        status, data = self.routes[key]
        return FakeResponse(status, data)


class DummySlackClient:
    """Placeholder. IDP_groups doesn't use slack_sdk.WebClient directly for SCIM calls."""
    pass


class DummyApiCaller:
    """Placeholder. IDP_groups doesn't need SlackApiCaller unless you extend it later."""
    pass


# -----------------------------
# Minimal config for tests
# -----------------------------

@dataclass
class DummyConfig:
    """
    Minimal subset of SlackObjectsConfig used by IDP_groups.
    Adjust field names if your real SlackObjectsConfig differs.
    """
    scim_token: str = "xoxp-scim-token"
    http_timeout_seconds: int = 5

    # Required by SlackObjectBase.__post_init__ → rate_policy resolution
    default_rate_tier: float = 3.0  # RateTier.TIER_2 value

    # Required by ScimMixin._scim_base_url()
    scim_base_url: str = "https://api.slack.com/scim"
    scim_version: str = "v1"

    # Required by SlackObjectsClient.__init__
    bot_token: Optional[str] = "xoxb-dummy-bot-token"
    user_token: Optional[str] = None


# -----------------------------
# Helpers
# -----------------------------

def _scim_base(cfg: DummyConfig, version: str = "v1") -> str:
    return f"{cfg.scim_base_url.rstrip('/')}/{cfg.scim_version}/"


# -----------------------------
# Pytest-style tests
# -----------------------------

def test_get_groups_paginates_and_shapes_output():
    """
    Verifies:
    - get_groups() collects all pages
    - output shape matches legacy: [{'group id': ..., 'group name': ...}, ...]
    """
    from slack_objects.idp_groups import IDP_groups  # import from your package

    cfg = DummyConfig()
    base = _scim_base(cfg, "v1")

    # Two-page SCIM Groups listing (startIndex 1-based)
    page1 = {
        "Resources": [
            {"id": "S111", "displayName": "Admins"},
            {"id": "S222", "displayName": "Readers"},
        ],
        "totalResults": 3,
        "startIndex": 1,
        "itemsPerPage": 2,
    }
    page2 = {
        "Resources": [
            {"id": "S333", "displayName": "Writers"},
        ],
        "totalResults": 3,
        "startIndex": 3,
        "itemsPerPage": 1,
    }

    # Our refactored IDP_groups uses query params count/startIndex.
    # We route by URL only (params are captured in calls for inspection).
    routes = {
        ("GET", f"{base}Groups"): (200, page1),  # first call
        # For the second call we reuse the same URL; the fake session returns the same payload unless we swap.
    }

    sess = FakeScimSession(routes)

    # Instantiate IDP_groups in package style (cfg/client/logger/api).
    idp = IDP_groups(cfg=cfg, client=DummySlackClient(), logger=logging.getLogger("test"), api=DummyApiCaller(), scim_session=sess)

    # After creating the IDP_groups instance in each test, add:
    idp.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    # Monkey-patch the session routes after first call to simulate pagination.
    # (Keeps the fake simple, but still tests your pagination loop.)
    call_count = []
    def request_side_effect(method: str, url: str, **kwargs):
        call_count.append(1)
        # first GET Groups -> page1, second -> page2
        if len(call_count) == 1:
            return FakeResponse(200, page1)
        return FakeResponse(200, page2)

    sess.request = request_side_effect  # type: ignore[method-assign]

    groups = idp.get_groups(fetch_count=2)

    assert groups == [
        {"group id": "S111", "group name": "Admins"},
        {"group id": "S222", "group name": "Readers"},
        {"group id": "S333", "group name": "Writers"},
    ]


def test_get_members_and_is_member_with_bound_group():
    """
    Verifies:
    - with_group binds group_id
    - get_members uses bound group_id if none passed
    - is_member returns True/False correctly
    """
    from slack_objects.idp_groups import IDP_groups  # import from your package

    cfg = DummyConfig()
    base = _scim_base(cfg, "v1")

    group_payload = {
        "id": "S123",
        "displayName": "Admins",
        "members": [
            {"value": "U111", "display": "Alice"},
            {"value": "U222", "display": "Bob"},
        ],
    }

    routes = {
        ("GET", f"{base}Groups/S123"): (200, group_payload),
    }

    sess = FakeScimSession(routes)

    idp = IDP_groups(cfg=cfg, client=DummySlackClient(), logger=logging.getLogger("test"), api=DummyApiCaller(), scim_session=sess)
    idp.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)
    bound = idp.with_group("S123")
    bound.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    members = bound.get_members()
    assert members == group_payload["members"]

    assert bound.is_member("U111") is True
    assert bound.is_member("U999") is False


def test_get_group_returns_full_record_in_one_call():
    """
    Verifies:
    - get_group() returns the complete SCIM payload (not just members)
    - a single GET Groups/{id} serves both displayName and members
    """
    from slack_objects.idp_groups import IDP_groups

    cfg = DummyConfig()
    base = _scim_base(cfg, "v1")

    group_payload = {
        "id": "S123",
        "displayName": "Admins",
        "meta": {"created": "2024-01-01T00:00:00Z"},
        "members": [{"value": "U111", "display": "Alice"}],
    }

    sess = FakeScimSession({("GET", f"{base}Groups/S123"): (200, group_payload)})

    idp = IDP_groups(cfg=cfg, client=DummySlackClient(), logger=logging.getLogger("test"), api=DummyApiCaller(), scim_session=sess)
    idp.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    group = idp.get_group("S123")

    assert group["displayName"] == "Admins"
    assert group["members"] == group_payload["members"]
    # Unmapped fields stay reachable, which is why the full payload is returned.
    assert group["meta"]["created"] == "2024-01-01T00:00:00Z"
    assert len(sess.calls) == 1


def test_bound_properties_load_lazily_and_share_one_call():
    """
    Verifies:
    - binding a group_id performs no API call
    - display_name triggers the fetch, and members reuses the cached response
    """
    from slack_objects.idp_groups import IDP_groups

    cfg = DummyConfig()
    base = _scim_base(cfg, "v1")

    group_payload = {
        "id": "S123",
        "displayName": "Admins",
        "members": [{"value": "U111", "display": "Alice"}],
    }

    sess = FakeScimSession({("GET", f"{base}Groups/S123"): (200, group_payload)})

    group = IDP_groups(cfg=cfg, client=DummySlackClient(), logger=logging.getLogger("test"), api=DummyApiCaller(), scim_session=sess, group_id="S123")
    group.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    # Construction must not perform network I/O.
    assert sess.calls == []

    assert group.display_name == "Admins"
    assert group.members == group_payload["members"]
    # get_members() must reuse the cache rather than issue a second request.
    assert group.get_members() == group_payload["members"]
    assert len(sess.calls) == 1


def test_properties_require_a_bound_group_id():
    """An unbound instance cannot lazily load, and must say so clearly."""
    from slack_objects.idp_groups import IDP_groups

    cfg = DummyConfig()
    sess = FakeScimSession({})

    idp = IDP_groups(cfg=cfg, client=DummySlackClient(), logger=logging.getLogger("test"), api=DummyApiCaller(), scim_session=sess)
    idp.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    try:
        idp.display_name
    except ValueError:
        pass
    else:
        raise AssertionError("display_name should raise ValueError when no group_id is bound")

    assert sess.calls == []


def test_get_group_merges_paginated_members():
    """
    Verifies:
    - when totalResults exceeds the members returned, remaining pages are fetched
    - members from all pages are merged, so large groups are not truncated
    """
    from slack_objects.idp_groups import IDP_groups

    cfg = DummyConfig()

    page1 = {
        "id": "S123",
        "displayName": "Admins",
        "totalResults": 3,
        "members": [{"value": "U111", "display": "Alice"}, {"value": "U222", "display": "Bob"}],
    }
    page2 = {
        "id": "S123",
        "displayName": "Admins",
        "totalResults": 3,
        "members": [{"value": "U333", "display": "Carol"}],
    }

    sess = FakeScimSession({})

    calls = []

    def request_side_effect(method: str, url: str, **kwargs):
        calls.append(kwargs.get("params"))
        return FakeResponse(200, page1 if len(calls) == 1 else page2)

    sess.request = request_side_effect  # type: ignore[method-assign]

    idp = IDP_groups(cfg=cfg, client=DummySlackClient(), logger=logging.getLogger("test"), api=DummyApiCaller(), scim_session=sess)
    idp.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    group = idp.get_group("S123", fetch_count=2)

    assert [m["value"] for m in group["members"]] == ["U111", "U222", "U333"]
    # First call is the plain legacy request; the second resumes after what we already have.
    assert calls[0] is None
    assert calls[1]["startIndex"] == 3


# -----------------------------
# Optional "factory-style" demo
# -----------------------------

def test_factory_style_if_available():
    """
    If your SlackObjectsClient is implemented, this demonstrates:
        slack = SlackObjectsClient(cfg)
        idp = slack.idp_groups()
        bound = slack.idp_groups("S123")

    We swap the internal session of the cached IDP_groups instance to avoid real HTTP.
    """
    try:
        from slack_objects.client import SlackObjectsClient
        from slack_objects.idp_groups import IDP_groups
    except Exception:
        # If client isn't available yet, skip silently.
        return

    cfg = DummyConfig()
    slack = SlackObjectsClient(cfg)  # should exist in your package

    base = _scim_base(cfg, "v1")
    group_payload = {"id": "S123", "displayName": "Admins", "members": [{"value": "U1", "display": "A"}]}
    routes = {("GET", f"{base}Groups/S123"): (200, group_payload)}
    sess = FakeScimSession(routes)

    # Get cached unbound instance and swap its session for testing
    idp = slack.idp_groups()
    if not isinstance(idp, IDP_groups):
        raise AssertionError("slack.idp_groups() did not return an IDP_groups instance")

    idp.scim_session = sess
    idp.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    bound = slack.idp_groups("S123")
    # Make sure the bound instance shares the session (since with_group copies it)
    bound.scim_session = sess
    bound.rate_policy = RateLimitPolicy(method_overrides={}, prefix_rules={}, default=0.0)

    assert bound.is_member("U1") is True


# -----------------------------
# Script mode
# -----------------------------

def _smoke_run() -> None:
    """Run a minimal subset of tests without pytest."""
    test_get_members_and_is_member_with_bound_group()
    print("Smoke test passed ✅")


if __name__ == "__main__":
    _smoke_run()
