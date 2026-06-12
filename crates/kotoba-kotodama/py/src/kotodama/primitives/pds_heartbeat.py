"""PDS heartbeat cron primitives for BPMN/LangServer."""

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
HEARTBEAT_COLLECTION = "com.etzhayyim.apps.pds.heartbeatCron"
DEFAULT_TIMEOUT_SEC = 90.0


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _http_post_json(url: str, payload: dict[str, Any], secret: str = "") -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "kotodama-pds-heartbeat/1",
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


def call_pds_heartbeat(pds_url: str, secret: str) -> dict[str, Any]:
    url = pds_url.rstrip("/") + "/_internal/run-heartbeat-cron"
    result = _http_post_json(url, {}, secret)
    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    http_status = int(result.get("httpStatus") or 0)
    ok = bool(body.get("ok")) and http_status > 0 and http_status < 400
    return {
        "ok": ok,
        "httpStatus": http_status,
        "appsTotal": int(body.get("appsTotal") or 0),
        "batchIndex": int(body.get("batchIndex") or 0),
        "batchSize": int(body.get("batchSize") or 0),
        "heartbeatOk": int(body.get("heartbeatOk") or 0),
        "heartbeatFail": int(body.get("heartbeatFail") or 0),
        "shinkaStatus": int(body.get("shinkaStatus") or 0),
        "error": "" if ok else str(body.get("error") or f"http {http_status}")[:500],
    }


def write_heartbeat_tick(tick: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    ts = str(tick.get("ts") or _utc_now_iso())
    rkey = "heartbeat-cron-" + ts.replace("-", "").replace(":", "").replace(".", "")
    rkey = rkey.replace("T", "").replace("Z", "")
    uri = f"at://{PDS_DID}/{HEARTBEAT_COLLECTION}/{rkey}"
    value = {
        "$type": HEARTBEAT_COLLECTION,
        "v": 1,
        **tick,
    }
    row = {
        "vertex_id": uri,
        "tick_id": rkey,
        "operation_kind": "heartbeatCron",
        "ok": bool(tick.get("ok")),
        "http_status": int(tick.get("httpStatus") or 0),
        "metric_primary": int(tick.get("appsTotal") or 0),
        "metric_secondary": int(tick.get("heartbeatOk") or 0),
        "error": str(tick.get("error") or "")[:4096],
        "value_json": json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        "observed_at": ts,
        "created_at": ts,
        "owner_did": PDS_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row("vertex_pds_operation_tick", row)
    return {"uri": uri, "rkey": rkey}


def task_pds_heartbeat_run(
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
            "appsTotal": 0,
            "batchIndex": 0,
            "batchSize": 0,
            "heartbeatOk": 0,
            "heartbeatFail": 0,
            "shinkaStatus": 0,
            "error": "PDS_SERVICE_AUTH_MINT_SECRET is required",
        }
    else:
        started = time.monotonic()
        result = call_pds_heartbeat(url, secret)
        tick = {
            "ts": ts,
            **result,
            "latencyMs": int((time.monotonic() - started) * 1000),
        }
    audit = write_heartbeat_tick(tick, flush=flush)
    return {
        "ok": tick["ok"],
        "httpStatus": tick["httpStatus"],
        "appsTotal": tick["appsTotal"],
        "batchIndex": tick["batchIndex"],
        "batchSize": tick["batchSize"],
        "heartbeatOk": tick["heartbeatOk"],
        "heartbeatFail": tick["heartbeatFail"],
        "shinkaStatus": tick["shinkaStatus"],
        "error": tick.get("error", ""),
        "auditUri": audit["uri"],
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="pds.heartbeat.run",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_pds_heartbeat_run)
