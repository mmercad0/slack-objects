# slack-objects

A focused Python package for working with **Slack objects** commonly used in administration and automation workflows.

`slack-objects` provides **opinionated, testable wrappers** around the Slack Web API, Admin API, SCIM API, and Discovery API—favoring object-based access over raw endpoint calls.

---

## Supported Slack Objects

The following Slack object types are supported:

- **Users**
- **Conversations** (e.g, channels)
- **Messages**
- **Files**
- **Workspaces**
- **IDP Groups** (SCIM - e.g., Okta groups)

---

## Overview

`slack-objects` is designed for:

- Slack administration automation
- Identity and access management (IAM) workflows
- Internal tooling and bots
- Auditing and cleanup scripts

This package is **not** a replacement for `slack_sdk`.
Instead, it focuses on higher-level object operations that typically require:

- multiple API calls
- pagination
- rate limiting
- Admin API, SCIM, or Discovery API usage
- non-trivial orchestration logic

---

## Design Highlights

### Factory-based API

All object helpers are created from a single entry point:

```python
from slack_objects import SlackObjectsClient, SlackObjectsConfig

cfg = SlackObjectsConfig(
    bot_token="xoxb-...",
    user_token="xoxp-...",
    scim_token="xoxp-...",
    # see SlackObjectsConfig for additional options (team_id, scim_base_url, http_timeout_seconds, etc.)
)

slack = SlackObjectsClient(cfg)

users = slack.users()       # unbound
alice = slack.users("U123") # bound to user_id

conversations = slack.conversations()
conversations = slack.conversations("C123") # bound to channel_id

files = slack.files("F123") # bound to file_id

msgs = slack.messages(channel_id="C123", ts="...")  # bound to message

ws = slack.workspaces("T123")   # bound to workspace_id

idp = slack.idp_groups("S123")  # bound to group_id
```

This avoids global state while keeping usage concise and consistent.

---

### Explicit token model

Slack APIs have different authorization requirements.
This package keeps tokens **explicit and separate**:

| Token | Used for |
|-----|---------|
| `bot_token` | Slack Web API (most read/write operations) |
| `user_token` | Slack Admin API |
| `scim_token` | Slack SCIM API (IdP / provisioning) |

Tokens are **optional in configuration**, but **required by methods that need them**.
Errors are raised at call time with clear messages.

---

### Strict method boundaries

Each object follows a consistent internal structure:

```
public method
    → wrapper method
        → SlackApiCaller / SCIM request
```

---

### Keyword-only APIs

Methods with multiple optional parameters use **keyword-only arguments** to avoid ambiguity and future breaking changes.

---

### Testability

The codebase is designed to be tested **without hitting Slack**.

---

## Installation

Requires **Python 3.9+**.

```bash
pip install slack-objects
```

---

## Configuration

```python
from slack_objects import SlackObjectsClient, SlackObjectsConfig, RateTier

cfg = SlackObjectsConfig(
    bot_token="xoxb-...",
    user_token="xoxp-...",
    scim_token="xoxp-...",
    team_id="T0123ABC",                 # workspace ID; required for org-wide tokens calling workspace-scoped Web APIs
    default_rate_tier=RateTier.TIER_2,  # fallback sleep between API calls when no specific tier matches (default)
)
```

---

## Testing

Run unit tests:
```bash
python -m pytest tests/UnitTests -v --tb=short
```

Run all smoke tests:

```bash
python -m tests.Smoke.run_all_smoke
```

---

## Rate Limiting
All Slack Web/Admin API calls go through `SlackApiCaller`, which:

- Sleeps according to the resolved rate tier after every successful call
- Automatically retries on HTTP **429** (rate-limited) responses up to **5 times**, respecting the `Retry-After` header

Rate tiers are resolved in priority order:
explicit per-call tier → method-specific override → prefix rule → `default_rate_tier` from config.

---

## Notes

- SCIM v2 is the default; v1 is supported where applicable
- `PC_Utils` is a required dependency (used for datetime handling in `set_guest_expiration_date`)
- This package is intended for automation and administration workflows
- `resolve_user_id` accepts flexible identifiers (user ID, email, or @username) and verifies existence via Web API + SCIM fallback
- `is_user_authorized` supports IdP-group-based authorization checks with configurable read/write access levels
- SCIM user operations are available on `Users`: create, deactivate, reactivate, update attributes, update email, and convert to multi-channel guest
- Discovery API is used for `Users.get_channels` and `Conversations.get_members` (requires appropriate token scopes)