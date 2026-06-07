"""etzhayyim Email Wire Protocol (GEWP) v1.0 — core protocol module.

Spec: https://spec.etzhayyim.com/gewp/v1/
License: Apache-2.0
MIME type: application/vnd.gewp+json

3-layer redundancy:
  Layer 1 (canonical): MIME attachment  application/vnd.gewp+json
  Layer 2 (fallback):  HTML comment     <!-- GEWP:{base64url(payload)} -->
  Layer 3 (hint):      X-GEWP-* headers (best-effort, stripped on forward)
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

GEWP_VERSION = "1.0"
GEWP_MIME_TYPE = "application/vnd.gewp+json"
GEWP_ATTACHMENT_NAME = "gewp.json"
_GEWP_COMMENT_RE = re.compile(r"<!-- GEWP:([A-Za-z0-9_=+-]+) -->")
_GEWP_PGP_COMMENT_RE = re.compile(r"<!-- GEWP-PGP:([A-Za-z0-9_=+-]+) -->")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class GewpThread:
    id: str
    step: int
    root_message_id: str = ""
    graph: str = ""           # ext:langgraph
    run_id: str = ""          # ext:langgraph
    barrier_total: int = 0    # ext:pregel — 0 means no barrier
    barrier_timeout_s: int = 300  # ext:pregel


@dataclass
class GewpActor:
    id: str                    # actor IRI (REQUIRED)
    type: str = "Service"      # AS2.0: Person | Service | Application
    email: str = ""
    did: str = ""              # ext:atproto
    handle: str = ""           # ext:atproto
    model: str = ""            # ext:langgraph (use resolveModelId())


@dataclass
class GewpRecipient:
    role: str                  # vertex | observer | human
    email: str = ""
    id: str = ""
    type: str = "Service"
    did: str = ""              # ext:atproto
    node: str = ""             # ext:langgraph — LangGraph node name


@dataclass
class GewpMessage:
    gewp: str
    type: str                  # pregel.message | pregel.barrier | human.intent
    thread: GewpThread
    sender: GewpActor
    to: list[GewpRecipient]
    payload: dict[str, Any]
    cc: list[GewpRecipient] = field(default_factory=list)
    performative: str = "inform"  # FIPA-ACL: inform|request|query-if|propose|confirm|refuse|failure
    extensions: list[str] = field(default_factory=list)
    state: dict[str, Any] | None = None
    auth: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Constructors
# ---------------------------------------------------------------------------

def new_thread_id() -> str:
    return f"thd_{uuid.uuid4().hex[:10]}"


def new_message(
    *,
    thread_id: str = "",
    step: int = 0,
    sender_id: str,
    sender_email: str = "",
    to_email: str,
    to_role: str = "vertex",
    payload: dict[str, Any],
    msg_type: str = "pregel.message",
    performative: str = "inform",
    extensions: list[str] | None = None,
    graph: str = "",
    run_id: str = "",
    to_node: str = "",
    sender_did: str = "",
    sender_handle: str = "",
    sender_model: str = "",
) -> GewpMessage:
    return GewpMessage(
        gewp=GEWP_VERSION,
        type=msg_type,
        performative=performative,
        extensions=extensions or [],
        thread=GewpThread(
            id=thread_id or new_thread_id(),
            step=step,
            graph=graph,
            run_id=run_id,
        ),
        sender=GewpActor(
            id=sender_id,
            email=sender_email,
            did=sender_did,
            handle=sender_handle,
            model=sender_model,
        ),
        to=[GewpRecipient(
            role=to_role,
            email=to_email,
            node=to_node,
        )],
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def to_dict(msg: GewpMessage) -> dict[str, Any]:
    thread: dict[str, Any] = {"id": msg.thread.id, "step": msg.thread.step}
    if msg.thread.root_message_id:
        thread["root_message_id"] = msg.thread.root_message_id
    if msg.thread.graph:
        thread["graph"] = msg.thread.graph
    if msg.thread.run_id:
        thread["run_id"] = msg.thread.run_id
    if msg.thread.barrier_total > 0:
        thread["barrier"] = {
            "total_vertices": msg.thread.barrier_total,
            "timeout_seconds": msg.thread.barrier_timeout_s,
        }

    sender: dict[str, Any] = {"id": msg.sender.id, "@type": msg.sender.type}
    if msg.sender.email:
        sender["email"] = msg.sender.email
    if msg.sender.did:
        sender["did"] = msg.sender.did
    if msg.sender.handle:
        sender["handle"] = msg.sender.handle
    if msg.sender.model:
        sender["model"] = msg.sender.model

    result: dict[str, Any] = {
        "gewp": msg.gewp,
        "type": msg.type,
        "performative": msg.performative,
        "thread": thread,
        "sender": sender,
        "to": [_recipient_dict(r) for r in msg.to],
        "payload": msg.payload,
    }
    if msg.cc:
        result["cc"] = [_recipient_dict(r) for r in msg.cc]
    if msg.extensions:
        result["extensions"] = msg.extensions
    if msg.state is not None:
        result["state"] = msg.state
    if msg.auth is not None:
        result["auth"] = msg.auth
    return result


def _recipient_dict(r: GewpRecipient) -> dict[str, Any]:
    d: dict[str, Any] = {"role": r.role, "@type": r.type}
    if r.email:
        d["email"] = r.email
    if r.id:
        d["id"] = r.id
    if r.did:
        d["did"] = r.did
    if r.node:
        d["node"] = r.node
    return d


def to_json(msg: GewpMessage) -> str:
    return json.dumps(to_dict(msg), ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Compose Resend API payload
# ---------------------------------------------------------------------------

def compose_resend_payload(
    *,
    sender: str,
    to_addresses: list[str],
    subject: str,
    text_body: str,
    html_body: str,
    msg: GewpMessage,
    reply_to: str = "",
) -> dict[str, Any]:
    """Build Resend API payload with all 3 GEWP layers embedded.

    Layer 1: attachment  application/vnd.gewp+json  (canonical, preserved by Resend)
    Layer 2: HTML comment <!-- GEWP:{base64url} -->  (fallback)
    Layer 3: X-GEWP-* headers                        (routing hint, best-effort)
    """
    payload_json = to_json(msg)
    payload_b64url = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    payload_b64std = base64.b64encode(payload_json.encode()).decode()

    html_with_layer2 = html_body + f"\n<!-- GEWP:{payload_b64url} -->"

    resend: dict[str, Any] = {
        "from": sender,
        "to": to_addresses,
        "subject": subject,
        "text": text_body,
        "html": html_with_layer2,
        "headers": {                      # Layer 3 (best-effort)
            "X-GEWP-Thread": msg.thread.id,
            "X-GEWP-Step": str(msg.thread.step),
            "X-GEWP-Type": msg.type,
        },
        "attachments": [                  # Layer 1 (canonical)
            {
                "filename": GEWP_ATTACHMENT_NAME,
                "content": payload_b64std,
                "content_type": GEWP_MIME_TYPE,
            }
        ],
    }
    if reply_to:
        resend["reply_to"] = reply_to
    return resend


def compose_pgp_mime_raw(
    *,
    sender: str,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str,
    msg: GewpMessage,
    pgp_recipient_key: str,
    reply_to: str = "",
    message_id: str = "",
) -> tuple[str, str]:
    """Build a PGP/MIME (RFC 3156) raw email with all 3 GEWP layers inside the ciphertext.

    Returns (raw_mime, message_id).

    Encrypted inner content structure:
      multipart/mixed
      ├── multipart/alternative  (Layer 2 HTML comment inside html part)
      │   ├── text/plain
      │   └── text/html  + <!-- GEWP:{b64url} -->
      └── application/vnd.gewp+json   (Layer 1)

    Outer envelope carries X-GEWP-* routing headers (Layer 3, unencrypted best-effort).
    """
    import email.mime.application
    import email.mime.multipart
    import email.mime.text
    import email.policy
    from email.utils import formatdate, make_msgid
    from kotodama.primitives.pgp import encrypt

    payload_json = to_json(msg)
    payload_b64url = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    html_with_layer2 = html_body + f"\n<!-- GEWP:{payload_b64url} -->"

    # Inner multipart/alternative (text + html with GEWP Layer 2)
    inner_alt = email.mime.multipart.MIMEMultipart("alternative")
    inner_alt.attach(email.mime.text.MIMEText(text_body, "plain", "utf-8"))
    inner_alt.attach(email.mime.text.MIMEText(html_with_layer2, "html", "utf-8"))

    # Inner multipart/mixed: alternative + GEWP Layer 1 attachment
    inner = email.mime.multipart.MIMEMultipart("mixed")
    inner["Subject"] = subject  # protected header (recovered by PGP-aware clients)
    inner.attach(inner_alt)

    gewp_part = email.mime.application.MIMEApplication(
        payload_json.encode("utf-8"), "vnd.gewp+json"
    )
    gewp_part.add_header("Content-Disposition", "attachment", filename=GEWP_ATTACHMENT_NAME)
    inner.attach(gewp_part)

    # Encrypt inner MIME with CRLF serialization (RFC 2822 §2.1)
    encrypted_str = encrypt(
        inner.as_bytes(policy=email.policy.SMTP).decode("utf-8"), pgp_recipient_key
    )

    msg_id = message_id or make_msgid(
        domain=sender.split("@")[-1] if "@" in sender else "etzhayyim.com"
    )

    # Outer PGP/MIME envelope (RFC 3156 §4)
    outer = email.mime.multipart.MIMEMultipart(
        "encrypted",
        protocol="application/pgp-encrypted",
    )
    outer["From"] = sender
    outer["To"] = to_address
    outer["Subject"] = "[Encrypted]"
    outer["Date"] = formatdate(localtime=False)
    outer["Message-ID"] = msg_id
    if reply_to:
        outer["Reply-To"] = reply_to
    # GEWP Layer 3: routing hints in outer headers (best-effort, stripped on forward)
    outer["X-GEWP-Thread"] = msg.thread.id
    outer["X-GEWP-Step"] = str(msg.thread.step)
    outer["X-GEWP-Type"] = msg.type
    outer["X-GEWP-Encrypted"] = "pgp"

    ver_part = email.mime.application.MIMEApplication(b"Version: 1\n", "pgp-encrypted")
    ver_part.add_header("Content-Disposition", "attachment", filename="version.asc")
    outer.attach(ver_part)

    enc_part = email.mime.application.MIMEApplication(
        encrypted_str.encode("ascii"), "octet-stream"
    )
    enc_part.add_header("Content-Disposition", "attachment", filename="encrypted.asc")
    outer.attach(enc_part)

    return outer.as_bytes(policy=email.policy.SMTP).decode("ascii"), msg_id


# ---------------------------------------------------------------------------
# Parse incoming email
# ---------------------------------------------------------------------------

def parse_from_email(
    *,
    attachment_json: str | None = None,
    html_body: str | None = None,
) -> GewpMessage | None:
    """Extract GEWP payload from email.  Returns None → treat as human.intent.

    Priority:
      1. attachment_json  (Layer 1 — application/vnd.gewp+json content)
      2. html_body comment (Layer 2 — <!-- GEWP:{base64url} --> plaintext)
      3. html_body PGP comment (Layer 2 encrypted — <!-- GEWP-PGP:{base64url} -->)

    For PGP-encrypted emails (case 3), returns a sentinel GewpMessage with
    type="pgp.encrypted" so the caller knows decryption is required.
    """
    if attachment_json:
        try:
            data = json.loads(attachment_json)
            # PGP-encrypted envelope: {"gewp":"1.0","encrypted":"pgp","ciphertext":"..."}
            if data.get("encrypted") == "pgp":
                return _pgp_encrypted_sentinel(data.get("ciphertext", ""))
            return _from_dict(data)
        except Exception:
            pass

    if html_body:
        m = _GEWP_COMMENT_RE.search(html_body)
        if m:
            try:
                padded = m.group(1) + "==="
                decoded = base64.urlsafe_b64decode(padded[:len(padded) - len(padded) % 4]).decode()
                return _from_dict(json.loads(decoded))
            except Exception:
                pass

        m2 = _GEWP_PGP_COMMENT_RE.search(html_body)
        if m2:
            try:
                padded = m2.group(1) + "==="
                ciphertext = base64.urlsafe_b64decode(
                    padded[: len(padded) - len(padded) % 4]
                ).decode()
                return _pgp_encrypted_sentinel(ciphertext)
            except Exception:
                pass

    return None


def _pgp_encrypted_sentinel(ciphertext: str) -> GewpMessage:
    """Sentinel GewpMessage indicating PGP-encrypted content awaiting decryption."""
    return GewpMessage(
        gewp=GEWP_VERSION,
        type="pgp.encrypted",
        performative="inform",
        thread=GewpThread(id="", step=0),
        sender=GewpActor(id=""),
        to=[],
        payload={"ciphertext": ciphertext},
    )


def _from_dict(data: dict[str, Any]) -> GewpMessage:
    t = data.get("thread", {})
    b = t.get("barrier") or {}
    thread = GewpThread(
        id=t.get("id", ""),
        step=int(t.get("step", 0)),
        root_message_id=t.get("root_message_id", ""),
        graph=t.get("graph", ""),
        run_id=t.get("run_id", ""),
        barrier_total=int(b.get("total_vertices", 0)),
        barrier_timeout_s=int(b.get("timeout_seconds", 300)),
    )
    s = data.get("sender", {})
    sender = GewpActor(
        id=s.get("id", ""),
        type=s.get("@type", "Service"),
        email=s.get("email", ""),
        did=s.get("did", ""),
        handle=s.get("handle", ""),
        model=s.get("model", ""),
    )
    return GewpMessage(
        gewp=data.get("gewp", GEWP_VERSION),
        type=data.get("type", "pregel.message"),
        performative=data.get("performative", "inform"),
        extensions=data.get("extensions") or [],
        thread=thread,
        sender=sender,
        to=[_recipient_from_dict(r) for r in (data.get("to") or [])],
        cc=[_recipient_from_dict(r) for r in (data.get("cc") or [])],
        payload=data.get("payload") or {},
        state=data.get("state"),
        auth=data.get("auth"),
    )


def _recipient_from_dict(d: dict[str, Any]) -> GewpRecipient:
    return GewpRecipient(
        role=d.get("role", "vertex"),
        email=d.get("email", ""),
        id=d.get("id", ""),
        type=d.get("@type", "Service"),
        did=d.get("did", ""),
        node=d.get("node", ""),
    )
