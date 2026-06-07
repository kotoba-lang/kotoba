"""
copyright.ingest — LangGraph StateGraph (ADR-2605080600 Phase 5).

Replaces the Zeebe BPMN processes copyright_crossref_ingest + copyright_datacite_ingest
(previously triggered via kubectl exec CronJob d091d660).

Triggered by K8s CronJob via POST /runs to LangGraph Server.

Graph:
  START → fetch_crossref → insert_crossref
        → fetch_datacite → insert_datacite
        → emit_audit → END

State:
  crossrefRows   int   vertex_work rows upserted from Crossref (output)
  dataciteRows   int   vertex_work rows upserted from DataCite (output)
  crossrefError  str   error from crossref fetch/insert, or None (output)
  dataciteError  str   error from datacite fetch/insert, or None (output)
  ok             bool  overall success flag (output)

Kotoba Datom log persistence:
  - vertex_work — PK overwrite dedup (same DOI safe to re-ingest)
  - Checkpoint via kotoba checkpoint saver (thread_id = actor DID)
  - Long-term state via kotoba store namespace ("did:web:copyright.etzhayyim.com","ingest_state")
"""

from __future__ import annotations

import time as _time
from typing import Any, TypedDict

import httpx

from kotodama.kotoba_datomic import get_kotoba_client

_CROSSREF_URL = (
    "https://api.crossref.org/works"
    "?rows=100&sort=indexed&order=desc"
    "&filter=from-pub-date%3A2020"
    "&mailto=jun%40etzhayyim.com"
)
_CROSSREF_HEADERS = {
    "User-Agent": "etzhayyim-copyright/2.0 (mailto:jun@etzhayyim.com)",
    "Accept": "application/json",
}
_DATACITE_URL = (
    "https://api.datacite.org/dois?page%5Bsize%5D=100&sort=created&direction=desc"
)
_COPYRIGHT_DID = "did:web:copyright.etzhayyim.com"
_TIMEOUT = 60.0


# ── State ──────────────────────────────────────────────────────────────────

class CopyrightIngestState(TypedDict, total=False):
    crossrefItems: list[dict]
    dataciteItems: list[dict]
    crossrefRows: int
    dataciteRows: int
    crossrefError: str | None
    dataciteError: str | None
    ok: bool
    error: str | None


# ── Helpers ────────────────────────────────────────────────────────────────

def _safe_title(item: dict) -> str:
    t = item.get("title")
    if isinstance(t, list) and t:
        return str(t[0])
    if isinstance(t, str) and t:
        return t
    return "(no title)"


def _doi_rkey(doi: str) -> str:
    return "doi-" + doi.replace("/", "-")


def _now_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _crossref_row(item: dict) -> dict | None:
    doi = item.get("DOI")
    if not doi:
        return None
    rkey = _doi_rkey(doi)
    kind = "dataset" if item.get("type") in ("dataset", "component") else "literary"
    return {
        "vertex_id": f"at://{_COPYRIGHT_DID}:crossref/com.etzhayyim.apps.copyright.work/{rkey}",
        "owner_did": f"{_COPYRIGHT_DID}:crossref",
        "rkey": rkey,
        "repo": f"{_COPYRIGHT_DID}:crossref",
        "did": f"{_COPYRIGHT_DID}:crossref",
        "status": "active",
        "kind": kind,
        "title": _safe_title(item),
        "doi": doi,
        "registry": "crossref",
        "berne_automatic": True,
        "source_url": f"https://doi.org/{doi}",
        "collected_at": _now_str(),
        "sensitivity_ord": 100,
    }


def _datacite_row(item: dict) -> dict | None:
    attrs = item.get("attributes") or {}
    doi = attrs.get("doi") or item.get("id")
    if not doi:
        return None
    rkey = _doi_rkey(doi)
    titles = attrs.get("titles") or []
    title = titles[0].get("title") if titles else "(no title)"
    return {
        "vertex_id": f"at://{_COPYRIGHT_DID}:datacite/com.etzhayyim.apps.copyright.work/{rkey}",
        "owner_did": f"{_COPYRIGHT_DID}:datacite",
        "rkey": rkey,
        "repo": f"{_COPYRIGHT_DID}:datacite",
        "did": f"{_COPYRIGHT_DID}:datacite",
        "status": "active",
        "kind": "dataset",
        "title": title or "(no title)",
        "doi": doi,
        "registry": "datacite",
        "berne_automatic": True,
        "source_url": f"https://doi.org/{doi}",
        "collected_at": _now_str(),
        "sensitivity_ord": 100,
    }





def _bulk_insert_vertex_work(rows: list[dict]) -> int:
    """Insert rows into vertex_work via kotoba_client.insert_rows."""
    if not rows:
        return 0
    try:
        get_kotoba_client().insert_rows("vertex_work", rows)
        return len(rows)
    except Exception:
        return 0


# ── Nodes ──────────────────────────────────────────────────────────────────

