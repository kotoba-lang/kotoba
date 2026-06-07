"""
copyright.fulltext — LangGraph StateGraph (ADR-2605080600 Phase 5).

Fetches open-access full text for CC-BY / public-domain works in
vertex_work, stores extracted text in vertex_work_blob, making
copyright content available in v_training_text for LLM training.

Pipeline:
  START → query_oa_works → fetch_fulltext → store_blobs → emit_audit → END

Steps:
  1. query_oa_works  — SELECT vertex_work rows with berne_automatic=true
                       that have no vertex_work_blob yet (up to batch_size)
  2. fetch_fulltext  — Unpaywall API per DOI → open-access URL →
                       HTTP GET PDF/HTML → extract text
  3. store_blobs     — INSERT into vertex_work_blob (status=done|failed)
  4. emit_audit      — vertex_repo_commit OCEL row

Unpaywall API: https://api.unpaywall.org/v2/{doi}?email=jun@etzhayyim.com
  Response: best_oa_location.url_for_pdf / url_for_landing_page
  License:  best_oa_location.license  (cc-by, cc-by-sa, cc0, …)

Keeps each run bounded: default batch_size=50 works per invocation.
Schedule: K8s CronJob POST /runs {"assistant_id":"copyright_fulltext"}
          0 */6 * * *  (every 6h, catches new DOIs from copyright_ingest)
"""

from __future__ import annotations

import hashlib
import time as _time
import uuid
from typing import Any, TypedDict
from kotodama.kotoba_datomic import get_kotoba_client

import httpx

_UNPAYWALL_URL = "https://api.unpaywall.org/v2/{doi}?email=jun%40etzhayyim.com"
_COPYRIGHT_DID = "did:web:copyright.etzhayyim.com"
_TIMEOUT = 30.0
_OA_LICENSES = {
    "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa",
    "cc0", "public-domain", "cc-by-4.0", "cc-by-sa-4.0",
}
_MAX_TEXT_BYTES = 2_000_000  # 2 MB cap per work


# ── State ─────────────────────────────────────────────────────────────

class CopyrightFulltextState(TypedDict, total=False):
    batchSize: int
    works: list[dict]          # [{vertex_id, doi, registry}, ...]
    blobs: list[dict]          # [{work_vertex_id, doi, oa_url, fulltext, license, lang, status, error}, ...]
    worksQueried: int
    blobsStored: int
    blobsFailed: int
    ok: bool
    error: str | None


# ── Helpers ───────────────────────────────────────────────────────────

