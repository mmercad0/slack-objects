"""
Example: Search for a Slack user by email, including deactivated users.

Slack's Web API `users.lookupByEmail` does NOT return deactivated users.
To find deactivated users by email, use the SCIM API with a filter query.

Prerequisites:
    - Copy ``examples_config.example.json`` to ``examples_config.json``
      and fill in your Azure Key Vault name and secret names.
    - pip install slack-objects PC_Azure
"""

import json
from pathlib import Path

from PC_Azure import Azure_Key_Vault as Key_Vault
from slack_objects import SlackObjectsConfig, SlackObjectsClient

# ── Load config from git-ignored JSON file ────────────────────────────────
_CONFIG_PATH = Path(__file__).resolve().parent / "examples_config.json"
if not _CONFIG_PATH.exists():
    raise FileNotFoundError(
        f"Config file not found: {_CONFIG_PATH}\n"
        f"Copy 'examples_config.example.json' to 'examples_config.json' "
        f"and fill in the values."
    )

with open(_CONFIG_PATH, encoding="utf-8") as fh:
    _config = json.load(fh)

# ── Configuration ──────────────────────────────────────────────────────────
slack_key_vault = Key_Vault(_config["keyvault_name"])

bot_token = slack_key_vault.get_secret(_config["bot_token_secret"])
user_token = slack_key_vault.get_secret(_config["user_token_secret"])

cfg = SlackObjectsConfig(
    bot_token=bot_token,
    user_token=user_token,
    scim_token=user_token,
)

slack = SlackObjectsClient(cfg)
users = slack.users()

email = input("Enter the email address to search: ")

# ── Approach 1: Web API (active users only) ───────────────────────────────
print("\n--- Web API: users.lookupByEmail ---")
user_id = users.get_user_id_from_email(email)
if user_id:
    print(f"Found active user: {user_id}")
else:
    print("No active user found with that email.")

# ── Approach 2: SCIM API (active AND deactivated users) ───────────────────
print("\n--- SCIM API: GET /Users?filter=emails.value eq ... ---")
try:
    scim_resp = users.scim_search_user_by_email(email)

    resources = scim_resp.data.get("Resources", [])
    if not resources:
        print("No user found (active or deactivated) with that email.")
    else:
        for resource in resources:
            uid = resource.get("id", "N/A")
            username = resource.get("userName", "N/A")
            active = resource.get("active", "N/A")
            print(f"  User ID : {uid}")
            print(f"  Username: {username}")
            print(f"  Active  : {active}")
            print()
except Exception as e:
    print(f"SCIM error: {e}")

# ── Approach 3: resolve_user_id (Web API → SCIM fallback) ────────────────
print("\n--- resolve_user_id (automatic fallback) ---")
try:
    resolved_id = users.resolve_user_id(email)
    print(f"Resolved user ID: {resolved_id}")
except LookupError:
    print("No user found with that email (active or deactivated).")