"""
Shared live-test configuration for integration tests against real Slack APIs.

Tokens are retrieved from Azure Key Vault via the PC_Azure package.
Test-user IDs and other identifiers are loaded from a JSON file.

Setup
-----
1.  Store your Slack tokens in Azure Key Vault:
        Bot-token-SB         – xoxb-... bot token with users:read and users:read.email scopes
        User-token-SB        – xoxp-... user token with admin scope (org-level admin + SCIM provisioning)

2.  Set the ``_KEYVAULT_NAME`` constant in this file to your Azure Key Vault name.

3.  Copy ``live_test_config.example.json`` to ``live_test_config.json`` and fill
    in the real Slack user/team IDs for your org.  This file is git-ignored and
    never committed.

Usage (individual files):
    python -m pytest tests/SCIM/test_scim_users_reactivate_live.py -v --tb=short
    python -m pytest tests/SCIM/test_scim_users_deactivate_live.py -v --tb=short
    python -m pytest tests/SCIM/test_scim_users_create_live.py -v --tb=short
    python -m pytest tests/SCIM/test_scim_users_update_attribute_live.py -v --tb=short
    python -m pytest tests/SCIM/test_scim_users_make_guest_live.py -v --tb=short
    python -m pytest tests/SCIM/test_scim_users_input_validation_live.py -v --tb=short
    python -m pytest tests/SCIM/test_scim_idp_groups_live.py -v --tb=short

Usage (run all SCIM Users tests, ordered safest → most destructive):
    python tests/SCIM/run_all_scim_users_live_tests.py -v --tb=short
    python tests/SCIM/run_all_scim_users_live_tests.py --stop-on-fail
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from PC_Azure import Azure_Key_Vault as Key_Vault
from slack_objects import SlackObjectsClient, SlackObjectsConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_DEFAULT_CONFIG_PATH = _HERE.parent / "live_test_config.json"

# Azure Key Vault
_KEYVAULT_NAME = "Slack-AI-assistant-KV"

# Key Vault secret names
_SECRET_BOT_TOKEN = "Bot-token-SB"
_SECRET_USER_TOKEN = "User-token-SB"
_SECRET_SCIM_TOKEN = "User-token-SB"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json_config(path: Path | None = None) -> Dict[str, Any]:
    """Load the JSON file that contains test-user IDs and other identifiers."""
    path = path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Live-test config file not found: {path}\n"
            f"Copy 'live_test_config.example.json' to 'live_test_config.json' "
            f"and fill in the values for your Slack org."
        )
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _require_key(data: Dict[str, Any], key: str) -> str:
    """Return a non-empty string value from *data* or raise."""
    val = data.get(key)
    if not val:
        raise KeyError(
            f"Missing or empty key '{key}' in live_test_config.json."
        )
    return str(val)


def _optional_key(data: Dict[str, Any], key: str, default: str = "") -> str:
    return str(data.get(key, default))


# ---------------------------------------------------------------------------
# LiveTestContext
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LiveTestContext:
    """Holds all tokens, IDs, and the configured SlackObjectsClient."""
    cfg: SlackObjectsConfig
    slack: SlackObjectsClient
    logger: logging.Logger

    # IDs
    team_id: str
    channel_id: str
    idp_group_id: str

    # Active full member
    active_member_id: str
    active_member_email: str

    # Admin
    active_admin_id: str

    # Owner
    active_owner_id: str

    # Deactivated user
    deactivated_user_id: str
    deactivated_user_email: str

    # Guests
    single_channel_guest_id: str
    multi_channel_guest_id: str

    # Non-existent
    nonexistent_user_id: str
    nonexistent_email: str

    # Disposable users — tests may permanently change their type/state
    disposable_member_id: str
    disposable_member_email: str
    disposable_guest_id: str
    disposable_guest_email: str


def build_live_context(
    config_path: Path | None = None,
) -> LiveTestContext:
    """
    Read tokens from Azure Key Vault, load test identifiers from a JSON
    config file, and return a fully-wired ``LiveTestContext``.
    """
    # --- Azure Key Vault ---------------------------------------------------
    kv = Key_Vault(_KEYVAULT_NAME)
    bot_token = kv.get_secret(_SECRET_BOT_TOKEN)
    user_token = kv.get_secret(_SECRET_USER_TOKEN)
    scim_token = kv.get_secret(_SECRET_SCIM_TOKEN)

    cfg = SlackObjectsConfig(
        bot_token=bot_token,
        user_token=user_token,
        scim_token=scim_token,
    )

    logger = logging.getLogger("slack-objects.live-tests")
    logger.setLevel(logging.DEBUG)

    slack = SlackObjectsClient(cfg, logger=logger)

    # --- JSON config -------------------------------------------------------
    data = _load_json_config(config_path)

    return LiveTestContext(
        cfg=cfg,
        slack=slack,
        logger=logger,
        team_id=_require_key(data, "team_id"),
        channel_id=_optional_key(data, "channel_id"),
        idp_group_id=_optional_key(data, "idp_group_id"),
        active_member_id=_require_key(data, "active_member_id"),
        active_member_email=_require_key(data, "active_member_email"),
        active_admin_id=_require_key(data, "active_admin_id"),
        active_owner_id=_require_key(data, "active_owner_id"),
        deactivated_user_id=_require_key(data, "deactivated_user_id"),
        deactivated_user_email=_require_key(data, "deactivated_user_email"),
        single_channel_guest_id=_require_key(data, "single_channel_guest_id"),
        multi_channel_guest_id=_require_key(data, "multi_channel_guest_id"),
        nonexistent_user_id=_require_key(data, "nonexistent_user_id"),
        nonexistent_email=_require_key(data, "nonexistent_email"),
        disposable_member_id=_optional_key(data, "disposable_member_id"),
        disposable_member_email=_optional_key(data, "disposable_member_email"),
        disposable_guest_id=_optional_key(data, "disposable_guest_id"),
        disposable_guest_email=_optional_key(data, "disposable_guest_email"),
    )