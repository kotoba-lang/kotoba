"""PDS signing key rotation primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


PDS_DID = "did:web:atproto.etzhayyim.com"
KEY_ROTATION_COLLECTION = "com.etzhayyim.apps.pds.keyRotation"
DEFAULT_TIMEOUT_SEC = 60.0


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _http_post_json(url: str, payload: dict[str, Any], secret: str = "") -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "kotodama-pds-key-rotation/1",
    }
    if secret:
        headers["x-bpmn-auth"] = _sign_body(secret, body)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw or "{}")
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            return {"httpStatus": resp.status, "body": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")[:500]
        return {"httpStatus": e.code, "body": {"ok": False, "error": raw or e.reason}}
    except Exception as e:  # noqa: BLE001
        return {"httpStatus": 0, "body": {"ok": False, "error": f"transport: {e}"}}


def call_pds_key_rotation(pds_url: str, secret: str, max_age_days: int, batch_size: int) -> dict[str, Any]:
    url = pds_url.rstrip("/") + "/_internal/rotate-signing-keys"
    result = _http_post_json(url, {"maxAgeDays": max_age_days, "batchSize": batch_size}, secret)
    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    http_status = int(result.get("httpStatus") or 0)
    errors = body.get("errors") if isinstance(body.get("errors"), list) else []
    ok = bool(body.get("ok")) and http_status > 0 and http_status < 400
    return {
        "ok": ok,
        "httpStatus": http_status,
        "scanned": int(body.get("scanned") or 0),
        "rotated": int(body.get("rotated") or 0),
        "errorCount": len(errors),
        "errors": errors[:5],
        "error": "" if ok else str(body.get("error") or f"http {http_status}")[:500],
    }


def write_key_rotation_tick(tick: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    ts = str(tick.get("ts") or _utc_now_iso())
    rkey = "key-rotation-" + ts.replace("-", "").replace(":", "").replace(".", "")
    rkey = rkey.replace("T", "").replace("Z", "")
    uri = f"at://{PDS_DID}/{KEY_ROTATION_COLLECTION}/{rkey}"
    value = {
        "$type": KEY_ROTATION_COLLECTION,
        "v": 1,
        **tick,
    }
    row = {
        "vertex_id": uri,
        "tick_id": rkey,
        "operation_kind": "keyRotation",
        "ok": bool(tick.get("ok")),
        "http_status": int(tick.get("httpStatus") or 0),
        "metric_primary": int(tick.get("scanned") or 0),
        "metric_secondary": int(tick.get("rotated") or 0),
        "error": str(tick.get("error") or "")[:4096],
        "value_json": json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        "observed_at": ts,
        "created_at": ts,
        "owner_did": PDS_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row("vertex_pds_operation_tick", row)
    return {"uri": uri, "rkey": rkey}


def task_pds_signing_keys_rotate_stale(
    pdsUrl: str = "",
    maxAgeDays: int = 90,
    batchSize: int = 5,
    flush: bool = True,
) -> dict[str, Any]:
    url = pdsUrl or os.environ.get("PDS_URL") or "https://atproto.etzhayyim.com"
    secret = os.environ.get("PDS_SERVICE_AUTH_MINT_SECRET") or os.environ.get("PDS_INTERNAL_HMAC_SECRET") or ""
    max_age_days = max(1, min(int(maxAgeDays or 90), 3650))
    batch_size = max(1, min(int(batchSize or 5), 50))
    ts = _utc_now_iso()
    if not secret:
        tick = {
            "ts": ts,
            "ok": False,
            "httpStatus": 0,
            "scanned": 0,
            "rotated": 0,
            "errorCount": 0,
            "errors": [],
            "error": "PDS_SERVICE_AUTH_MINT_SECRET is required",
        }
    else:
        started = time.monotonic()
        result = call_pds_key_rotation(url, secret, max_age_days, batch_size)
        tick = {
            "ts": ts,
            "maxAgeDays": max_age_days,
            "batchSize": batch_size,
            **result,
            "latencyMs": int((time.monotonic() - started) * 1000),
        }
    audit = write_key_rotation_tick(tick, flush=flush)
    return {
        "ok": tick["ok"],
        "httpStatus": tick["httpStatus"],
        "scanned": tick["scanned"],
        "rotated": tick["rotated"],
        "errorCount": tick["errorCount"],
        "error": tick.get("error", ""),
        "auditUri": audit["uri"],
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="pds.signingKeys.rotateStale",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_pds_signing_keys_rotate_stale)