def fetch_crossref(state: CopyrightIngestState) -> dict:
    """HTTP GET Crossref API → extract items list into state."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(_CROSSREF_URL, headers=_CROSSREF_HEADERS)
            resp.raise_for_status()
            data = resp.json()
        items = (data.get("message") or {}).get("items") or []
        return {"crossrefItems": items}
    except Exception as e:
        return {"crossrefItems": [], "crossrefError": str(e)}


def insert_crossref(state: CopyrightIngestState) -> dict:
    """Transform Crossref items and bulk-insert into vertex_work."""
    items = state.get("crossrefItems") or []
    try:
        rows = [r for item in items if (r := _crossref_row(item)) is not None]
        n = _bulk_insert_vertex_work(rows)
        return {"crossrefRows": n}
    except Exception as e:
        return {"crossrefRows": 0, "crossrefError": str(e)}


def fetch_datacite(state: CopyrightIngestState) -> dict:
    """HTTP GET DataCite API → extract items list into state."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(_DATACITE_URL, headers={"Accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
        items = data.get("data") or []
        return {"dataciteItems": items}
    except Exception as e:
        return {"dataciteItems": [], "dataciteError": str(e)}


def insert_datacite(state: CopyrightIngestState) -> dict:
    """Transform DataCite items and bulk-insert into vertex_work."""
    items = state.get("dataciteItems") or []
    try:
        rows = [r for item in items if (r := _datacite_row(item)) is not None]
        n = _bulk_insert_vertex_work(rows)
        return {"dataciteRows": n, "ok": True}
    except Exception as e:
        return {"dataciteRows": 0, "dataciteError": str(e), "ok": False}


def emit_audit(state: CopyrightIngestState) -> dict:
    """Write typed run rows into vertex_copyright_ingest_run (non-fatal)."""
    crossref_rows = state.get("crossrefRows", 0)
    datacite_rows = state.get("dataciteRows", 0)
    crossref_error = state.get("crossrefError")
    datacite_error = state.get("dataciteError")
    ok = state.get("ok", True)
    now = _now_str()
    today = now[:10]
    ts_ms = int(_time.time() * 1000)
    try:
        rows = [
            {
                "vertex_id": f"at://{_COPYRIGHT_DID}/com.etzhayyim.apps.copyright.ingestRun/run-crossref-{ts_ms}",
                "owner_did": _COPYRIGHT_DID,
                "registry": "crossref",
                "started_at": now,
                "finished_at": now,
                "status": "done" if not crossref_error else "failed",
                "rows_fetched": len(state.get("crossrefItems") or []),
                "rows_inserted": crossref_rows,
                "error": crossref_error,
                "created_date": today,
                "sensitivity_ord": 100,
            },
            {
                "vertex_id": f"at://{_COPYRIGHT_DID}/com.etzhayyim.apps.copyright.ingestRun/run-datacite-{ts_ms}",
                "owner_did": _COPYRIGHT_DID,
                "registry": "datacite",
                "started_at": now,
                "finished_at": now,
                "status": "done" if not datacite_error else "failed",
                "rows_fetched": len(state.get("dataciteItems") or []),
                "rows_inserted": datacite_rows,
                "error": datacite_error,
                "created_date": today,
                "sensitivity_ord": 100,
            },
        ]
        get_kotoba_client().insert_rows("vertex_copyright_ingest_run", rows)
    except Exception:
        pass
    return {}


# ── LangGraph Store — ingest state persistence ─────────────────────────────

def _update_ingest_state(
    thread_id: str,
    crossref_rows: int,
    datacite_rows: int,
    ok: bool,
) -> None:
    """
    Write last-run summary into kotoba store for cross-thread memory.
    Namespace: ("did:web:copyright.etzhayyim.com", "ingest_state")
    Key: "last_run"
    """
    try:
        import asyncio
        import os

        from kotodama.langgraph_store_kotoba import KotobaStore
        store = KotobaStore()
        ns = (_COPYRIGHT_DID, "ingest_state")

        async def _put():
            from langgraph.store.base import PutOp
            await store.abatch([
                PutOp(
                    namespace=ns,
                    key="last_run",
                    value={
                        "thread_id": thread_id,
                        "crossref_rows": crossref_rows,
                        "datacite_rows": datacite_rows,
                        "ok": ok,
                        "ts": _now_str(),
                    },
                )
            ])

        asyncio.run(_put())
    except Exception:
        pass


# ── Graph factory ──────────────────────────────────────────────────────────

def build_graph():
    """
    Build and compile the copyright ingest StateGraph.

    Flow:
      fetch_crossref → insert_crossref → fetch_datacite → insert_datacite
      → emit_audit → END

    Crossref and DataCite are serialised (not parallel) to avoid
    simultaneous connection pressure.
    """
    from langgraph.graph import END, StateGraph

    builder = StateGraph(CopyrightIngestState)
    builder.add_node("fetch_crossref", fetch_crossref)
    builder.add_node("insert_crossref", insert_crossref)
    builder.add_node("fetch_datacite", fetch_datacite)
    builder.add_node("insert_datacite", insert_datacite)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("fetch_crossref")
    builder.add_edge("fetch_crossref", "insert_crossref")
    builder.add_edge("insert_crossref", "fetch_datacite")
    builder.add_edge("fetch_datacite", "insert_datacite")
    builder.add_edge("insert_datacite", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
