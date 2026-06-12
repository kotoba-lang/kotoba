"""NIST CSF fallback app handlers for BPMN + Zeebe."""

from __future__ import annotations

from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _event(kind: str, payload: dict[str, Any]) -> str:
    event_id = _id(kind)
    created_at = now_iso()
    rec = {**payload, "eventId": event_id, "createdAt": created_at}
    client = get_kotoba_client()
    client.insert_row(
        "vertex_nist_event",
        {
            "vertex_id": f"nist:event:{event_id}",
            "owner_did": OWNER_DID,
            "event_id": event_id,
            "event_kind": kind,
            "event_json": json.dumps(rec, ensure_ascii=False, sort_keys=True),
            "created_at": created_at,
        },
    )
    return event_id


def health(**_: Any) -> dict[str, Any]:
    return {"status": "healthy", "app": "NIST CSF", "nanoid": NANOID, "did": OWNER_DID, "now": now_iso()}


def describe(**_: Any) -> dict[str, Any]:
    return {
        "name": "NIST CSF Intelligence",
        "did": OWNER_DID,
        "nanoid": NANOID,
        "capabilities": ["health", "describe", "wave", "csf-assessment", "cross-framework-mapping"],
        "protocols": ["xrpc", "w-protocol", "mcp", "bpmn"],
    }


def wave(message: Any = None, **_: Any) -> dict[str, Any]:
    text = _s(message, "hello")
    event_id = _event("wave", {"message": text, "postText": f"NIST CSF: {text}"})
    return {"ok": True, "nanoid": NANOID, "eventId": event_id}
