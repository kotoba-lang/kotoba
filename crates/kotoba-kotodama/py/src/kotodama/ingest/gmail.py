"""Gmail BPMN/Zeebe handlers.

Moves Gmail OAuth, sync, send/reply, and read-side commands out of the
Cloudflare Worker. The Worker remains an OAuth/XRPC edge facade.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from email.utils import parseaddr
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR = "did:web:gmail.etzhayyim.com"
TOKEN_TABLE = "vertex_gmail_oauth_token"
SCOPES = " ".join([
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "openid",
    "email",
    "profile",
])


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _gen(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}"





def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64u_json(part: str) -> dict[str, Any]:
    try:
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode()).decode())
    except Exception:
        return {}


def _decode_jwt_payload(jwt: str) -> dict[str, Any]:
    parts = jwt.split(".")
    return _b64u_json(parts[1]) if len(parts) == 3 else {}


def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-gmail-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _redirect_uri() -> str:
    return os.environ.get("GMAIL_GOOGLE_REDIRECT_URI", "https://gmail.etzhayyim.com/oauth/callback")


def _google_client() -> tuple[str, str]:
    return os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", ""), os.environ.get("SS_GOOGLE_OAUTH_CLIENT_SECRET", "")


def _exchange_code(code: str) -> dict[str, Any]:
    client_id, client_secret = _google_client()
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth client credentials not configured")
    body = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": _redirect_uri(),
        "grant_type": "authorization_code",
    }).encode()
    return _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)


def _refresh(refresh_token: str) -> dict[str, Any]:
    client_id, client_secret = _google_client()
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth client credentials not configured")
    body = urllib.parse.urlencode({
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }).encode()
    return _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)


def _active_token(email: str = "", account_did: str = "") -> dict[str, Any] | None:
    db = get_kotoba_client()
    if email:
        return db.select_first_where(TOKEN_TABLE, "email", email, columns=["*"])
    if account_did:
        return db.select_first_where(TOKEN_TABLE, "account_did", account_did, columns=["*"])
    # R0: Multi-predicate WHERE and ORDER BY is not directly supported by select_first_where.
    # Fetch all active tokens and apply ordering in Python.
    all_active_tokens = db.select_where(TOKEN_TABLE, "status", "active", columns=["*"], limit=2000)
    if not all_active_tokens:
        return None
    # Sort by COALESCE(last_sync_at, created_at) ASC
    all_active_tokens.sort(key=lambda t: t.get("last_sync_at") or t.get("created_at") or "")
    return all_active_tokens[0]


def _access_token(token: dict[str, Any]) -> str:
    now = int(time.time())
    cached = _str(token.get("access_token_cache"))
    expires = int(token.get("access_expires_at") or 0)
    if cached and expires > now + 30:
        return cached
    fresh = _refresh(_str(token.get("encrypted_refresh_token")))
    access = _str(fresh.get("access_token"))
    if not access:
        raise RuntimeError("Google token refresh did not return access_token")

    # Update the token dictionary with new values
    token["access_token_cache"] = access
    token["access_expires_at"] = now + int(fresh.get("expires_in") or 3600)
    token["updated_at"] = now_iso()

    # Use insert_row for upsert, it will update if vertex_id exists
    get_kotoba_client().insert_row(TOKEN_TABLE, token)
    return access


def _gmail(token: dict[str, Any], path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"authorization": f"Bearer {_access_token(token)}"}
    if data is not None:
        headers["content-type"] = "application/json"
    return _http_json(f"https://gmail.googleapis.com/gmail/v1{path}", method=method, headers=headers, body=data)


def _header(msg: dict[str, Any], name: str) -> str:
    headers = (((msg.get("payload") or {}).get("headers")) or [])
    for h in headers:
        if _str(h.get("name")).lower() == name.lower():
            return _str(h.get("value"))
    return ""


def _urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s<>\"']+", text or "")[:20]


def _base_row(collection: str, rkey: str) -> dict[str, Any]:
    now = now_iso()
    return {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.gmail.{collection}/{rkey}",
        "created_date": now[:10],
        "sensitivity_ord": 100,
        "owner_did": ACTOR,
        "rkey": rkey,
        "repo": ACTOR,
        "created_at": now,
        "org_id": "etzhayyim",
        "user_id": "system",
        "actor_id": "sys.gmail",
    }


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


def _insert(table: str, row: dict[str, Any]) -> None:
    get_kotoba_client().insert_row(table, row)


def _write(collection: str, data: dict[str, Any], rkey: str | None = None) -> None:
    key = rkey or _str(data.get(f"{collection}Id") or data.get("emailId") or data.get("jobId") or data.get("outboundId") or _gen(collection))
    row = _base_row(collection, key)
    for k, v in data.items():
        snake = _snake(k)
        if snake in row:
            continue
        row[snake] = json.dumps(v) if isinstance(v, (dict, list)) else v
    _insert(f"vertex_gmail_{_snake(collection)}", row)


def _phish_score(spf: str, dkim: str, dmarc: str, reply_to: str, from_addr: str, subject: str, urls: list[str]) -> int:
    score = 0
    if spf not in ("pass", "none"):
        score += 20
    if dkim not in ("pass", "none"):
        score += 20
    if dmarc not in ("pass", "none"):
        score += 25
    if reply_to and parseaddr(reply_to)[1].split("@")[-1] != parseaddr(from_addr)[1].split("@")[-1]:
        score += 15
    if re.search(r"urgent|verify|password|invoice|payment|account|suspend", subject or "", re.I):
        score += 15
    if urls:
        score += 10
    return min(score, 100)


def _write_alert(email_id: str, from_addr: str, subject: str, spf: str, dkim: str, dmarc: str, reply_to: str, urls: list[str]) -> None:
    score = _phish_score(spf, dkim, dmarc, reply_to, from_addr, subject, urls)
    if score < 60:
        return
    alert_id = _gen("phish")
    _write("phishingAlert", {
        "alertId": alert_id,
        "emailId": email_id,
        "fromAddr": from_addr,
        "subject": subject,
        "spfResult": spf,
        "dkimResult": dkim,
        "dmarcResult": dmarc,
        "bodyUrls": json.dumps(urls[:10]),
        "phishingScore": score,
        "reasons": "python:heuristic",
        "detectedAt": now_iso(),
    }, alert_id)


def _persist_message(token: dict[str, Any], msg: dict[str, Any]) -> str:
    from_hdr = _header(msg, "From")
    subject = _header(msg, "Subject")
    reply_to = _header(msg, "Reply-To")
    auth = _header(msg, "Authentication-Results")
    spf = (re.search(r"spf=(\w+)", auth, re.I) or [None, "none"])[1]
    dkim = (re.search(r"dkim=(\w+)", auth, re.I) or [None, "none"])[1]
    dmarc = (re.search(r"dmarc=(\w+)", auth, re.I) or [None, "none"])[1]
    urls = _urls(_str(msg.get("snippet")))
    email_id = f"email-{msg['id']}"
    _write("email", {
        "emailId": email_id,
        "threadId": msg.get("threadId"),
        "messageId": _header(msg, "Message-ID"),
        "accountDid": token.get("account_did"),
        "accountEmail": token.get("email"),
        "fromAddr": from_hdr,
        "toAddrs": _header(msg, "To"),
        "ccAddrs": _header(msg, "Cc"),
        "bccAddrs": _header(msg, "Bcc"),
        "replyTo": reply_to,
        "returnPath": _header(msg, "Return-Path"),
        "subject": subject,
        "snippet": msg.get("snippet") or "",
        "bodyUrlsJson": json.dumps(urls),
        "labels": ",".join(msg.get("labelIds") or []),
        "direction": "inbound",
        "spfResult": spf,
        "dkimResult": dkim,
        "dmarcResult": dmarc,
        "historyId": msg.get("historyId") or "",
        "sizeEstimate": msg.get("sizeEstimate") or 0,
        "internalDate": msg.get("internalDate") or "",
    }, email_id)
    _write_alert(email_id, from_hdr, subject, spf, dkim, dmarc, reply_to, urls)
    return _str(msg.get("historyId"))


def connect_account(accountDid: str = "did:anonymous", email: str = "", **_: Any) -> dict[str, Any]:
    client_id, _secret = _google_client()
    if not client_id:
        return {"ok": False, "error": "SS_GOOGLE_OAUTH_CLIENT_ID not configured"}
    qs = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": accountDid or "did:anonymous",
        "access_type": "offline",
        "prompt": "consent",
        **({"login_hint": email} if email else {}),
    })
    _write("accountBinding", {"bindingId": _gen("binding"), "email": email, "status": "pending_oauth"}, _gen("binding"))
    return {"ok": True, "status": "pending_oauth", "oauthUrl": f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"}


def oauth_callback(code: str = "", error: str = "", state: str = "", **_: Any) -> dict[str, Any]:
    if error:
        return {"ok": False, "html": f"<h1>Gmail connect failed</h1><p>{error}</p>"}
    if not code:
        return {"ok": False, "html": "<h1>Missing code</h1>"}
    tokens = _exchange_code(code)
    refresh = _str(tokens.get("refresh_token"))
    payload = _decode_jwt_payload(_str(tokens.get("id_token")))
    email = _str(payload.get("email"))
    if not refresh or not email:
        return {"ok": False, "html": "<h1>Connect error</h1><p>missing refresh_token or email</p>"}
    account_did = state or "did:anonymous"
    now = now_iso()
    token_data = {
        "vertex_id": f"{account_did}|{email}",
        "account_did": account_did,
        "actor_did": account_did,
        "org_did": 'anon',
        "at_did": account_did if account_did.startswith(("did:plc:", "did:web:")) else None,
        "email": email,
        "encrypted_refresh_token": refresh,
        "wrapped_data_key": '',
        "iv": '',
        "scope": _str(tokens.get("scope") or SCOPES),
        "status": 'active',
        "created_at": now,
        "updated_at": now,
    }
    get_kotoba_client().insert_row(TOKEN_TABLE, token_data)
    _write("account", {"accountDid": account_did, "email": email, "displayName": _str(payload.get("name")), "status": "active", "scope": _str(tokens.get("scope") or SCOPES), "connectedAt": now}, email)
    return {"ok": True, "html": f"<h1>Gmail connected</h1><p>{email}</p>", "email": email}


def disconnect_account(accountEmail: str = "", email: str = "", **_: Any) -> dict[str, Any]:
    target = accountEmail or email
    if not target:
        return {"ok": False, "error": "accountEmail required"}

    db = get_kotoba_client()
    token_to_update = db.select_first_where(TOKEN_TABLE, "email", target, columns=["*"])
    if token_to_update:
        token_to_update["status"] = 'disconnected'
        token_to_update["updated_at"] = now_iso()
        db.insert_row(TOKEN_TABLE, token_to_update)

    _write("accountBinding", {"bindingId": _gen("binding"), "email": target, "status": "disconnected"}, _gen("binding"))
    return {"ok": True, "status": "disconnected"}


def sync_inbox(email: str = "", accountDid: str = "", maxResults: int = 25, pageToken: str = "", query: str = "", **_: Any) -> dict[str, Any]:
    token = _active_token(email=email, account_did=accountDid)
    if not token:
        return {"ok": False, "error": "No active Gmail account connected. Call connectAccount first."}
    job_id = _gen("sync")
    try:
        params = urllib.parse.urlencode({k: v for k, v in {"maxResults": str(max(1, min(int(maxResults or 25), 500))), "pageToken": pageToken, "q": query}.items() if v})
        listing = _gmail(token, f"/users/me/messages?{params}")
        latest = ""
        synced = 0
        for item in (listing.get("messages") or []):
            msg = _gmail(token, f"/users/me/messages/{item['id']}?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Cc&metadataHeaders=Bcc&metadataHeaders=Subject&metadataHeaders=Reply-To&metadataHeaders=Return-Path&metadataHeaders=Message-ID&metadataHeaders=Date&metadataHeaders=Authentication-Results")
            latest = _persist_message(token, msg) or latest
            synced += 1
        if latest:
            # Update the token dictionary with new values
            token["history_id"] = latest
            token["last_sync_at"] = now_iso()
            token["updated_at"] = now_iso()
            # Use insert_row for upsert, it will update if vertex_id exists
            get_kotoba_client().insert_row(TOKEN_TABLE, token)
        _write("syncJob", {"jobId": job_id, "accountDid": token.get("account_did"), "email": token.get("email"), "kind": "full", "status": "completed", "messagesSynced": synced, "endHistoryId": latest, "completedAt": now_iso()}, job_id)
        return {"ok": True, "jobId": job_id, "status": "completed", "messagesSynced": synced, "historyId": latest, "nextPageToken": listing.get("nextPageToken")}
    except Exception as e:
        _write("syncJob", {"jobId": job_id, "email": token.get("email"), "kind": "full", "status": "failed", "error": str(e), "completedAt": now_iso()}, job_id)
        return {"ok": False, "error": str(e), "jobId": job_id, "status": "failed"}


def _raw_mime(from_addr: str, to: list[str], subject: str, body: str, in_reply_to: str = "", references: str = "") -> str:
    lines = [f"From: {from_addr}", f"To: {', '.join(to)}", f"Subject: {subject}", "MIME-Version: 1.0", "Content-Type: text/plain; charset=UTF-8", "Content-Transfer-Encoding: 7bit"]
    if in_reply_to:
        lines.append(f"In-Reply-To: {in_reply_to}")
    if references:
        lines.append(f"References: {references}")
    lines.extend(["", body])
    return _b64u("\r\n".join(lines).encode())


def send_email(accountEmail: str = "", accountDid: str = "", to: Any = None, subject: str = "", body: str = "", **_: Any) -> dict[str, Any]:
    recipients = to if isinstance(to, list) else []
    if not recipients or not subject or not body:
        return {"ok": False, "error": "to, subject, body required"}
    token = _active_token(email=accountEmail, account_did=accountDid)
    if not token:
        return {"ok": False, "error": "No active Gmail account"}
    outbound_id = _gen("outbound")
    try:
        res = _gmail(token, "/users/me/messages/send", method="POST", payload={"raw": _raw_mime(_str(token["email"]), recipients, subject, body)})
        _write("outboundEmail", {"outboundId": outbound_id, "accountDid": token.get("account_did"), "accountEmail": token.get("email"), "toAddrs": ",".join(recipients), "subject": subject, "bodyPreview": body[:300], "gmailMessageId": res.get("id"), "threadId": res.get("threadId"), "status": "sent", "sentAt": now_iso()}, outbound_id)
        return {"ok": True, "outboundId": outbound_id, "gmailMessageId": res.get("id"), "threadId": res.get("threadId"), "status": "sent"}
    except Exception as e:
        _write("outboundEmail", {"outboundId": outbound_id, "accountEmail": token.get("email"), "toAddrs": ",".join(recipients), "subject": subject, "status": "failed", "error": str(e)}, outbound_id)
        return {"ok": False, "error": str(e), "outboundId": outbound_id, "status": "failed"}


def reply_to_thread(accountEmail: str = "", accountDid: str = "", threadId: str = "", inReplyTo: str = "", body: str = "", **_: Any) -> dict[str, Any]:
    if not threadId or not body:
        return {"ok": False, "error": "threadId, body required"}
    token = _active_token(email=accountEmail, account_did=accountDid)
    if not token:
        return {"ok": False, "error": "No active Gmail account"}
    thread = _gmail(token, f"/users/me/threads/{urllib.parse.quote(threadId)}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Message-ID&metadataHeaders=References")
    messages = thread.get("messages") or []
    if not messages:
        return {"ok": False, "error": "thread not found"}
    last = messages[-1]
    to = [_header(last, "From")]
    subject = re.sub(r"^(Re:\s*)*", "Re: ", _header(last, "Subject"), flags=re.I)
    msg_id = inReplyTo or _header(last, "Message-ID")
    references = " ".join([x for x in [_header(last, "References"), msg_id] if x])
    raw = _raw_mime(_str(token["email"]), to, subject, body, msg_id, references)
    outbound_id = _gen("outbound")
    try:
        res = _gmail(token, "/users/me/messages/send", method="POST", payload={"raw": raw, "threadId": threadId})
        _write("outboundEmail", {"outboundId": outbound_id, "accountDid": token.get("account_did"), "accountEmail": token.get("email"), "toAddrs": ",".join(to), "subject": subject, "bodyPreview": body[:300], "threadId": res.get("threadId"), "inReplyTo": msg_id, "gmailMessageId": res.get("id"), "status": "sent", "sentAt": now_iso()}, outbound_id)
        return {"ok": True, "outboundId": outbound_id, "gmailMessageId": res.get("id"), "threadId": res.get("threadId"), "status": "sent"}
    except Exception as e:
        _write("outboundEmail", {"outboundId": outbound_id, "accountEmail": token.get("email"), "toAddrs": ",".join(to), "subject": subject, "threadId": threadId, "status": "failed", "error": str(e)}, outbound_id)
        return {"ok": False, "error": str(e), "outboundId": outbound_id, "status": "failed"}


def list_accounts(**_: Any) -> dict[str, Any]:
    db = get_kotoba_client()
    # R0: Using q() to fetch all records from TOKEN_TABLE as select_where requires a specific column-value predicate.
    # Datalog query to find all entities of type TOKEN_TABLE and pull all their attributes.
    # Assuming Datalog entity type for 'vertex_gmail_oauth_token' is ':vertex.gmail-oauth-token' and primary key is 'vertex-id'.
    entity_type_datalog = TOKEN_TABLE.replace("vertex_", "vertex.").replace("_", "-")
    query_edn = f'[:find (pull ?e [*]) :where [?e :{entity_type_datalog}/vertex-id ?id]]'
    raw_tokens = db.q(query_edn)

    # The result of q is a list of lists, where each inner list contains one pulled entity map.
    all_tokens = [item[0] for item in raw_tokens if item]

    # Sort by created_at DESC in Python
    all_tokens.sort(key=lambda r: r.get("created_at") or "", reverse=True)

    rows = []
    for r in all_tokens:
        rows.append({
            "email": r.get("email") or "",
            "displayName": r.get("display_name") or "",
            "status": r.get("status") or "",
            "scope": r.get("scope") or "",
            "historyId": r.get("history_id") or "",
            "lastSyncAt": r.get("last_sync_at") or "",
            "connectedAt": r.get("created_at") or ""
        })
    return {"ok": True, "accounts": rows, "total": len(rows)}


def list_threads(**_: Any) -> dict[str, Any]:
    return {"ok": True, "threads": [], "total": 0}


def search_emails(**_: Any) -> dict[str, Any]:
    return {"ok": True, "emails": [], "total": 0}


def get_thread(threadId: str = "", accountEmail: str = "", **_: Any) -> dict[str, Any]:
    if not threadId:
        return {"ok": False, "error": "threadId required"}
    token = _active_token(email=accountEmail)
    if not token:
        return {"ok": False, "error": "No active Gmail account"}
    thread = _gmail(token, f"/users/me/threads/{urllib.parse.quote(threadId)}?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject&metadataHeaders=Date")
    messages = [{"emailId": f"email-{m.get('id')}", "from": _header(m, "From"), "to": _header(m, "To"), "subject": _header(m, "Subject"), "snippet": m.get("snippet") or "", "sentAt": _header(m, "Date")} for m in (thread.get("messages") or [])]
    return {"ok": True, "threadId": thread.get("id"), "subject": (messages[0] or {}).get("subject", "") if messages else "", "messageCount": len(messages), "messages": messages}


def triage(**kwargs: Any) -> dict[str, Any]:
    """Run the gmail.triage.v1 LangGraph over untriaged vertex_gmail_email rows.

    Inputs (kwargs):
      batchSize: int = 50  (max 200)
      accountEmail: str = "" (filter, optional)

    Side effects:
      - UPDATE vertex_gmail_email SET triaged_at, triage_classification,
        triage_score, triage_reasons
      - Chain actor: INSERT/UPDATE vertex_yabai_entity + vertex_yabai_evidence
        per ADR-0032 (FraudSignal 0.85 / IntelExtraction 0.60 / gray 0.55)
    """
    import asyncio

    from kotodama.agents.gmail_triage import gmail_triage_graph

    initial_state: dict[str, Any] = {
        "batchSize": int(kwargs.get("batchSize") or 50),
        "accountEmail": str(kwargs.get("accountEmail") or ""),
        "llmCalls": 0,
    }
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # LangServer handler is already on an event loop; create_task style
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, gmail_triage_graph.ainvoke(initial_state))
                final = future.result()
        else:
            final = loop.run_until_complete(gmail_triage_graph.ainvoke(initial_state))
    except RuntimeError:
        final = asyncio.run(gmail_triage_graph.ainvoke(initial_state))

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


def cron_tick(**_: Any) -> dict[str, Any]:
    db = get_kotoba_client()
    # Fetch all active tokens, then sort and limit in Python
    all_active_tokens = db.select_where(TOKEN_TABLE, "status", "active", columns=["*"], limit=2000)
    all_active_tokens.sort(key=lambda t: t.get("last_sync_at") or t.get("created_at") or "")
    rows = all_active_tokens[:10]

    synced_total = 0
    errors = 0
    for token in rows:
        try:
            if token.get("history_id"):
                delta = _gmail(token, f"/users/me/history?startHistoryId={urllib.parse.quote(_str(token['history_id']))}&historyTypes=messageAdded")
                latest = _str(delta.get("historyId") or token.get("history_id"))
                synced = 0
                for item in [m["message"] for h in (delta.get("history") or []) for m in (h.get("messagesAdded") or [])][:50]:
                    msg = _gmail(token, f"/users/me/messages/{item['id']}?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Cc&metadataHeaders=Bcc&metadataHeaders=Subject&metadataHeaders=Reply-To&metadataHeaders=Return-Path&metadataHeaders=Message-ID&metadataHeaders=Date&metadataHeaders=Authentication-Results")
                    latest = _persist_message(token, msg) or latest
                    synced += 1
                # Update the token dictionary with new values
                token["history_id"] = latest
                token["last_sync_at"] = now_iso()
                token["updated_at"] = now_iso()
                # Use insert_row for upsert
                db.insert_row(TOKEN_TABLE, token)
                synced_total += synced
            else:
                result = sync_inbox(email=_str(token.get("email")), maxResults=25)
                synced_total += int(result.get("messagesSynced") or 0)
        except Exception:
            errors += 1
    return {"ok": errors == 0, "accounts": len(rows), "synced": synced_total, "errors": errors}
