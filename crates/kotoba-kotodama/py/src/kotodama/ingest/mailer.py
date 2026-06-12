"""Mailer handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.gewp import (
    GewpMessage,
    compose_pgp_mime_raw,
    compose_resend_payload,
    new_message,
    new_thread_id,
    parse_from_email,
    to_dict as gewp_to_dict,
)
from kotodama.local_agent_env import load_keychain_secret
from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.pgp import lookup_public_key as _pgp_lookup

ACTOR = "did:web:mailer.etzhayyim.com"
INBOUND_REPO = "did:web:ml1nb0nd.etzhayyim.com"
INBOUND_COLLECTION = "com.etzhayyim.apps.mailer.inboundEmail"
PDS_ORIGIN = os.environ.get("PDS_ORIGIN", "https://atproto.etzhayyim.com")

_kotoba_client = get_kotoba_client()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any], str]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-mailer-zeebe/1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        return e.code, data, raw


KEYCHAIN_SECRET_REFS: dict[str, tuple[str, str]] = {
    "RESEND_API_KEY": ("etzhayyim.resend", "API_KEY"),
    "SS_RESEND_API_KEY": ("etzhayyim.resend", "API_KEY"),
    "EMAIL_RELAY_ADMIN_TOKEN": ("etzhayyim.email-relay", "ADMIN_TOKEN"),
    "SS_EMAIL_RELAY_ADMIN_TOKEN": ("etzhayyim.email-relay", "ADMIN_TOKEN"),
}


def _secret(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    for name in names:
        ref = KEYCHAIN_SECRET_REFS.get(name)
        if not ref:
            continue
        value = load_keychain_secret(service=ref[0], account=ref[1])
        if value:
            return value
    return ""


RESEND_SMTP_HOST = "smtp.resend.com"
RESEND_SMTP_PORT = 587


def _send_smtp(raw_mime: str, *, from_addr: str, to_addrs: list[str], api_key: str) -> None:
    """Send a raw RFC 2822 message via Resend SMTP relay (STARTTLS, port 587)."""
    import smtplib
    with smtplib.SMTP(RESEND_SMTP_HOST, RESEND_SMTP_PORT, timeout=45) as smtp:
        smtp.starttls()
        smtp.login("resend", api_key)
        smtp.sendmail(from_addr, to_addrs, raw_mime)


def health(**_: Any) -> dict[str, Any]:
    return {"ok": True, "app": "mailer", "ts": now_iso()}


def list_emails(limit: Any = 30, toLocal: str = "", **_: Any) -> dict[str, Any]:
    n = max(1, min(_int(limit, 30), 100))
    to_local = toLocal.lower().strip()

    # R0: Using Datalog q() for ORDER BY and optional WHERE.
    # Datalog query for list_emails
    query_edn_parts = [
        ":find", "(pull ?e [:vertex_id :message_id :from_address_hash :to_local :to_local_hash :subject :body_text :received_at_ms :content_protection :status])",
        ":where", "[?e :vertex_id]",
    ]
    query_args: dict[str, Any] = {}

    if to_local:
        query_edn_parts.append("[?e :to_local $to_local_param]")
        query_args["$to_local_param"] = to_local

    query_edn_parts.extend([
        ":order-by", "desc", "?received_at_ms",
        ":limit", "$n_param"
    ])
    query_args["$n_param"] = n

    rows_raw = _kotoba_client.q(json.dumps(query_edn_parts), args=query_args)
    rows = [row[0] for row in rows_raw] if rows_raw and isinstance(rows_raw[0], list) else rows_raw

    if not rows:
        return _list_emails_from_pds(n, to_local)
    items = [
        {
            "uri": row.get("vertex_id") or "",
            "cid": "",
            "messageId": row.get("message_id") or "",
            "toLocal": row.get("to_local") or "",
            "toLocalHash": row.get("to_local_hash") or "",
            "fromAddressHash": row.get("from_address_hash") or "",
            "subject": row.get("subject") or "",
            "bodyText": row.get("body_text") or "",
            "receivedAtMs": row.get("received_at_ms") or 0,
            "contentProtection": row.get("content_protection") or "plaintext",
            "status": row.get("status") or "",
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


def _list_emails_from_pds(limit: int, to_local: str) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"repo": INBOUND_REPO, "collection": INBOUND_COLLECTION, "limit": str(limit)})
    status, data, raw = _http_json(f"{PDS_ORIGIN}/xrpc/com.atproto.repo.listRecords?{qs}")
    if status >= 400:
        return {"items": [], "count": 0, "error": f"pds_{status}", "body": raw[:200]}
    records = data.get("records") if isinstance(data.get("records"), list) else []
    items = []
    for rec in records:
        value = rec.get("value") if isinstance(rec, dict) else {}
        if not isinstance(value, dict):
            continue
        item = {
            "uri": rec.get("uri") or "",
            "cid": rec.get("cid") or "",
            "toLocal": _str(value.get("toLocal")),
            "toLocalHash": _str(value.get("toLocalHash")),
            "fromAddressHash": _str(value.get("fromAddressHash")),
            "subject": _str(value.get("subject")),
            "bodyText": _str(value.get("bodyText")),
            "receivedAtMs": value.get("receivedAtMs"),
            "contentProtection": _str(value.get("contentProtection")) or "plaintext",
            "status": _str(value.get("status")),
        }
        if not to_local or item["toLocal"] == to_local:
            items.append(item)
    return {"items": items, "count": len(items)}


def list_bindings(limit: Any = 50, **_: Any) -> dict[str, Any]:
    n = max(1, min(_int(limit, 50), 200))

    # R0: Using Datalog q() for ORDER BY.
    query_edn_parts = [
        ":find", "(pull ?e [:email :did :direction :verified :created_at_ms])",
        ":where", "[?e :email]", # Assuming entities with :email attribute represent email bindings
        "[?e :created_at_ms ?created_at_ms]",
    ]
    query_args = {}

    query_edn_parts.extend([
        ":order-by", "desc", "?created_at_ms",
        ":limit", "$n_param"
    ])
    query_args["$n_param"] = n

    rows_raw = _kotoba_client.q(json.dumps(query_edn_parts), args=query_args)
    rows = [row[0] for row in rows_raw] if rows_raw and isinstance(rows_raw[0], list) else rows_raw

    items = [
        {
            "email": row.get("email") or "",
            "did": row.get("did") or "",
            "direction": row.get("direction") or "",
            "verified": bool(row.get("verified")),
            "createdAtMs": row.get("created_at_ms") or 0,
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


def stats(**_: Any) -> dict[str, Any]:
    # R0: Using Datalog q() for COUNT(*) without WHERE clause.
    emails_count_raw = _kotoba_client.q(json.dumps([":find", "(count ?e)", ":where", "[?e :vertex_id]"]), args={})
    emails_total = emails_count_raw[0][0] if emails_count_raw else 0

    bindings_count_raw = _kotoba_client.q(json.dumps([":find", "(count ?e)", ":where", "[?e :email]"]), args={})
    bindings_total = bindings_count_raw[0][0] if bindings_count_raw else 0

    return {"emails": _int(emails_total), "bindings": _int(bindings_total), "ts": now_iso()}


def send_email(to: str = "", subject: str = "", text: str = "", html: str = "", from_: str = "", fromAddress: str = "", replyTo: str = "", **kwargs: Any) -> dict[str, Any]:
    sender = from_ or fromAddress or _str(kwargs.get("from")) or "abuse-report@etzhayyim.com"
    if not to or not subject or not text:
        return {"error": "to/subject/text required"}
    api_key = _secret("RESEND_API_KEY", "SS_RESEND_API_KEY")
    if not api_key:
        return {"error": "RESEND_API_KEY not configured"}

    pgp_key: str | None = None
    try:
        pgp_key = _pgp_lookup(to)
    except Exception:
        pass

    content_protection = "plaintext"
    message_id = ""
    outbound_record_error = ""

    if pgp_key:
        from kotodama.primitives.pgp import build_pgp_mime_raw
        mime_msg, message_id = build_pgp_mime_raw(
            sender=sender, to_address=to, subject=subject,
            text_body=text, html_body=html or None,
            recipient_pubkey_armored=pgp_key, reply_to=replyTo,
        )
        content_protection = "pgp"
        status = 0
        raw = ""
        try:
            _send_smtp(mime_msg, from_addr=sender, to_addrs=[to], api_key=api_key)
            status = 200
        except Exception as exc:
            status = 500
            raw = str(exc)[:500]
        data: dict[str, Any] = {}
    else:
        payload: dict[str, Any] = {"from": sender, "to": [to], "subject": subject, "text": text}
        if html:
            payload["html"] = html
        if replyTo:
            payload["reply_to"] = replyTo
        status, data, raw = _http_json(
            "https://api.resend.com/emails",
            method="POST",
            headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
            body=json.dumps(payload).encode(),
        )
        message_id = _str(data.get("id"))

    sent_at = now_iso()
    try:
        _record_outbound(
            message_id, sender, to, subject, text, html,
            "resend", "sent" if status < 400 else "error",
            "" if status < 400 else raw[:500],
            content_protection=content_protection,
        )
    except Exception as exc:
        outbound_record_error = str(exc)[:300]
    if status >= 400:
        return {"error": "resend_api_failed", "status": status, "body": raw[:500], "outboundRecordError": outbound_record_error}
    result: dict[str, Any] = {
        "messageId": message_id, "provider": "resend", "from": sender,
        "to": to, "subject": subject, "sentAt": sent_at,
        "contentProtection": content_protection,
    }
    if outbound_record_error:
        result["outboundRecordError"] = outbound_record_error
    return result


def _record_outbound(
    message_id: str, sender: str, to: str, subject: str, text: str, html: str,
    provider: str, status: str, error: str,
    gewp_thread_id: str = "", gewp_step: int = 0,
    content_protection: str = "plaintext",
) -> None:
    rid = f"outbound-{uuid.uuid4().hex[:16]}"
    now_ms = int(time.time() * 1000)
    vertex_id = f"at://{ACTOR}/com.etzhayyim.apps.mailer.outboundEmail/{rid}"

    # R0: Replaced DELETE and INSERT with kotoba_datomic.insert_row for upsert.
    # Replaced SQL now() with Python datetime.now(timezone.utc).

    outbound_record = {
        "vertex_id": vertex_id,
        "sensitivity_ord": 1,
        "owner_did": ACTOR,
        "rkey": rid,
        "repo": ACTOR,
        "message_id": message_id,
        "from_address": sender,
        "to_address": to,
        "subject": subject,
        "body_text": text,
        "body_html": html,
        "provider": provider,
        "provider_message_id": message_id,
        "status": status,
        "error": error,
        "sent_at_ms": now_ms,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "org_id": 'anon',
        "user_id": 'anon',
        "actor_id": ACTOR,
        "gewp_thread_id": gewp_thread_id or None,
        "gewp_step": gewp_step or None,
        "content_protection": content_protection,
    }
    _kotoba_client.insert_row("vertex_mailer_outbound_email", outbound_record)


def provision_mailbox(handle: str = "", did: str = "", purpose: str = "", **_: Any) -> dict[str, Any]:
    local = handle.strip().lower()
    if not local:
        return {"error": "handle is required", "email": "", "did": ""}
    if not re.match(r"^[a-z][a-z0-9._-]{0,63}$", local):
        return {"error": "handle must be alpha-start, lowercase, kebab/dot/underscore", "email": "", "did": ""}
    recipient_did = did or f"did:web:{local}.etzhayyim.com"
    email = f"{local}@etzhayyim.com"
    relay_url = os.environ.get("EMAIL_RELAY_ADMIN_URL", "https://email-relay.etzhayyim.com/register-email")
    token = _secret("EMAIL_RELAY_ADMIN_TOKEN", "SS_EMAIL_RELAY_ADMIN_TOKEN")
    if not token:
        return {"email": email, "did": recipient_did, "registered": False, "error": "EMAIL_RELAY_ADMIN_TOKEN not configured"}
    status, data, raw = _http_json(
        relay_url,
        method="POST",
        headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
        body=json.dumps({"email": email, "did": recipient_did, "purpose": purpose or None}).encode(),
    )
    if status >= 400:
        return {"email": email, "did": recipient_did, "registered": False, "error": f"relay_{status}", "body": raw[:300]}
    return {"email": email, "did": recipient_did, "registered": data.get("ok") is True, "alreadyExisted": data.get("alreadyExisted") is True}


def send_gewp_message(
    to: str = "",
    subject: str = "",
    text: str = "",
    html: str = "",
    from_: str = "",
    fromAddress: str = "",
    replyTo: str = "",
    gewp_thread_id: str = "",
    gewp_step: int = 0,
    gewp_payload: dict[str, Any] | None = None,
    gewp_to_role: str = "vertex",
    gewp_to_node: str = "",
    gewp_sender_did: str = "",
    gewp_performative: str = "inform",
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a GEWP-conformant email (agent-to-agent or agent-to-human).

    Composes all 3 GEWP layers:
      Layer 1: application/vnd.gewp+json attachment (canonical)
      Layer 2: <!-- GEWP:{base64url} --> in HTML body (fallback)
      Layer 3: X-GEWP-* headers (best-effort routing hint)
    """
    sender = from_ or fromAddress or _str(kwargs.get("from")) or "mailer@etzhayyim.com"
    if not to or not subject:
        return {"error": "to/subject required"}
    api_key = _secret("RESEND_API_KEY", "SS_RESEND_API_KEY")
    if not api_key:
        return {"error": "RESEND_API_KEY not configured"}

    msg: GewpMessage = new_message(
        thread_id=gewp_thread_id or new_thread_id(),
        step=gewp_step,
        sender_id=f"https://{ACTOR.replace('did:web:', '')}",
        sender_email=sender,
        sender_did=gewp_sender_did or ACTOR,
        to_email=to,
        to_role=gewp_to_role,
        to_node=gewp_to_node,
        payload=gewp_payload or {},
        performative=gewp_performative,
        extensions=["ext:atproto"],
    )

    pgp_key: str | None = None
    try:
        pgp_key = _pgp_lookup(to)
    except Exception:
        pass

    html_body = html or f"<p>{text}</p>"
    content_protection = "pgp" if pgp_key else "plaintext"

    if pgp_key:
        mime_msg, message_id = compose_pgp_mime_raw(
            sender=sender, to_address=to, subject=subject,
            text_body=text, html_body=html_body,
            msg=msg, pgp_recipient_key=pgp_key, reply_to=replyTo,
        )
        status = 0
        raw = ""
        data: dict[str, Any] = {}
        try:
            _send_smtp(mime_msg, from_addr=sender, to_addrs=[to], api_key=api_key)
            status = 200
        except Exception as exc:
            status = 500
            raw = str(exc)[:500]
    else:
        resend_payload = compose_resend_payload(
            sender=sender, to_addresses=[to], subject=subject,
            text_body=text, html_body=html_body, msg=msg, reply_to=replyTo,
        )
        status, data, raw = _http_json(
            "https://api.resend.com/emails",
            method="POST",
            headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
            body=json.dumps(resend_payload).encode(),
        )
        message_id = _str(data.get("id"))
    sent_at = now_iso()
    try:
        _record_outbound(
            message_id, sender, to, subject, text, html_body,
            "resend", "sent" if status < 400 else "error",
            "" if status < 400 else raw[:500],
            gewp_thread_id=msg.thread.id,
            gewp_step=msg.thread.step,
            content_protection=content_protection,
        )
    except Exception:
        pass
    if status >= 400:
        return {"error": "resend_api_failed", "status": status, "body": raw[:500]}
    return {
        "messageId": message_id,
        "provider": "resend",
        "from": sender,
        "to": to,
        "subject": subject,
        "sentAt": sent_at,
        "gewpThreadId": msg.thread.id,
        "gewpStep": msg.thread.step,
        "contentProtection": content_protection,
    }


