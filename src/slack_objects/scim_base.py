"""
Shared SCIM plumbing for any object helper that makes SCIM REST calls.

Centralizes:
- ID validation (path-injection defense)
- Base URL construction
- Token-guarded HTTP request + JSON parsing
- Rate-tier sleep
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

from .config import RateTier

# Slack IDs are alphanumeric with hyphens/underscores.
_SLACK_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def validate_scim_id(value: str, label: str = "id") -> str:
    """Raise ValueError if *value* contains path-traversal or unexpected characters."""
    if not value or not _SLACK_ID_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


@dataclass
class ScimResponse:
    """Structured result for SCIM calls (no Slack 'ok' boolean)."""
    ok: bool
    status_code: int
    data: Dict[str, Any]
    text: str


class ScimMixin:
    """
    Mixin providing SCIM REST helpers.

    Requirements on the host class (satisfied by SlackObjectBase subclasses):
        - self.cfg   (SlackObjectsConfig)
        - self.scim_session  (requests.Session)
    """

    # --- URL ---

    def _scim_base_url(self) -> str:
        return f"{self.cfg.scim_base_url.rstrip('/')}/{self.cfg.scim_version}/"

    # --- Low-level request ---

    def _scim_request(
        self,
        *,
        path: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        raise_for_status: bool = True,
    ) -> ScimResponse:
        """
        Perform a SCIM REST request and return a ScimResponse.

        Raises ValueError when the token is missing.
        Raises requests.HTTPError on non-2xx when raise_for_status is True.
        """
        tok = token or self.cfg.scim_token
        if not tok:
            raise ValueError("SCIM request requires cfg.scim_token (or token override)")

        url = self._scim_base_url() + path.lstrip("/")
        headers = {
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json; charset=utf-8",
        }

        resp = self.scim_session.request(
            method=method.upper(),
            url=url,
            headers=headers,
            params=params,
            json=payload,
            timeout=self.cfg.http_timeout_seconds,
        )

        if raise_for_status:
            resp.raise_for_status()

        text = resp.text or ""
        try:
            data = resp.json() if text else {}
        except Exception:
            data = {"_raw_text": text}

        ok = resp.ok and (data.get("Errors") is None)

        time.sleep(float(RateTier.TIER_2))
        return ScimResponse(ok=ok, status_code=resp.status_code, data=data, text=text)