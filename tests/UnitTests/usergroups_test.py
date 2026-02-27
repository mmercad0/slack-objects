"""
Unit tests for slack_objects.usergroups
=======================================

All Slack API calls are mocked via ``api.call`` to test logic in isolation.

Run:  python -m pytest tests/UnitTests/usergroups_test.py -v --tb=short
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from slack_objects.config import SlackObjectsConfig, RateTier
from slack_objects.api_caller import SlackApiCaller
from slack_objects.usergroups import Usergroups


# ---------- helpers ----------

def _make_usergroups(
    *,
    usergroup_id: str | None = None,
    team_id: str | None = None,
) -> tuple[Usergroups, MagicMock]:
    """Return a ``Usergroups`` instance with a mocked ``api.call``."""
    cfg = SlackObjectsConfig(bot_token="xoxb-fake", team_id=team_id)
    client = MagicMock()
    api = MagicMock(spec=SlackApiCaller)
    ug = Usergroups(
        cfg=cfg,
        client=client,
        api=api,
        logger=logging.getLogger("test"),
        usergroup_id=usergroup_id,
    )
    return ug, api.call


# ---------- factory ----------

class TestWithUsergroup:
    def test_returns_new_bound_instance(self):
        ug, _ = _make_usergroups()
        bound = ug.with_usergroup("S0614TZR7")
        assert bound.usergroup_id == "S0614TZR7"
        assert bound is not ug

    def test_shares_cfg_and_api(self):
        ug, _ = _make_usergroups()
        bound = ug.with_usergroup("S0614TZR7")
        assert bound.cfg is ug.cfg
        assert bound.api is ug.api
        assert bound.client is ug.client


# ---------- identifier resolution ----------

class TestResolveUsergroupId:
    def test_uses_passed_value(self):
        ug, _ = _make_usergroups(usergroup_id="SBOUND")
        assert ug._resolve_usergroup_id("SPASSED") == "SPASSED"

    def test_falls_back_to_bound(self):
        ug, _ = _make_usergroups(usergroup_id="SBOUND")
        assert ug._resolve_usergroup_id() == "SBOUND"

    def test_raises_when_missing(self):
        ug, _ = _make_usergroups()
        with pytest.raises(ValueError, match="usergroup_id is required"):
            ug._resolve_usergroup_id()


# ---------- endpoint wrappers ----------

class TestUsergroupsList:
    def test_injects_team_id_when_configured(self):
        ug, mock_call = _make_usergroups(team_id="T1234")
        mock_call.return_value = {"ok": True, "usergroups": []}
        ug._usergroups_list()
        _, kwargs = mock_call.call_args
        assert kwargs.get("team_id") == "T1234"

    def test_omits_team_id_when_not_configured(self):
        ug, mock_call = _make_usergroups(team_id=None)
        mock_call.return_value = {"ok": True, "usergroups": []}
        ug._usergroups_list()
        _, kwargs = mock_call.call_args
        assert "team_id" not in kwargs

    def test_does_not_override_explicit_team_id(self):
        ug, mock_call = _make_usergroups(team_id="TCFG")
        mock_call.return_value = {"ok": True, "usergroups": []}
        ug._usergroups_list(team_id="TEXPLICIT")
        _, kwargs = mock_call.call_args
        assert kwargs.get("team_id") == "TEXPLICIT"


class TestUsergroupsUsersList:
    def test_injects_team_id_when_configured(self):
        ug, mock_call = _make_usergroups(team_id="T1234")
        mock_call.return_value = {"ok": True, "users": []}
        ug._usergroups_users_list("S123")
        _, kwargs = mock_call.call_args
        assert kwargs.get("team_id") == "T1234"
        assert kwargs.get("usergroup") == "S123"

    def test_omits_team_id_when_not_configured(self):
        ug, mock_call = _make_usergroups(team_id=None)
        mock_call.return_value = {"ok": True, "users": []}
        ug._usergroups_users_list("S123")
        _, kwargs = mock_call.call_args
        assert "team_id" not in kwargs


# ---------- get_usergroups ----------

class TestGetUsergroups:
    def test_returns_usergroups_list(self):
        ug, mock_call = _make_usergroups()
        mock_call.return_value = {
            "ok": True,
            "usergroups": [
                {"id": "S1", "name": "admins"},
                {"id": "S2", "name": "devs"},
            ],
        }
        result = ug.get_usergroups()
        assert len(result) == 2
        assert result[0]["id"] == "S1"

    def test_returns_empty_list_on_missing_key(self):
        ug, mock_call = _make_usergroups()
        mock_call.return_value = {"ok": True}
        assert ug.get_usergroups() == []


# ---------- get_members ----------

class TestGetMembers:
    def test_returns_correct_shape(self):
        ug, mock_call = _make_usergroups(usergroup_id="S123")
        mock_call.return_value = {"ok": True, "users": ["U1", "U2", "U3"]}
        members = ug.get_members()
        assert members == [
            {"value": "U1", "display": ""},
            {"value": "U2", "display": ""},
            {"value": "U3", "display": ""},
        ]

    def test_accepts_explicit_usergroup_id(self):
        ug, mock_call = _make_usergroups()
        mock_call.return_value = {"ok": True, "users": ["U9"]}
        members = ug.get_members(usergroup_id="SEXPLICIT")
        assert members == [{"value": "U9", "display": ""}]

    def test_empty_users(self):
        ug, mock_call = _make_usergroups(usergroup_id="S123")
        mock_call.return_value = {"ok": True, "users": []}
        assert ug.get_members() == []

    def test_raises_without_usergroup_id(self):
        ug, _ = _make_usergroups()
        with pytest.raises(ValueError, match="usergroup_id is required"):
            ug.get_members()


# ---------- is_member ----------

class TestIsMember:
    def test_true_when_present(self):
        ug, mock_call = _make_usergroups(usergroup_id="S123")
        mock_call.return_value = {"ok": True, "users": ["U1", "U2"]}
        assert ug.is_member("U2") is True

    def test_false_when_absent(self):
        ug, mock_call = _make_usergroups(usergroup_id="S123")
        mock_call.return_value = {"ok": True, "users": ["U1", "U2"]}
        assert ug.is_member("U999") is False

    def test_accepts_explicit_usergroup_id(self):
        ug, mock_call = _make_usergroups()
        mock_call.return_value = {"ok": True, "users": ["UTARGET"]}
        assert ug.is_member("UTARGET", usergroup_id="SEXPLICIT") is True

    def test_raises_without_usergroup_id(self):
        ug, _ = _make_usergroups()
        with pytest.raises(ValueError, match="usergroup_id is required"):
            ug.is_member("U1")