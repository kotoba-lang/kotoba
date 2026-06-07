"""Kotodama organizer primitives for BPMN/LangServer.

The Cloudflare Worker still owns the organizer implementation because it has
the R2 and Hyperdrive bindings used by the dashboard. This module moves the
timer and retry lifecycle to Zeebe and records each run as graph-visible audit
data.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


KOTODAMA_DID = "did:web:kotoba-kotodama.etzhayyim.com"
ORGANIZER_RUN_COLLECTION = "com.etzhayyim.apps.kotoba-kotodama.organizerRun"
DEFAULT_TIMEOUT_SEC = 60.0


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_post_json(url: str, payload: dict[str, Any], bearer: str = "") -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "kotodama-organizer/1",
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
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
        return {"httpStatus": e.code, "body": {"error": raw or e.reason}}
    except Exception as e:  # noqa: BLE001
        return {"httpStatus": 0, "body": {"error": f"transport: {e}"}}


def call_organizer(organizer_url: str, bearer: str = "") -> dict[str, Any]:
    result = _http_post_json(organizer_url.rstrip("/"), {}, bearer)
    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    http_status = int(result.get("httpStatus") or 0)
    summary = body.get("summary") if isinstance(body.get("summary"), dict) else {}
    fleet = body.get("fleet") if isinstance(body.get("fleet"), dict) else {}
    ok = http_status > 0 and http_status < 400 and "error" not in body
    return {
        "ok": ok,
        "httpStatus": http_status,
        "runsTotal24h": int(body.get("runsTotal24h") or 0),
        "summary": {
            "hot": int(summary.get("hot") or 0),
            "normal": int(summary.get("normal") or 0),
            "stale": int(summary.get("stale") or 0),
            "silent": int(summary.get("silent") or 0),
            "archived": int(summary.get("archived") or 0),
        },
        "fleetSaturation": float(fleet.get("saturation") or 0.0),
        "planTs": str(body.get("ts") or ""),
        "error": "" if ok else str(body.get("error") or f"http {http_status}")[:500],
    }


def write_organizer_run(tick: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    ts = str(tick.get("ts") or _utc_now_iso())
    rkey = "organizer-run-" + ts.replace("-", "").replace(":", "").replace(".", "")
    rkey = rkey.replace("T", "").replace("Z", "")
    uri = f"at://{KOTODAMA_DID}/{ORGANIZER_RUN_COLLECTION}/{rkey}"
    value = {
        "$type": ORGANIZER_RUN_COLLECTION,
        "v": 1,
        **tick,
    }
    row = {
        "vertex_id": uri,
        "record_key": rkey,
        "status": "ok" if value.get("ok") else "error",
        "value_json": json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        "indexed_at": ts,
        "created_at": ts,
        "updated_at": ts,
        "actor_did": KOTODAMA_DID,
        "org_did": "anon",
        "owner_did": KOTODAMA_DID,
        "sensitivity_ord": 2,
        "http_status": int(value.get("httpStatus") or 0),
        "runs_total_24h": int(value.get("runsTotal24h") or 0),
        "summary_hot": int((value.get("summary") or {}).get("hot") or 0),
        "summary_normal": int((value.get("summary") or {}).get("normal") or 0),
        "summary_stale": int((value.get("summary") or {}).get("stale") or 0),
        "summary_silent": int((value.get("summary") or {}).get("silent") or 0),
        "summary_archived": int((value.get("summary") or {}).get("archived") or 0),
        "fleet_saturation": float(value.get("fleetSaturation") or 0.0),
        "plan_ts": str(value.get("planTs") or ""),
        "latency_ms": int(value.get("latencyMs") or 0),
        "error": str(value.get("error") or "")[:500],
    }
    get_kotoba_client().insert_row("vertex_kotoba-kotodama_organizer_run", row)


def task_kotoba-kotodama_organizer_run(
    organizerUrl: str = "",
    flush: bool = True,
) -> dict[str, Any]:
    url = organizerUrl or os.environ.get("KOTODAMA_ORGANIZER_URL") or ""
    ts = _utc_now_iso()
    if not url:
        tick = {
            "ts": ts,
            "ok": False,
            "httpStatus": 0,
            "runsTotal24h": 0,
            "summary": {"hot": 0, "normal": 0, "stale": 0, "silent": 0, "archived": 0},
            "fleetSaturation": 0.0,
            "error": "KOTODAMA_ORGANIZER_URL is required",
        }
    else:
        bearer = os.environ.get("KOTODAMA_ORGANIZER_BEARER") or ""
        started = time.monotonic()
        result = call_organizer(url, bearer)
        tick = {
            "ts": ts,
            **result,
            "latencyMs": int((time.monotonic() - started) * 1000),
        }
    audit = write_organizer_run(tick, flush=flush)
    return {
        "ok": tick["ok"],
        "httpStatus": tick["httpStatus"],
        "runsTotal24h": tick["runsTotal24h"],
        "summary": tick["summary"],
        "fleetSaturation": tick["fleetSaturation"],
        "error": tick.get("error", ""),
        "auditUri": audit["uri"],
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="kotoba-kotodama.organizer.run",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_kotoba-kotodama_organizer_run)
