"""PDS write-outbox primitives for BPMN/LangServer."""

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
OUTBOX_SYNC_COLLECTION = "com.etzhayyim.apps.pds.writeOutboxSync"
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
        "User-Agent": "kotodama-pds-outbox/1",
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


def call_pds_outbox_sync(pds_url: str, secret: str) -> dict[str, Any]:
    url = pds_url.rstrip("/") + "/_internal/sync-write-outbox"
    result = _http_post_json(url, {}, secret)
    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    http_status = int(result.get("httpStatus") or 0)
    ok = bool(body.get("ok")) and http_status > 0 and http_status < 400
    return {
        "ok": ok,
        "httpStatus": http_status,
        "replayed": int(body.get("replayed") or 0),
        "retried": int(body.get("retried") or 0),
        "expired": int(body.get("expired") or 0),
        "error": "" if ok else str(body.get("error") or f"http {http_status}")[:500],
    }


def write_outbox_sync_tick(tick: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    ts = str(tick.get("ts") or _utc_now_iso())
    rkey = "write-outbox-sync-" + ts.replace("-", "").replace(":", "").replace(".", "")
    rkey = rkey.replace("T", "").replace("Z", "")
    uri = f"at://{PDS_DID}/{OUTBOX_SYNC_COLLECTION}/{rkey}"
    value = {
        "$type": OUTBOX_SYNC_COLLECTION,
        "v": 1,
        **tick,
    }
    row = {
        "vertex_id": uri,
        "tick_id": rkey,
        "operation_kind": "writeOutboxSync",
        "ok": bool(tick.get("ok")),
        "http_status": int(tick.get("httpStatus") or 0),
        "metric_primary": int(tick.get("replayed") or 0),
        "metric_secondary": int(tick.get("retried") or 0),
        "error": str(tick.get("error") or "")[:4096],
        "value_json": json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        "observed_at": ts,
        "created_at": ts,
        "owner_did": PDS_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row("vertex_pds_operation_tick", row)
    return {"uri": uri, "rkey": rkey}


def task_pds_write_outbox_sync(
    pdsUrl: str = "",
    flush: bool = True,
) -> dict[str, Any]:
    url = pdsUrl or os.environ.get("PDS_URL") or "https://atproto.etzhayyim.com"
    secret = os.environ.get("PDS_SERVICE_AUTH_MINT_SECRET") or os.environ.get("PDS_INTERNAL_HMAC_SECRET") or ""
    ts = _utc_now_iso()
    if not secret:
        tick = {
            "ts": ts,
            "ok": False,
            "httpStatus": 0,
            "replayed": 0,
            "retried": 0,
            "expired": 0,
            "error": "PDS_SERVICE_AUTH_MINT_SECRET is required",
        }
    else:
        started = time.monotonic()
        result = call_pds_outbox_sync(url, secret)
        tick = {
            "ts": ts,
            **result,
            "latencyMs": int((time.monotonic() - started) * 1000),
        }
    audit = write_outbox_sync_tick(tick, flush=flush)
    return {
        "ok": tick["ok"],
        "httpStatus": tick["httpStatus"],
        "replayed": tick["replayed"],
        "retried": tick["retried"],
        "expired": tick["expired"],
        "error": tick.get("error", ""),
        "auditUri": audit["uri"],
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="pds.writeOutbox.sync",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_pds_write_outbox_sync)
