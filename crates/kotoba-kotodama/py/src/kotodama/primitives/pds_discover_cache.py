"""PDS DiscoverFeed cache warm primitives for BPMN/LangServer."""

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
DISCOVER_CACHE_COLLECTION = "com.etzhayyim.apps.pds.discoverCacheWarm"
DEFAULT_TIMEOUT_SEC = 45.0


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _http_post_json(url: str, payload: dict[str, Any], secret: str = "") -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "kotodama-pds-discover-cache/1",
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


def call_pds_discover_cache_warm(pds_url: str, secret: str) -> dict[str, Any]:
    url = pds_url.rstrip("/") + "/_internal/warm-discover-cache"
    result = _http_post_json(url, {}, secret)
    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    http_status = int(result.get("httpStatus") or 0)
    ok = bool(body.get("ok")) and http_status > 0 and http_status < 400
    return {
        "ok": ok,
        "httpStatus": http_status,
        "rowCount": int(body.get("rowCount") or 0),
        "cacheWritten": bool(body.get("cacheWritten")),
        "error": "" if ok else str(body.get("error") or f"http {http_status}")[:500],
    }


def write_discover_cache_tick(tick: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    ts = str(tick.get("ts") or _utc_now_iso())
    rkey = "discover-cache-warm-" + ts.replace("-", "").replace(":", "").replace(".", "")
    rkey = rkey.replace("T", "").replace("Z", "")
    uri = f"at://{PDS_DID}/{DISCOVER_CACHE_COLLECTION}/{rkey}"
    value = {"$type": DISCOVER_CACHE_COLLECTION, "v": 1, **tick}
    row = {
        "vertex_id": uri,
        "tick_id": rkey,
        "operation_kind": "discoverCacheWarm",
        "ok": bool(tick.get("ok")),
        "http_status": int(tick.get("httpStatus") or 0),
        "metric_primary": int(tick.get("rowCount") or 0),
        "metric_secondary": 1 if tick.get("cacheWritten") else 0,
        "error": str(tick.get("error") or "")[:4096],
        "value_json": json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        "observed_at": ts,
        "created_at": ts,
        "owner_did": PDS_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row("vertex_pds_operation_tick", row)
    return {"uri": uri, "rkey": rkey}


def task_pds_discover_cache_warm(
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
            "rowCount": 0,
            "cacheWritten": False,
            "error": "PDS_SERVICE_AUTH_MINT_SECRET is required",
        }
    else:
        started = time.monotonic()
        result = call_pds_discover_cache_warm(url, secret)
        tick = {"ts": ts, **result, "latencyMs": int((time.monotonic() - started) * 1000)}
    audit = write_discover_cache_tick(tick, flush=flush)
    return {
        "ok": tick["ok"],
        "httpStatus": tick["httpStatus"],
        "rowCount": tick["rowCount"],
        "cacheWritten": tick["cacheWritten"],
        "error": tick.get("error", ""),
        "auditUri": audit["uri"],
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="pds.discoverCache.warm",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_pds_discover_cache_warm)
