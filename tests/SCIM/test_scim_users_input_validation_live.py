"""
Live integration tests for SCIM input validation.

SAFE — these tests verify that bad IDs are rejected locally before any
network call is made.  No Slack API calls are issued.
"""

from __future__ import annotations

from typing import Optional

import pytest
from unittest.mock import patch

from slack_objects.users import Users

from conftest_live import LiveTestContext, build_live_context

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ctx: Optional[LiveTestContext] = None


def _get_ctx() -> LiveTestContext:
    global _ctx
    if _ctx is None:
        _ctx = build_live_context()
    return _ctx


@pytest.fixture(scope="module")
def ctx() -> LiveTestContext:
    return _get_ctx()


@pytest.fixture(scope="module")
def users(ctx: LiveTestContext) -> Users:
    return ctx.slack.users()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScimInputValidation:
    """Cross-cutting input validation for SCIM methods."""

    @pytest.mark.parametrize("bad_id", [
        "../../admin",
        "U1/../../etc",
        "G1/../G2",
        "",
        " ",
        "U1 U2",
        "U1;DROP",
        "G1&x=1",
        "U<script>",
    ])
    def test_deactivate_rejects_bad_ids(self, users, bad_id):
        with patch.object(users, "_scim_request", wraps=users._scim_request) as spy:
            with pytest.raises(ValueError):
                users.scim_deactivate_user(bad_id)
            spy.assert_not_called()

    @pytest.mark.parametrize("bad_id", [
        "../../admin",
        "",
        " ",
        "U1;DROP",
    ])
    def test_reactivate_rejects_bad_ids(self, users, bad_id):
        with patch.object(users, "_scim_request", wraps=users._scim_request) as spy:
            with pytest.raises(ValueError):
                users.scim_reactivate_user(bad_id)
            spy.assert_not_called()

    @pytest.mark.parametrize("bad_id", [
        "../traversal",
        "",
        "id with spaces",
    ])
    def test_update_attribute_rejects_bad_ids(self, users, bad_id):
        with patch.object(users, "_scim_request", wraps=users._scim_request) as spy:
            with pytest.raises(ValueError):
                users.scim_update_user_attribute(
                    user_id=bad_id,
                    attribute="displayName",
                    new_value="x",
                )
            spy.assert_not_called()

    @pytest.mark.parametrize("bad_id", [
        "../traversal",
        "",
    ])
    def test_make_mcg_rejects_bad_ids(self, users, bad_id):
        with patch.object(users, "_scim_request", wraps=users._scim_request) as spy:
            with pytest.raises(ValueError):
                users.make_multi_channel_guest(bad_id)
            spy.assert_not_called()