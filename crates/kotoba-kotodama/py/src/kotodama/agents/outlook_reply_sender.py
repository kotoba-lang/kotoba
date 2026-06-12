"""Outlook reply sender — Phase 6 HITL send-after-approval.

Sends an approved reply draft via Microsoft Graph API.

Flow:
  apply_draft_verdict("approve") → send_reply_for_draft(draft_id, final_text)
    → get_message_context(email_vertex_id)   # message_id + account_did
    → get_access_token_for_account(account_did)  # with auto-refresh
    → send_reply(message_id, reply_text, access_token)
      POST https://graph.microsoft.com/v1.0/me/messages/{id}/reply
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

__all__ = ["send_reply_for_draft"]


# ── Internal helpers ───────────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _is_expired(iso: str) -> bool:
    """Return True if the ISO timestamp is within 30 seconds of now or unparseable."""
    if not iso:
        return True
    try:
        return (
            time.mktime(time.strptime(iso.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))
            <= time.time() + 30
        )
    except Exception:
        return True


def _expires(expires_in: Any) -> str:
    return time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() + max(0, int(expires_in or 3600))),
    )


def _client_credentials() -> tuple[str, str, str]:
    """Return (client_id, client_secret, tenant) from env vars."""
    client_id = (
        os.environ.get("OUTLOOK_CLIENT_ID")
        or os.environ.get("M365_CLIENT_ID")
        or ""
    )
    client_secret = (
        os.environ.get("OUTLOOK_CLIENT_SECRET")
        or os.environ.get("M365_CLIENT_SECRET")
        or ""
    )
    tenant = (
        os.environ.get("OUTLOOK_TENANT_ID")
        or os.environ.get("M365_TENANT_ID")
        or "common"
    )
    return client_id, client_secret, tenant


# ── Public helpers ─────────────────────────────────────────────────────


def get_message_context(email_vertex_id: str) -> dict | None:
    """Return {"message_id": ..., "account_did": ...} for the given email vertex.
    Updated to use kotoba Datom log.

    Returns None if the row is not found.
    """
    row = get_kotoba_client().select_first_where(
        "vertex_email_message",
        "vertex_id",
        email_vertex_id,
        columns=["message_id", "account_did"],
    )

    if row is None:
        return None

    return {"message_id": row.get("message_id", ""), "account_did": row.get("account_did", "")}


def get_access_token_for_account(account_did: str) -> str | None:
    """Return a valid access token for the given account DID.
    If the stored token is expired, attempts a refresh token exchange and
    updates vertex_outlook_oauth_connection with the new token.
    Updated to use kotoba Datom log.

    Returns None if no connected record exists or refresh fails.
    """
    row = get_kotoba_client().select_first_where(
        "vertex_outlook_oauth_connection",
        "user_key",
        account_did,
        columns=["access_token", "refresh_token", "expires_at", "connected"],
    )
    # R0: Apply additional filter `connected = true` in Python.
    if row is None or not row.get("connected"):
        return None

    access_token: str = row.get("access_token", "")
    refresh_token: str = row.get("refresh_token", "")
    expires_at: str = row.get("expires_at", "")

    if not _is_expired(expires_at):
        return access_token

    # Token is expired — attempt refresh
    if not refresh_token:
        return None

    client_id, client_secret, tenant = _client_credentials()
    if not client_id or not client_secret:
        return None

    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    params = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "scope": "https://graph.microsoft.com/.default offline_access",
    }

    try:
        req = urllib.request.Request(
            token_url,
            method="POST",
            data=urllib.parse.urlencode(params).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    new_access_token: str = data.get("access_token", "")
    new_refresh_token: str = data.get("refresh_token", refresh_token)
    new_expires_at: str = _expires(data.get("expires_in", 3600))

    if not new_access_token:
        return None

    get_kotoba_client().insert_row(
        "vertex_outlook_oauth_connection",
        {
            "user_key": account_did,  # Identity column for upsert
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "expires_at": new_expires_at,
            "connected": True,
        },
    )

    return new_access_token


def send_reply(message_id: str, reply_text: str, access_token: str) -> bool:
    """POST a reply to the given Graph message ID.

    Uses the /reply endpoint which sends the message immediately.
    Returns True on HTTP 202, raises on 4xx/5xx.
    """
    url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/reply"
    payload = json.dumps({"comment": reply_text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        status = resp.status  # type: ignore[attr-defined]

    return status == 202


def send_reply_for_draft(draft_id: str, reply_text: str) -> bool:
    """Send the approved reply for a draft.

    Looks up the email message context and OAuth token, then calls send_reply.
    Updated to use kotoba Datom log.

    Returns True on success, False if context or token is unavailable.
    Raises on Graph API 4xx/5xx errors.
    """
    row = get_kotoba_client().select_first_where(
        "vertex_email_reply_draft",
        "vertex_id",
        draft_id,
        columns=["email_vertex_id"],
    )

    if row is None:
        return False

    email_vertex_id: str = row.get("email_vertex_id", "")

    ctx = get_message_context(email_vertex_id)
    if ctx is None:
        return False

    message_id: str = ctx.get("message_id", "")
    account_did: str = ctx.get("account_did", "")

    if not message_id or not account_did:
        return False

    access_token = get_access_token_for_account(account_did)
    if not access_token:
        return False

    return send_reply(message_id, reply_text, access_token)
