"""
business_person_synth_v1 — LangGraph multi-hop synthesis for business_person coverage.

Von Neumann stored-program orchestrator node for coverage.gap.generate task.
Registered as "business_person_synth_v1" in langgraph_registry on module load.

Pipeline (4-node StateGraph):
  1. lei_fetch     — fetch a batch of LEI records from GLEIF API
  2. role_extract  — LLM structured extraction: identify persons + roles from LEI data
  3. did_mint      — generate vertex_id + AT DID stub per person
  4. db_write      — INSERT into vertex_business_person

Input state keys:
  domain       — "business_person"
  worldTotal   — target size (100_000_000)
  batchSize    — how many LEI records to process per invocation (default 50)

Output state keys:
  rowsWritten  — int
  error        — str (empty = success)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives import langgraph_registry

log = logging.getLogger(__name__)

GLEIF_API = "https://api.gleif.org/api/v1/lei-records"
_UA = "business-person-synth/1 (+https://etzhayyim.com)"


# ── State ────────────────────────────────────────────────────────────────────

class BPState(TypedDict, total=False):
    domain: str
    worldTotal: int
    batchSize: int
    # internal
    leiRecords: list[dict[str, Any]]
    persons: list[dict[str, Any]]
    rowsWritten: int
    error: str


# ── Node helpers ──────────────────────────────────────────────────────────────

def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return "bp-" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def _fetch_lei_page(page_size: int, page_num: int = 1) -> list[dict[str, Any]]:
    url = (
        f"{GLEIF_API}?page[size]={page_size}&page[number]={page_num}"
        "&filter[entity.status]=ACTIVE"
    )
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("data", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("lei_fetch failed: %s", exc)
        return []


# ── Nodes ─────────────────────────────────────────────────────────────────────

def lei_fetch(state: BPState) -> BPState:
    batch = int(state.get("batchSize") or 50)
    records = _fetch_lei_page(page_size=min(batch, 200))
    return {**state, "leiRecords": records, "persons": [], "rowsWritten": 0, "error": ""}


def role_extract(state: BPState) -> BPState:
    records = state.get("leiRecords") or []
    if not records:
        return {**state, "persons": [], "error": "no LEI records fetched"}

    # Summarize LEI records for LLM
    lei_snippets = []
    for r in records[:20]:  # process first 20 for cost control
        attrs = r.get("attributes", {}) or {}
        entity = attrs.get("entity", {}) or {}
        lei_snippets.append({
            "lei": r.get("id", ""),
            "name": entity.get("legalName", {}).get("name", ""),
            "jurisdiction": entity.get("jurisdiction", ""),
            "category": entity.get("category", ""),
        })

    system = (
        "You are a business intelligence agent. Given a list of company LEI records, "
        "extract key person roles associated with these companies. "
        "For each company infer ONE representative C-suite person (CEO, CFO, or Chair). "
        "Return a JSON array of objects with keys: "
        "lei (string), personName (string), role (string), jurisdiction (string). "
        "If you cannot determine a person, set personName to empty string. "
        "Return ONLY the JSON array."
    )
    user = f"LEI records:\n{json.dumps(lei_snippets, ensure_ascii=False)}"

    try:
        result = llm.call_tier_json("deep", system=system, user=user)
    except Exception as exc:  # noqa: BLE001
        return {**state, "persons": [], "error": f"llm role_extract: {exc}"}

    persons: list[dict[str, Any]] = []
    if isinstance(result, list):
        persons = result
    elif isinstance(result, dict):
        persons = result.get("persons") or result.get("data") or []

    # Filter: only persons with a non-empty name
    persons = [p for p in persons if isinstance(p, dict) and p.get("personName")]
    return {**state, "persons": persons}


def did_mint(state: BPState) -> BPState:
    persons = state.get("persons") or []
    minted = []
    for p in persons:
        lei = str(p.get("lei") or "")
        name = str(p.get("personName") or "")
        role = str(p.get("role") or "unknown")
        jurisdiction = str(p.get("jurisdiction") or "")
        if not name:
            continue
        vertex_id = (
            f"at://did:web:business-person.etzhayyim.com/"
            f"com.etzhayyim.apps.businessPerson.person/{_stable_id(lei, name, role)}"
        )
        minted.append({
            "vertex_id": vertex_id,
            "lei": lei[:64],
            "person_name": name[:255],
            "role": role[:128],
            "jurisdiction": jurisdiction[:8],
            "source": "gleif_lei",
        })
    return {**state, "persons": minted}


def db_write(state: BPState) -> BPState:
    persons = state.get("persons") or []
    if not persons:
        return {**state, "rowsWritten": 0}

    from datetime import datetime, timezone
    ts_date = datetime.now(timezone.utc).date().isoformat()
    client = get_kotoba_client()
    try:
        written = 0
        for p in persons:
            lei = p["lei"]
            name = p["person_name"]
            role = p["role"]
            country = p["jurisdiction"][:3] if p["jurisdiction"] else ""
            # Use existing vertex_business_person schema (0001_initial_schema.ts)
            # key columns: vertex_id, display_name, name, title, org_name, country, source, source_url, created_date
            row_dict = {
                "vertex_id": p["vertex_id"],
                "display_name": name,
                "name": name,
                "title": role,
                "org_name": f"LEI:{lei}",
                "country": country,
                "source": "gleif_lei",
                "source_url": f"https://api.gleif.org/api/v1/lei-records/{lei}",
                "created_date": ts_date,
            }
            client.insert_row("vertex_business_person", row_dict)
            written += 1
    except Exception as exc:  # noqa: BLE001
        return {**state, "rowsWritten": 0, "error": f"db_write: {exc}"}

    return {**state, "rowsWritten": written, "error": ""}


# ── Graph ─────────────────────────────────────────────────────────────────────

def _build_graph() -> Any:
    g: StateGraph = StateGraph(BPState)
    g.add_node("lei_fetch", lei_fetch)
    g.add_node("role_extract", role_extract)
    g.add_node("did_mint", did_mint)
    g.add_node("db_write", db_write)

    g.add_edge(START, "lei_fetch")
    g.add_edge("lei_fetch", "role_extract")
    g.add_edge("role_extract", "did_mint")
    g.add_edge("did_mint", "db_write")
    g.add_edge("db_write", END)

    return g.compile()


# Register on module load (lazy — only compiled when the module is first imported)
_graph = _build_graph()
langgraph_registry.register("business_person_synth_v1", _graph)
log.info("business_person_synth_v1 registered in langgraph_registry")
