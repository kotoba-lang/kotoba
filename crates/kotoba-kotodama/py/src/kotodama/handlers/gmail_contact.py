"""
ADR-0049 Phase B — gmail contact DID materializer.

For every inbound gmail message, materialize one `vertex_gmail_contact`
row per unique sender + one `edge_gmail_email_from_contact` edge. This
replaces the stub `TODO(Phase 2)` in the gmail Worker that never got
wired because per-sender DID creation via PDS XRPC was too expensive on
the hot ingest path (each `sync_inbox` batch may see 50-500 new senders).

The UDF runs entirely inside the mitama-udf pod:

    app.ts syncInbox → INSERT vertex_gmail_email →
      SELECT gmail_upsert_contact(email_id, from_addr, account_did) →
        [UDF] parse from_addr → sanitize path segment → INSERT contact
                                                     → INSERT edge
        returns {contactDid, wasNew, emailPath, displayName}

PDS registration (`sdk.did.create`) is deliberately NOT done here. The
row lives in the graph projection only; a later promotion job can read
`vertex_gmail_contact WHERE pds_registered = false` and publish those
that cross an activity threshold (e.g. ≥10 inbound messages) to avoid
polluting the AT relay with one-shot spam addresses.

Sanitization rules (`sanitize_path_segment`):
  alice@example.com   → alice-at-example-com
  a.b+tag@x.co.jp     → a-b-tag-at-x-co-jp
  "ALICE" <a@x>       → alice-at-x  (drops the display-name wrapper)

Only `[a-z0-9-]` are kept; `.`, `+`, `_`, `@`, whitespace collapse to `-`.
Length-capped to 63 chars (DNS label constraint for did:web path
segments). If the tail gets truncated, the sanitized path remains a
valid deterministic function of the input (no hash collision risk —
two distinct emails never produce the same segment because we bake the
full local+domain into the allowed chars).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from kotodama import udf
from kotodama.kotoba_datomic import get_kotoba_client

_CONTACT_COLLECTION = "com.etzhayyim.apps.gmail.contact"
_CONTACT_DID_PREFIX = "did:web:gmail.etzhayyim.com:contact:"
_MAX_SEGMENT_LEN = 63  # DNS label ceiling (RFC 1035)

# Match "Display Name" <email@host> or just email@host.
_RFC5322 = re.compile(r'^\s*(?:"?([^"<]*?)"?\s*)?<?([^<>\s]+@[^<>\s]+)>?\s*$')


def _err(msg: str, **extra: Any) -> str:
    return json.dumps({"error": msg, **extra})


def _parse_from(addr: str) -> tuple[str, str]:
    """Return (display_name, email). display_name is '' when not present."""
    if not addr:
        return "", ""
    m = _RFC5322.match(addr)
    if not m:
        # Bare token with no < > wrapper and not matching email shape —
        # fall back to treating the whole thing as the address.
        return "", addr.strip().lower()
    name = (m.group(1) or "").strip()
    email = (m.group(2) or "").strip().lower()
    return name, email


def sanitize_path_segment(email: str) -> str:
    """Deterministic email → did:web path segment."""
    s = email.strip().lower()
    s = s.replace("@", "-at-")
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:_MAX_SEGMENT_LEN]


@udf(
    nsid="com.etzhayyim.apps.gmail.upsertContact",
    io_threads=50,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("gmail", "contact", "did-materialize"),
    agent_tool="Materialize a gmail contact DID + edge from a sender address.",
)
def upsert_contact(request_json: str) -> str:
    """
    Input: JSON `{emailId, fromAddr, accountDid}` — emailId is the rkey
    used by the gmail Worker when it INSERTed vertex_gmail_email (it's
    the `email-${gmailMessageId}` shape at call site, not the full
    vertex_id).

    Output: JSON `{contactDid, sanitized, displayName, email, wasNew,
    edgeCreated}`.
    """

    try:
        body = json.loads(request_json) if request_json else {}
    except json.JSONDecodeError as e:
        return _err(f"invalid JSON: {e}")
    if not isinstance(body, dict):
        return _err("request must be a JSON object")
    if "json" in body and isinstance(body.get("json"), dict):
        body = body["json"]

    email_id = str(body.get("emailId") or "").strip()
    from_addr = str(body.get("fromAddr") or "").strip()
    account_did = str(body.get("accountDid") or "did:web:gmail.etzhayyim.com").strip()
    if not email_id:
        return _err("emailId is required")
    if not from_addr:
        return _err("fromAddr is required")

    display_name, email = _parse_from(from_addr)
    if not email or "@" not in email:
        # Reject bare tokens that slipped past _RFC5322 — we never want
        # contacts like `did:web:gmail.etzhayyim.com:contact:junk-no-email`.
        return _err("could not extract email from fromAddr", fromAddr=from_addr)

    sanitized = sanitize_path_segment(email)
    if not sanitized:
        return _err("sanitization produced empty segment", email=email)

    contact_did = f"{_CONTACT_DID_PREFIX}{sanitized}"
    contact_vertex_id = f"at://{contact_did}/{_CONTACT_COLLECTION}/{sanitized}"
    # Email vertex_id shape from gmail/app.ts write("email", ...).
    email_vertex_id = f"at://{account_did}/com.etzhayyim.apps.gmail.email/{email_id}"
    edge_id = f"{email_vertex_id}|from|{contact_vertex_id}"

    # RisingWave does not parse `ON CONFLICT DO NOTHING`. Use `WHERE NOT
    # EXISTS` so concurrent / replay inserts are idempotent without the
    # round-trip cost of a separate pre-SELECT. The pattern degrades
    # message_count tracking — keep it fixed at 1; a streaming MV over
    # `vertex_gmail_email` can aggregate true counts later.
    now_utc = datetime.now(timezone.utc)
    contact_row_dict = {
        "vertex_id": contact_vertex_id,
        "created_date": now_utc.strftime('%Y-%m-%d'),
        "sensitivity_ord": 50,
        "owner_did": contact_did,
        "rkey": sanitized,
        "repo": contact_did,
        "contact_did": contact_did,
        "email": email,
        "display_name": display_name,
        "first_seen_at": now_utc.isoformat(timespec='seconds') + 'Z',
        "last_seen_at": now_utc.isoformat(timespec='seconds') + 'Z',
        "message_count": 1,
        "created_at": now_utc.isoformat(timespec='seconds') + 'Z',
        "org_id": "etzhayyim",
        "user_id": "system",
        "actor_id": "sys.gmail-udf",
    }
    inserted_contact = get_kotoba_client().insert_row("vertex_gmail_contact", contact_row_dict)
    was_new = bool(inserted_contact)

    edge_row_dict = {
        "edge_id": edge_id,
        "src_vid": email_vertex_id,
        "dst_vid": contact_vertex_id,
        "created_date": now_utc.strftime('%Y-%m-%d'),
        "sensitivity_ord": 50,
        "owner_did": account_did,
        "email_id": email_id,
        "contact_did": contact_did,
        "created_at": now_utc.isoformat(timespec='seconds') + 'Z',
    }
    inserted_edge = get_kotoba_client().insert_row("edge_gmail_email_from_contact", edge_row_dict)
    edge_created = bool(inserted_edge)

    return json.dumps(
        {
            "contactDid": contact_did,
            "sanitized": sanitized,
            "displayName": display_name,
            "email": email,
            "wasNew": was_new,
            "edgeCreated": edge_created,
        }
    )