def parse_inbound_gewp(
    vertex_id: str = "",
    body_html: str = "",
    attachment_json: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Extract GEWP payload from a stored inbound email record.

    Tries Layer 1 (attachment_json) then Layer 2 (HTML comment).
    Returns {'type': 'human.intent'} when neither layer is present.
    """
    msg = parse_from_email(
        attachment_json=attachment_json or None,
        html_body=body_html or None,
    )
    if msg is None:
        return {"type": "human.intent", "vertexId": vertex_id, "gewp": None}

    try:
        if vertex_id:
            # R0: Replaced UPDATE with kotoba_datomic.insert_row leveraging its upsert behavior.
            update_record = {
                "vertex_id": vertex_id,
                "gewp_thread_id": msg.thread.id,
                "gewp_step": msg.thread.step,
                "gewp_type": msg.type,
                "gewp_performative": msg.performative,
            }
            _kotoba_client.insert_row("vertex_mailer_inbound_email", update_record)
    except Exception:
        pass

    return {
        "type": msg.type,
        "vertexId": vertex_id,
        "gewp": gewp_to_dict(msg),
    }


def register_pgp_key(email: str = "", publicKey: str = "", **_: Any) -> dict[str, Any]:
    """Register a PGP public key for an email address to enable E2EE outbound."""
    if not email or not publicKey:
        return {"error": "email and publicKey are required"}
    try:
        from kotodama.primitives.pgp import register_public_key
        return register_public_key(email, publicKey)
    except Exception as exc:
        return {"error": str(exc)[:300]}


def revoke_pgp_key(email: str = "", fingerprint: str = "", **_: Any) -> dict[str, Any]:
    """Revoke a registered PGP key."""
    if not email or not fingerprint:
        return {"error": "email and fingerprint are required"}
    try:
        from kotodama.primitives.pgp import revoke_public_key
        return revoke_public_key(email, fingerprint)
    except Exception as exc:
        return {"error": str(exc)[:300]}


def decrypt_inbound(
    vertex_id: str = "",
    private_key_armored: str = "",
    passphrase: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Decrypt a PGP-encrypted inbound email payload.

    Retrieves the stored ciphertext from vertex_mailer_inbound_email and
    decrypts it using the supplied private key. The private key is NOT stored
    server-side — it must be supplied by the caller at decrypt time.
    """
    if not vertex_id or not private_key_armored:
        return {"error": "vertex_id and private_key_armored are required"}

    # R0: Replaced _fetch_one with kotoba_datomic.select_first_where.
    row = _kotoba_client.select_first_where(
        "vertex_mailer_inbound_email",
        "vertex_id",
        vertex_id,
        columns=["body_text", "body_html", "gewp_attachment_json"],
    )
    if not row:
        return {"error": "not_found"}
    try:
        from kotodama.primitives.pgp import decrypt as pgp_decrypt
        ciphertext = row.get("body_text") or ""
        plaintext = pgp_decrypt(ciphertext, private_key_armored, passphrase or None)
        return {"vertexId": vertex_id, "plaintext": plaintext, "contentProtection": "pgp"}
    except Exception as exc:
        return {"error": str(exc)[:300]}


def handle_commit(collection: str = "", action: str = "", **_: Any) -> dict[str, Any]:
    if action and action != "create":
        return {"ok": True, "detail": "skip non-create"}
    if collection in (INBOUND_COLLECTION, "com.etzhayyim.apps.mailer.emailBinding"):
        return {"ok": True, "detail": f"processed {collection}"}
    return {"ok": True, "detail": "commit accepted"}


def heartbeat(**_: Any) -> dict[str, Any]:
    return {"ok": True, "actions": [{"action": "noop", "ts": now_iso()}]}