def _now_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _work_blob_vertex_id(doi: str) -> str:
    h = hashlib.sha256(doi.encode()).hexdigest()[:16]
    return f"at://{_COPYRIGHT_DID}/com.etzhayyim.apps.copyright.workblob/blob-{h}"


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Run pdftotext in subprocess to extract text from PDF bytes."""
    import subprocess
    try:
        result = subprocess.run(
            ["pdftotext", "-", "-"],
            input=pdf_bytes,
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _extract_text_from_html(html_bytes: bytes) -> str:
    """Strip HTML tags, return plain text."""
    import re
    text = html_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch_oa_text(doi: str) -> tuple[str, str, str]:
    """
    Query Unpaywall for open-access location.
    Returns (fulltext, license, oa_url). Empty strings on failure.
    """
    url = _UNPAYWALL_URL.format(doi=doi.replace("/", "%2F"))
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url, headers={"Accept": "application/json"})
            if resp.status_code == 404:
                return "", "", ""
            resp.raise_for_status()
            data = resp.json()

        best = data.get("best_oa_location") or {}
        license_str = (best.get("license") or "").lower().strip()
        if license_str not in _OA_LICENSES:
            return "", license_str, ""

        pdf_url = best.get("url_for_pdf") or ""
        landing_url = best.get("url_for_landing_page") or ""
        oa_url = pdf_url or landing_url
        if not oa_url:
            return "", license_str, ""

        # Fetch the actual document
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            doc_resp = client.get(oa_url)
            doc_resp.raise_for_status()
            content_type = doc_resp.headers.get("content-type", "")
            raw = doc_resp.content

        if len(raw) > _MAX_TEXT_BYTES:
            raw = raw[:_MAX_TEXT_BYTES]

        if "pdf" in content_type.lower() or oa_url.lower().endswith(".pdf"):
            text = _extract_text_from_pdf(raw)
        else:
            text = _extract_text_from_html(raw)

        return text, license_str, oa_url

    except Exception:
        return "", "", ""


# ── Nodes ─────────────────────────────────────────────────────────────







def query_oa_works(state: CopyrightFulltextState) -> dict:
    """
    SELECT vertex_work rows that have berne_automatic=true AND a DOI,
    but no corresponding vertex_work_blob yet.
    """
    batch_size = int(state.get("batchSize") or 50)
    try:
        # R0: Datalog query to select works without corresponding work_blob
        query_edn = f"""
            [:find (pull ?w [:vertex/id :work/doi :work/registry])
             :where
             [?w :work/berne_automatic true]
             [?w :work/doi ?doi]
             (not [?wb :work-blob/work-vertex-id ?w])]
             :limit {batch_size}
        """
        rows_data = get_kotoba_client().q(query_edn)
        works = []
        for row in rows_data:
            work = row[0] # pull returns a map within a list
            works.append({
                "vertex_id": work.get(":vertex/id"),
                "doi": work.get(":work/doi"),
                "registry": work.get(":work/registry"),
            })
        return {"works": works, "worksQueried": len(works)}
    except Exception as e:
        return {"works": [], "worksQueried": 0, "error": str(e)}


def fetch_fulltext(state: CopyrightFulltextState) -> dict:
    """
    For each work, query Unpaywall and fetch the open-access full text.
    Assembles blob dicts (not yet stored to DB).
    """
    works = state.get("works") or []
    blobs: list[dict] = []
    for work in works:
        doi = work["doi"]
        fulltext, license_str, oa_url = _fetch_oa_text(doi)
        blob: dict = {
            "work_vertex_id": work["vertex_id"],
            "doi": doi,
            "oa_url": oa_url,
            "license": license_str,
            "lang": None,
            "fulltext": fulltext if fulltext else None,
            "status": "done" if fulltext else "failed",
            "error": None if fulltext else "no_oa_text",
        }
        blobs.append(blob)
        # Rate-limit: Unpaywall asks for ≤100k req/day (~1/s average)
        _time.sleep(0.2)
    return {"blobs": blobs}


def store_blobs(state: CopyrightFulltextState) -> dict:
    """INSERT vertex_work_blob + edge_work_blob_of rows (ADR-2605080300)."""
    blobs = state.get("blobs") or []
    stored = 0
    failed = 0

    now = _now_str()
    today = now[:10]
    rows_done: list[dict] = []
    rows_fail: list[dict] = []
    edge_rows: list[dict] = []
    for blob in blobs:
        blob_vid = _work_blob_vertex_id(blob["doi"])
        work_vid = blob["work_vertex_id"]
        row = {
            "vertex_id": blob_vid,
            "work_vertex_id": work_vid,
            "doi": blob["doi"],
            "oa_url": blob.get("oa_url") or None,
            "fulltext": blob.get("fulltext"),
            "lang": blob.get("lang"),
            "license": blob.get("license") or None,
            "status": blob["status"],
            "error": blob.get("error"),
            "fetched_at": now,
            "created_date": today,
            "sensitivity_ord": 0,
        }
        if blob["status"] == "done":
            rows_done.append(row)
        else:
            rows_fail.append(row)
        edge_id = "blob-of:" + hashlib.sha256(
            f"{blob_vid}:{work_vid}".encode()
        ).hexdigest()[:16]
        edge_rows.append({
            "edge_id": edge_id,
            "src_vid": blob_vid,
            "dst_vid": work_vid,
            "owner_did": _COPYRIGHT_DID,
            "created_date": today,
            "sensitivity_ord": 0,
        })
    all_rows = rows_done + rows_fail
    if all_rows:
        try:
            get_kotoba_client().insert_rows("vertex_work_blob", all_rows)
            stored = len(rows_done)
            failed = len(rows_fail)
        except Exception:
            failed = len(all_rows)
    if edge_rows:
        try:
            get_kotoba_client().insert_rows("edge_work_blob_of", edge_rows)
        except Exception:
            pass
    return {"blobsStored": stored, "blobsFailed": failed, "ok": True}


def emit_audit(state: CopyrightFulltextState) -> dict:
    """Write OCEL audit row (non-fatal, ADR-2605080300)."""
    ts_ms = int(_time.time() * 1000)
    stored = state.get("blobsStored", 0)
    failed = state.get("blobsFailed", 0)
    ok = state.get("ok", True)
    try:
        record_json_content = (
            f'{{"worksQueried":{state.get("worksQueried", 0)},'
            f'"blobsStored":{stored},'
            f'"blobsFailed":{failed},'
            f'"ok":{str(ok).lower()}}}'
        )
        audit_row = {
            "vertex_id": str(uuid.uuid4()),
            "repo": _COPYRIGHT_DID,
            "collection": "com.etzhayyim.apps.copyright.fulltext",
            "rkey": f"lg-{ts_ms}",
            "action": "create",
            "ts_ms": ts_ms,
            "record_json": record_json_content,
        }
        get_kotoba_client().insert_row("vertex_repo_commit", audit_row)
    except Exception:
        pass
    return {}


# ── Graph factory ─────────────────────────────────────────────────────

def build_graph():
    """
    Build copyright fulltext StateGraph.

    Flow:
      query_oa_works → fetch_fulltext → store_blobs → emit_audit → END
    """
    from langgraph.graph import END, StateGraph

    builder = StateGraph(CopyrightFulltextState)
    builder.add_node("query_oa_works", query_oa_works)
    builder.add_node("fetch_fulltext", fetch_fulltext)
    builder.add_node("store_blobs", store_blobs)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("query_oa_works")
    builder.add_edge("query_oa_works", "fetch_fulltext")
    builder.add_edge("fetch_fulltext", "store_blobs")
    builder.add_edge("store_blobs", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
