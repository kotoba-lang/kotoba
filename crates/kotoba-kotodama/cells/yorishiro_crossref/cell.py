"""
Yorishiro: crossref (kami: api.crossref.org)
Generator: @etzhayyim/yorishiro v0.1.0
Per ADR-2605211900 (yorishiro external-actor bridge) + ADR-2605202200
(kotoba-kotodama cell.py runtime contract).

Transport: openapi-v3
Base URL : https://api.crossref.org
Charter purposes: grant

This file is generator output. Hand edits will be overwritten by
`yorishiro regen crossref` — extend the kami OpenAPI spec instead.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, TypedDict
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


YORISHIRO_NAME = "crossref"
YORISHIRO_KAMI = "api.crossref.org"
YORISHIRO_BASE_URL = "https://api.crossref.org"
YORISHIRO_PURPOSES = tuple(["grant"])
USER_AGENT = f"etzhayyim-yorishiro-{YORISHIRO_NAME}/0.1"


class CrossrefState(TypedDict, total=False):
    # routing
    op: str

    # arbitrary kami input (one set of keys per op — kept loose because
    # OpenAPI parameter shape varies. Validation belongs to the L1
    # lexicon + parseLexiconInput at the XRPC/MCP seam).
    params: dict[str, Any]
    body: dict[str, Any]

    # kami output
    http_status: int
    json: dict[str, Any]
    body_raw: str
    error: str


def _http_call(method: str, url: str, params: dict[str, Any], body: dict[str, Any] | None) -> tuple[int, str]:
    filtered = {k: v for k, v in params.items() if v is not None and v != ""}
    qs = urlencode(filtered, doseq=True)
    full_url = f"{url}?{qs}" if qs else url
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(full_url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 — kami failures surface to state.error
        return 0, str(exc)


def _attempt_json(text: str) -> dict[str, Any] | None:
    try:
        out = json.loads(text)
        if isinstance(out, dict):
            return out
        return {"value": out}
    except (json.JSONDecodeError, ValueError):
        return None


def search_works_node(state: dict[str, Any]) -> dict[str, Any]:
    """Free-text + structured query over the Crossref works index."""
    params = dict(state.get("params") or {})
    body = state.get("body") or None
    path = "/works"
    for key in list(params.keys()):
        token = "{" + key + "}"
        if token in path:
            path = path.replace(token, str(params.pop(key)))
    url = f"{YORISHIRO_BASE_URL}{path}"
    status, text = _http_call("GET", url, params, body if isinstance(body, dict) and body else None)
    out: dict[str, Any] = {**state, "http_status": status}
    if status == 0:
        out["error"] = text
        return out
    if status >= 400:
        out["error"] = text[:1000]
        out["body_raw"] = text
        return out
    if "application/json" == "application/json":
        parsed = _attempt_json(text)
        if parsed is not None:
            out["json"] = parsed
            return out
    out["body_raw"] = text
    return out

def get_work_by_doi_node(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch a single work record by its DOI."""
    params = dict(state.get("params") or {})
    body = state.get("body") or None
    path = "/works/{doi}"
    for key in list(params.keys()):
        token = "{" + key + "}"
        if token in path:
            path = path.replace(token, str(params.pop(key)))
    url = f"{YORISHIRO_BASE_URL}{path}"
    status, text = _http_call("GET", url, params, body if isinstance(body, dict) and body else None)
    out: dict[str, Any] = {**state, "http_status": status}
    if status == 0:
        out["error"] = text
        return out
    if status >= 400:
        out["error"] = text[:1000]
        out["body_raw"] = text
        return out
    if "application/json" == "application/json":
        parsed = _attempt_json(text)
        if parsed is not None:
            out["json"] = parsed
            return out
    out["body_raw"] = text
    return out


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(CrossrefState)
    g.add_node("searchWorks", search_works_node)
    g.add_node("getWorkByDoi", get_work_by_doi_node)

    def _router(state: CrossrefState) -> str:
        op = state.get("op") or "searchWorks"
        return op if op in {"searchWorks", "getWorkByDoi"} else "searchWorks"

    g.add_conditional_edges(START, _router, {
        "searchWorks": "searchWorks",
        "getWorkByDoi": "getWorkByDoi",
    })
    g.add_edge("searchWorks", END)
    g.add_edge("getWorkByDoi", END)

    return g.compile(checkpointer=checkpointer)


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ───────────────────────────


def state_from_event(event: dict[str, Any]) -> CrossrefState:
    """Map an MST / XRPC event payload into the cell's TypedDict state."""
    return {
        "op": event.get("op", "searchWorks"),
        "params": event.get("params", {}) or {},
        "body": event.get("body", {}) or {},
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    """Deterministic thread id so duplicate events deduplicate at the checkpointer."""
    key = json.dumps(
        {
            "op": event.get("op"),
            "params": event.get("params"),
            "body": event.get("body"),
        },
        sort_keys=True,
        default=str,
    )
    return f"yorishiro-{YORISHIRO_NAME}-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "yorishiro": YORISHIRO_NAME,
        "kami": YORISHIRO_KAMI,
        "purposes": list(YORISHIRO_PURPOSES),
        "ops": ["searchWorks","getWorkByDoi"],
    }


__all__ = [
    "CrossrefState",
    "build_graph",
    "state_from_event",
    "thread_id_from_event",
    "healthz",
    "search_works_node",
    "get_work_by_doi_node",
]
