# slack-objects

A focused Python package for working with **Slack objects** commonly used in administration and automation workflows.

`slack-objects` provides **opinionated, testable wrappers** around the Slack Web API, Admin API, and SCIM API—favoring object-based access over raw endpoint calls.

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
- Admin API or SCIM usage
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
    # see SlackObjectsConfig for additional options (scim_base_url, http_timeout_seconds, etc.)
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
    default_rate_tier=RateTier.TIER_3,  # fallback sleep between API calls when no specific tier matches
)
```

---

## Testing

Run all smoke tests:

```bash
python -m tests.run_all_smoke
```

---

## Notes

- SCIM v2 is the default; v1 is supported where applicable
- `PC_Utils` is an optional dependency (used for datetime handling in `set_guest_expiration_date`)
- This package is intended for automation and administration workflows
