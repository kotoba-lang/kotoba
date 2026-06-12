"""Google Workspace OAuth/sync stubs for Zeebe workers.

These handlers replace the previous Cloudflare Worker D1 token scaffolds for
tasks/sheets/drive/contacts/meet/docs/slides. The per-service sync behavior was already a
no-op scaffold in the Workers; this module preserves that behavior while moving
OAuth state and cron handling out of the edge runtime.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    "https://www.googleapis.com/auth/meetings.space.readonly",
])

TOKEN_TABLES = {
    "tasks": "vertex_gtasks_oauth_token",
    "sheets": "vertex_gsheets_oauth_token",
    "drive": "vertex_gdrive_oauth_token",
    "contacts": "vertex_gcontacts_oauth_token",
    "meet": "vertex_gmeet_oauth_token",
    "docs": "vertex_gdocs_oauth_token",
    "slides": "vertex_gslides_oauth_token",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _str(value: Any) -> str:
    return "" if value is None else str(value)



def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-gworkspace-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _decode_jwt_payload(jwt: str) -> dict[str, Any]:
    try:
        part = jwt.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode()).decode())
    except Exception:
        return {}


def _redirect_uri(app: str) -> str:
    return os.environ.get(f"{app.upper()}_GOOGLE_REDIRECT_URI", f"https://{app}.etzhayyim.com/oauth/callback")


def connect_account(app: str, accountDid: str = "did:anonymous", email: str = "", **_: Any) -> dict[str, Any]:
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        return {"ok": False, "error": "SS_GOOGLE_OAUTH_CLIENT_ID not configured"}
    qs = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": _redirect_uri(app),
        "response_type": "code",
        "scope": SCOPES,
        "state": accountDid or "did:anonymous",
        "access_type": "offline",
        "prompt": "consent",
        **({"login_hint": email} if email else {}),
    })
    return {"ok": True, "status": "pending_oauth", "oauthUrl": f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"}


def oauth_callback(app: str, code: str = "", error: str = "", state: str = "", **_: Any) -> dict[str, Any]:
    if error:
        return {"ok": False, "html": f"<h1>{app} connect failed</h1><p>{error}</p>"}
    if not code:
        return {"ok": False, "html": "<h1>Missing code</h1>"}
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return {"ok": False, "html": "<h1>Google OAuth credentials not configured</h1>"}
    body = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": _redirect_uri(app),
        "grant_type": "authorization_code",
    }).encode()
    tokens = _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)
    refresh = _str(tokens.get("refresh_token"))
    payload = _decode_jwt_payload(_str(tokens.get("id_token")))
    email = _str(payload.get("email"))
    if not refresh or not email:
        return {"ok": False, "html": "<h1>Connect error</h1><p>missing refresh_token or email</p>"}
    table = TOKEN_TABLES[app]
    now = now_iso()
    vid = f"{state or 'did:anonymous'}|{email}"
    actor = f"did:web:{app}.etzhayyim.com"
    get_kotoba_client().insert_row(
        table,
        {
            "vertex_id": vid,
            "account_did": state or "did:anonymous",
            "email": email,
            "encrypted_refresh_token": refresh,
            "wrapped_data_key": "",
            "iv": "",
            "scope": _str(tokens.get("scope") or SCOPES),
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "actor_did": actor,
            "org_did": "anon",
        },
    )
    _write_account(app, state or "did:anonymous", email, _str(payload.get("name")), _str(tokens.get("scope") or SCOPES))
    return {"ok": True, "html": f"<h1>Google {app.title()} connected</h1><p>{email}</p>", "email": email}


def _write_account(app: str, account_did: str, email: str, display_name: str, scope: str) -> None:
    table = {
        "tasks": "vertex_gtasks_account",
        "sheets": "vertex_gsheets_account",
        "drive": "vertex_gdrive_account",
        "contacts": "vertex_gcontacts_account",
        "meet": "vertex_gmeet_account",
        "docs": "vertex_gdocs_account",
        "slides": "vertex_gslides_account",
    }[app]
    actor = f"did:web:{app}.etzhayyim.com"
    now = now_iso()
    vid = f"at://{actor}/com.etzhayyim.apps.{app}.account/{email}"
    get_kotoba_client().insert_row(
        table,
        {
            "vertex_id": vid,
            "created_date": now[:10],
            "sensitivity_ord": 100,
            "owner_did": actor,
            "rkey": email,
            "repo": actor,
            "account_did": account_did,
            "email": email,
            "display_name": display_name,
            "status": "active",
            "scope": scope,
            "last_sync_at": "",
            "connected_at": now,
            "created_at": now,
            "org_id": "anon",
            "user_id": "anon",
            "actor_id": f"{app}-mcp",
            "actor_did": actor,
            "org_did": "anon",
        },
    )


def sync_from_google(app: str, email: str = "", **_: Any) -> dict[str, Any]:
    if not email:
        return {"ok": False, "error": "email required"}
    # R0: Multi-predicate filter applied in Python
    row = get_kotoba_client().select_first_where(TOKEN_TABLES[app], "email", email)
    if row and row.get("status") != "active":
        row = None
    if not row:
        return {"ok": False, "error": "No active account. connectAccount first."}
    return {"ok": True, "jobId": f"gsync-{app}-{int(time.time())}", "synced": 0}


def cron_tick(app: str, **_: Any) -> dict[str, Any]:
    # R0: ORDER BY and COALESCE applied in Python after fetching.
    fetched_rows = get_kotoba_client().select_where(
        TOKEN_TABLES[app],
        "status",
        "active",
        columns=["email", "last_sync_at", "created_at"],
        limit=1000, # Fetch a larger set to ensure we get 10 after sorting
    )
    # Sort in Python based on COALESCE(last_sync_at, created_at)
    rows = sorted(
        fetched_rows,
        key=lambda r: r.get("last_sync_at") or r.get("created_at") or "",
    )[:10]

    return {"ok": True, "accounts": len(rows), "synced": 0, "errors": 0}
