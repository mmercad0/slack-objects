from __future__ import annotations

"""
Smoke tests for security utilities introduced in the security assessment.

Validates:
- validate_scim_id rejects path-traversal and empty strings
- validate_scim_id accepts legitimate Slack IDs
- safe_error_context strips unknown keys and truncates
"""

import logging

from slack_objects.scim_base import validate_scim_id
from slack_objects.base import safe_error_context

from tests._smoke_harness import CallSpec, run_smoke


# ---------- validate_scim_id ----------

def test_valid_ids_accepted() -> None:
    """Standard Slack IDs should pass without error."""
    for valid in ("U12345", "G1", "W0ABC_DEF", "S-hyphen-ok"):
        result = validate_scim_id(valid, "test_id")
        assert result == valid, f"Expected {valid!r} back, got {result!r}"


def test_path_traversal_rejected() -> None:
    """IDs containing path-traversal characters must raise ValueError."""
    for bad in ("../../admin", "U1/../../etc", "G1/../G2"):
        try:
            validate_scim_id(bad, "test_id")
            raise AssertionError(f"Expected ValueError for {bad!r}")
        except ValueError:
            pass  # expected


def test_empty_and_whitespace_rejected() -> None:
    """Empty strings and whitespace must raise ValueError."""
    for bad in ("", " ", "U1 U2", "G1\nG2"):
        try:
            validate_scim_id(bad, "test_id")
            raise AssertionError(f"Expected ValueError for {bad!r}")
        except ValueError:
            pass  # expected


def test_special_chars_rejected() -> None:
    """Characters outside [A-Za-z0-9_\\-] must raise ValueError."""
    for bad in ("U1;DROP", "G1&x=1", "U<script>", "G1%2F.."):
        try:
            validate_scim_id(bad, "test_id")
            raise AssertionError(f"Expected ValueError for {bad!r}")
        except ValueError:
            pass  # expected


# ---------- safe_error_context ----------

def test_safe_error_context_filters_keys() -> None:
    """Only safe keys should survive; token-like keys must be stripped."""
    resp = {
        "ok": False,
        "error": "invalid_auth",
        "token": "xoxb-should-not-appear",
        "headers": {"Authorization": "Bearer secret"},
        "needed": "admin",
        "provided": "user",
    }
    result = safe_error_context(resp)
    assert "xoxb-should-not-appear" not in result, f"Token leaked: {result}"
    assert "Bearer secret" not in result, f"Auth header leaked: {result}"
    assert "invalid_auth" in result, f"Error key missing: {result}"
    assert "admin" in result, f"Needed key missing: {result}"


def test_safe_error_context_truncates() -> None:
    """Output should be capped at max_len."""
    resp = {"ok": False, "error": "x" * 500}
    result = safe_error_context(resp, max_len=50)
    assert len(result) <= 53, f"Not truncated: len={len(result)}"  # 50 + "..."
    assert result.endswith("..."), f"Missing ellipsis: {result}"


def test_safe_error_context_non_dict() -> None:
    """Non-dict input should return a repr, not crash."""
    result = safe_error_context("raw string error")
    assert isinstance(result, str)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    specs = [
        CallSpec("validate_scim_id: valid IDs accepted", test_valid_ids_accepted),
        CallSpec("validate_scim_id: path traversal rejected", test_path_traversal_rejected),
        CallSpec("validate_scim_id: empty/whitespace rejected", test_empty_and_whitespace_rejected),
        CallSpec("validate_scim_id: special chars rejected", test_special_chars_rejected),
        CallSpec("safe_error_context: filters sensitive keys", test_safe_error_context_filters_keys),
        CallSpec("safe_error_context: truncates long output", test_safe_error_context_truncates),
        CallSpec("safe_error_context: handles non-dict", test_safe_error_context_non_dict),
    ]

    run_smoke("Security utilities smoke", specs)


if __name__ == "__main__":
    main()