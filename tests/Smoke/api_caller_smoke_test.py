from __future__ import annotations

"""
Smoke tests for SlackApiCaller retry / rate-limit behavior.

Validates:
- Normal calls succeed
- 429 retries succeed after transient rate-limits
- 429 retries give up after MAX_RETRIES
- Malformed Retry-After header falls back gracefully
- use_json flag is preserved across retries
"""

import logging
import time
from typing import Any, Dict, Optional

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.api_caller import SlackApiCaller

from tests.Smoke._smoke_harness import CallSpec, run_smoke


# ---------------------------------------------------------------------------
# Fake Slack response / error plumbing
# ---------------------------------------------------------------------------

class FakeSlackResponse:
    """Mimics slack_sdk.web.SlackResponse enough for SlackApiCaller."""
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.status_code = 200


class FakeSlackApiError(Exception):
    """Mimics slack_sdk.errors.SlackApiError with a .response attribute."""
    def __init__(self, status_code: int, headers: Optional[Dict[str, str]] = None):
        super().__init__(f"HTTP {status_code}")
        self.response = type("Resp", (), {
            "status_code": status_code,
            "headers": headers or {},
        })()


# ---------------------------------------------------------------------------
# Configurable fake client
# ---------------------------------------------------------------------------

class RateLimitingClient:
    """
    A fake WebClient that returns 429 for the first `fail_count` calls,
    then succeeds.  Tracks how many times api_call was invoked and
    which serialization style (json vs params) was used.
    """
    def __init__(self, fail_count: int = 0, retry_after: str = "0",
                 headers: Optional[Dict[str, str]] = None):
        self.fail_count = fail_count
        self.call_count = 0
        self.last_serialization: Optional[str] = None
        self._headers = headers or {"Retry-After": retry_after}

    def api_call(self, method: str, json: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Any]] = None) -> FakeSlackResponse:
        self.call_count += 1
        self.last_serialization = "json" if json is not None else "params"

        if self.call_count <= self.fail_count:
            # Monkey-patch into the exception type that SlackApiCaller catches
            import slack_sdk.errors as sdk_errors
            err = sdk_errors.SlackApiError(
                message=f"HTTP 429",
                response=type("Resp", (), {
                    "status_code": 429,
                    "headers": self._headers,
                    "data": {"ok": False},
                })(),
            )
            raise err

        return FakeSlackResponse({"ok": True, "method": method})


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_caller() -> SlackApiCaller:
    cfg = SlackObjectsConfig(
        bot_token="xoxb-fake",
        default_rate_tier=RateTier.TIER_4,  # 0.6 s — smallest sleep
    )
    return SlackApiCaller(cfg)


# Suppress the real time.sleep so smoke tests are instant
_original_sleep = time.sleep
time.sleep = lambda _: None


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

def test_normal_call() -> None:
    caller = _make_caller()
    client = RateLimitingClient(fail_count=0)
    result = caller.call(client, "users.info", user="U1")
    assert result["ok"] is True, f"Expected ok=True, got {result}"
    assert client.call_count == 1


def test_retry_then_succeed() -> None:
    caller = _make_caller()
    client = RateLimitingClient(fail_count=3, retry_after="0")
    result = caller.call(client, "users.info", user="U1")
    assert result["ok"] is True, f"Expected ok=True after retries, got {result}"
    assert client.call_count == 4, f"Expected 4 calls (3 fails + 1 success), got {client.call_count}"


def test_retry_exceeds_max() -> None:
    caller = _make_caller()
    client = RateLimitingClient(fail_count=99, retry_after="0")  # never succeeds
    try:
        caller.call(client, "users.info", user="U1")
        raise AssertionError("Expected RuntimeError after MAX_RETRIES")
    except RuntimeError as e:
        assert "Rate-limited" in str(e), f"Unexpected error message: {e}"
        # MAX_RETRIES is 5, so: 1 initial + 5 retries = 6 total calls
        assert client.call_count == 6, f"Expected 6 calls, got {client.call_count}"


def test_malformed_retry_after_header() -> None:
    caller = _make_caller()
    client = RateLimitingClient(fail_count=1, headers={"Retry-After": "not-a-number"})
    result = caller.call(client, "users.info", user="U1")
    assert result["ok"] is True, f"Expected graceful fallback, got {result}"


def test_use_json_preserved_across_retries() -> None:
    caller = _make_caller()
    client = RateLimitingClient(fail_count=2, retry_after="0")
    caller.call(client, "chat.postMessage", use_json=True, channel="C1", text="hi")
    assert client.last_serialization == "json", (
        f"use_json should be preserved on retry; last call used '{client.last_serialization}'"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    specs = [
        CallSpec("normal call succeeds", test_normal_call),
        CallSpec("retry 3x then succeed", test_retry_then_succeed),
        CallSpec("give up after MAX_RETRIES", test_retry_exceeds_max),
        CallSpec("malformed Retry-After falls back", test_malformed_retry_after_header),
        CallSpec("use_json preserved across retries", test_use_json_preserved_across_retries),
    ]

    try:
        run_smoke("SlackApiCaller smoke (retry & rate-limit)", specs)
    finally:
        time.sleep = _original_sleep  # restore


if __name__ == "__main__":
    main()