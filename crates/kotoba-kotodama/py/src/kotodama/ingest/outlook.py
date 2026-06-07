"""Outlook/Microsoft Graph handlers for BPMN + Zeebe."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from datetime import datetime, timezone


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _random(size: int = 32) -> str:
    return _b64u(secrets.token_bytes(size))


def _challenge(verifier: str) -> str:
    return _b64u(hashlib.sha256(verifier.encode()).digest())


def _tenant() -> str:
    return os.environ.get("OUTLOOK_TENANT_ID") or os.environ.get("M365_TENANT_ID") or DEFAULT_TENANT


def _client() -> tuple[str, str, str]:
    client_id = os.environ.get("OUTLOOK_CLIENT_ID") or os.environ.get("M365_CLIENT_ID") or os.environ.get("SS_OUTLOOK_CLIENT_ID") or ""
    client_secret = (
        os.environ.get("OUTLOOK_CLIENT_SECRET")
        or os.environ.get("M365_CLIENT_SECRET")
        or os.environ.get("SS_M365_CLIENT_SECRET")
        or os.environ.get("SS_OUTLOOK_CLIENT_SECRET")
        or ""
    )
    tenant = _tenant()
    if not client_id or not client_secret:
        raise RuntimeError("Outlook OAuth client credentials are not configured")
    return client_id, client_secret, tenant


def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-outlook-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _form(url: str, params: dict[str, str]) -> dict[str, Any]:
    return _http_json(url, method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=urllib.parse.urlencode(params).encode())


def _expires(expires_in: Any) -> str:
    return datetime.fromtimestamp(time.time() + max(0, int(expires_in or 3600)), tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_expired(iso: str) -> bool:
    if not iso:
        return True
    try:
        return time.mktime(time.strptime(iso.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")) <= time.time() + 30
    except Exception:
        return True


def _rkey(key: str) -> str:
    return "".join(c if c.isalnum() or c in "._~-" else "-" for c in key.lower())[:200] or "anon"


def _view(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row or not row.get("connected"):
        return {"connected": False}
    return {
        "connected": True,
        "display_name": row.get("display_name") or "",
        "email": row.get("email") or "",
        "expires_at": row.get("expires_at") or "",
        "scope": row.get("scope") or "",
        "token_type": row.get("token_type") or "Bearer",
    }


def get_oauth_config(**_: Any) -> dict[str, Any]:
    client_id, _secret, tenant = _client()
    return {"ok": True, "clientId": client_id, "tenantId": tenant, "scope": SCOPE}


def get_auth_status(userId: str = "", actorId: str = "", **_: Any) -> dict[str, Any]:
    signed = bool(userId and userId != "anon")
    return {"ok": True, "signed_in": signed, "user_id": userId if signed else None, "actor_id": actorId if signed else None}


def start_auth(redirect_uri: str = "https://outlook.etzhayyim.com/auth/callback", **kwargs: Any) -> dict[str, Any]:
    client_id, _secret, tenant = _client()
    key = _user_key(**kwargs)
    state = _random(24)
    verifier = _random(48)
    auth = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
    qs = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": SCOPE,
        "state": state,
        "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256",
    })
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    get_kotoba_client().insert_row(
        "vertex_outlook_pending_oauth",
        {
            "vertex_id": f"{ACTOR}/pending/{_rkey(key)}",
            "user_key": key,
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "created_at": now,
            "expires_at": datetime.fromtimestamp(time.time() + PENDING_TTL_SEC, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )
    return {"ok": True, "auth_url": f"{auth}?{qs}", "state": state, "code_verifier": verifier, "expires_in": PENDING_TTL_SEC}


def _pending(key: str) -> dict[str, Any] | None:
    row = get_kotoba_client().select_first_where("vertex_outlook_pending_oauth", "user_key", key)
    if row and _is_expired(_str(row.get("expires_at"))):
        # R0: Explicit DELETE not directly supported by shims; using q() as Datalog escape hatch for retraction.
        entity_id_to_retract = get_kotoba_client().q(f"""
            [:find ?e .
             :in $ ?user_key
             :where
             [?e :vertex_outlook_pending_oauth/user_key ?user_key]]
        """, args=[key])
        if entity_id_to_retract:
            get_kotoba_client().q(f"""
                [[:db.fn/retractEntity {entity_id_to_retract}]]
            """)
        return None
    return row


def _fetch_me(access: str) -> dict[str, Any]:
    return _http_json("https://graph.microsoft.com/v1.0/me?$select=displayName,mail,userPrincipalName", headers={"authorization": f"Bearer {access}"})


def _sync_summary(access: str, limit: int = 25) -> dict[str, Any]:
    top = max(1, min(int(limit or 25), 100))
    try:
        mail = _http_json(f"https://graph.microsoft.com/v1.0/me/messages?$top={top}&$select=id,subject,from,receivedDateTime", headers={"authorization": f"Bearer {access}"})
        cal = _http_json(f"https://graph.microsoft.com/v1.0/me/events?$top={top}&$select=id,subject,start,end", headers={"authorization": f"Bearer {access}"})
        emails = len(mail.get("value") or [])
        events = len(cal.get("value") or [])
        current_time_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return {"last_synced_at": current_time_iso, "emails_found": emails, "emails_saved": emails, "calendar_events_found": events, "calendar_events_saved": events}
    except Exception as e:
        current_time_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return {"last_synced_at": current_time_iso, "emails_found": 0, "emails_saved": 0, "calendar_events_found": 0, "calendar_events_saved": 0, "error": str(e)[:240]}


def exchange_code(code: str = "", redirect_uri: str = "https://outlook.etzhayyim.com/auth/callback", state: str = "", code_verifier: str = "", **kwargs: Any) -> dict[str, Any]:
    if not code:
        return {"ok": False, "error": "code required"}
    client_id, client_secret, tenant = _client()
    key = _user_key(**kwargs)
    pending = _pending(key)
    verifier = code_verifier or _str((pending or {}).get("code_verifier"))
    if not verifier:
        return {"ok": False, "error": "code_verifier required"}
    if pending and state and pending.get("state") != state:
        return {"ok": False, "error": "OAuth state mismatch"}
    tokens = _form(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
        "code_verifier": verifier,
    })
    access = _str(tokens.get("access_token"))
    if not access:
        return {"ok": False, "error": "Token exchange succeeded but access_token missing"}
    me = _fetch_me(access)
    sync = _sync_summary(access, 25)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    get_kotoba_client().insert_row(
        "vertex_outlook_oauth_connection",
        {
            "vertex_id": f"{ACTOR}/connection/{_rkey(key)}",
            "user_key": key,
            "connected": True,
            "access_token": access,
            "refresh_token": _str(tokens.get("refresh_token")),
            "expires_at": _expires(tokens.get("expires_in")),
            "token_type": _str(tokens.get("token_type") or "Bearer"),
            "display_name": _str(me.get("displayName")),
            "email": _str(me.get("mail") or me.get("userPrincipalName")),
            "scope": _str(tokens.get("scope") or SCOPE),
            "last_synced_at": sync["last_synced_at"],
            "created_at": now,
            "updated_at": now,
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )
    # R0: Explicit DELETE not directly supported by shims; using q() as Datalog escape hatch for retraction.
    entity_id_to_retract = get_kotoba_client().q(f"""
        [:find ?e .
         :in $ ?user_key
         :where
         [?e :vertex_outlook_pending_oauth/user_key ?user_key]]
    """, args=[key])
    if entity_id_to_retract:
        get_kotoba_client().q(f"""
            [[:db.fn/retractEntity {entity_id_to_retract}]]
        """)
    return {"ok": True, "connection": _view(_connection(key)), "sync": sync}


def _connection(key: str) -> dict[str, Any] | None:
    return get_kotoba_client().select_first_where("vertex_outlook_oauth_connection", "user_key", key)


def _refresh(row: dict[str, Any]) -> dict[str, Any]:
    if not _is_expired(_str(row.get("expires_at"))) and row.get("access_token"):
        return row
    refresh = _str(row.get("refresh_token"))
    if not refresh:
        return row
    client_id, client_secret, tenant = _client()
    tokens = _form(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "scope": SCOPE,
    })
    if not tokens.get("access_token"):
        raise RuntimeError("Refresh token response missing access_token")
    # Fetch the existing row to get all fields, then update the necessary ones for insert_row
    # Assuming `row` passed to _refresh already contains `user_key` and `vertex_id`
    existing_row = get_kotoba_client().select_first_where("vertex_outlook_oauth_connection", "vertex_id", row["vertex_id"])
    if existing_row:
        existing_row.update({
            "access_token": _str(tokens.get("access_token")),
            "refresh_token": _str(tokens.get("refresh_token") or refresh),
            "expires_at": _expires(tokens.get("expires_in")),
            "token_type": _str(tokens.get("token_type") or row.get("token_type") or "Bearer"),
            "scope": _str(tokens.get("scope") or row.get("scope") or SCOPE),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        })
        get_kotoba_client().insert_row("vertex_outlook_oauth_connection", existing_row)
    return _connection(_str(row.get("user_key"))) or row


def get_connection(**kwargs: Any) -> dict[str, Any]:
    row = _connection(_user_key(**kwargs))
    if not row or not row.get("connected"):
        return {"ok": True, "connection": {"connected": False}}
    try:
        return {"ok": True, "connection": _view(_refresh(row))}
    except Exception as e:
        return {"ok": False, "connection": {"connected": False}, "error": str(e)}


def sync_mailbox(limit: int = 25, **kwargs: Any) -> dict[str, Any]:
    key = _user_key(**kwargs)
    row = _connection(key)
    if not row or not row.get("connected"):
        current_time_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return {"ok": True, "sync": {"last_synced_at": current_time_iso, "emails_found": 0, "emails_saved": 0, "calendar_events_found": 0, "calendar_events_saved": 0, "error": "not connected"}}
    active = _refresh(row)
    sync = _sync_summary(_str(active.get("access_token")), limit)
    active_row = get_kotoba_client().select_first_where("vertex_outlook_oauth_connection", "vertex_id", active["vertex_id"])
    if active_row:
        active_row.update({
            "last_synced_at": sync["last_synced_at"],
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        })
        get_kotoba_client().insert_row("vertex_outlook_oauth_connection", active_row)
    get_kotoba_client().insert_row(
        "vertex_outlook_sync_job",
        {
            "vertex_id": f"{ACTOR}/sync/{int(time.time() * 1000)}",
            "user_key": key,
            "email": active.get("email"),
            "status": "failed" if sync.get("error") else "completed",
            "emails_found": sync["emails_found"],
            "emails_saved": sync["emails_saved"],
            "calendar_events_found": sync["calendar_events_found"],
            "calendar_events_saved": sync["calendar_events_saved"],
            "error": sync.get("error", ""),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "actor_did": ACTOR,
            "org_did": "anon",
        },
    )
    return {"ok": not bool(sync.get("error")), "sync": sync}


def disconnect(**kwargs: Any) -> dict[str, Any]:
    key = _user_key(**kwargs)
    # R0: Explicit DELETE not directly supported by shims; using q() as Datalog escape hatch for retraction.
    entity_id_to_retract = get_kotoba_client().q(f"""
        [:find ?e .
         :in $ ?user_key
         :where
         [?e :vertex_outlook_pending_oauth/user_key ?user_key]]
    """, args=[key])
    if entity_id_to_retract:
        get_kotoba_client().q(f"""
            [[:db.fn/retractEntity {entity_id_to_retract}]]
        """)
    connection_row = get_kotoba_client().select_first_where("vertex_outlook_oauth_connection", "user_key", key)
    if connection_row:
        connection_row.update({
            "connected": False,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        })
        get_kotoba_client().insert_row("vertex_outlook_oauth_connection", connection_row)
    return {"ok": True, "connection": {"connected": False}}


def card_home(**kwargs: Any) -> dict[str, Any]:
    conn = get_connection(**kwargs).get("connection") or {"connected": False}
    return {"ok": True, "contentType": "application/vnd.etzhayyim.card.list", "payload": {"title": "Outlook", "items": [{"label": "Connected", "value": "yes" if conn.get("connected") else "no"}, {"label": "Account", "value": _str(conn.get("email") or "-")}, {"label": "Last Sync", "value": "never"}]}}


def card_compose(**_: Any) -> dict[str, Any]:
    return {"ok": True, "contentType": "application/vnd.etzhayyim.card.form", "payload": {"title": "Compose", "fields": [{"key": "to", "type": "email", "required": True}, {"key": "subject", "type": "text", "required": True}, {"key": "body", "type": "textarea", "required": True}], "action": "outlook.send"}}


def card_action(action: str = "", **kwargs: Any) -> dict[str, Any]:
    if action == "outlook.disconnect":
        return {"ok": True, "contentType": "application/vnd.etzhayyim.card.confirmation", "payload": {"title": "Disconnect Outlook", "body": "Are you sure you want to disconnect?", "destructive": True}}
    return card_home(**kwargs)


def triage(**kwargs: Any) -> dict[str, Any]:
    """Run the outlook.triage.v1 LangGraph over untriaged vertex_email_message rows.

    Inputs (kwargs):
      batchSize: int = 50  (max 200)
      accountDid: str = ""  (filter, optional)

    Side effects:
      - UPDATE vertex_email_message SET triaged_at, triage_classification,
        triage_score, triage_reasons
      - Chain actor: INSERT/UPDATE vertex_yabai_entity + vertex_yabai_evidence
        (shares entity_id with gmail.triage → cross-channel reputation MV
        sees both sources automatically).
    """
    import asyncio

    from kotodama.agents.outlook_triage import outlook_triage_graph

    initial_state: dict[str, Any] = {
        "batchSize": int(kwargs.get("batchSize") or 50),
        "accountDid": str(kwargs.get("accountDid") or ""),
        "llmCalls": 0,
    }
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, outlook_triage_graph.ainvoke(initial_state))
                final = future.result()
        else:
            final = loop.run_until_complete(outlook_triage_graph.ainvoke(initial_state))
    except RuntimeError:
        final = asyncio.run(outlook_triage_graph.ainvoke(initial_state))

    return {
        "ok": True,
        "triaged": int(final.get("triagedTotal") or 0),
        "spam": int(final.get("spamTotal") or 0),
        "trash": int(final.get("trashTotal") or 0),
        "gray": int(final.get("grayTotal") or 0),
        "clean": int(final.get("cleanTotal") or 0),
        "yabaiEntities": int(final.get("yabaiEntities") or 0),
        "yabaiEvidence": int(final.get("yabaiEvidence") or 0),
        "llmCalls": int(final.get("llmCalls") or 0),
    }
