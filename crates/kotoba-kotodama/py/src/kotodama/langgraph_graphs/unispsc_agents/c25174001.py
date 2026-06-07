# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174001 — Fan Procurement (segment 25).

Bespoke graph for Fan Procurement. This agent handles the specification
validation, vendor matching, and procurement finalization for industrial
and commercial fans.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174001"
UNISPSC_TITLE = "Fan Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Fan Procurement
    airflow_requirement_cfm: int
    mounting_type: str
    vendor_id: str
    lead_time_weeks: int
    spec_validated: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the fan specifications provided in the input."""
    inp = state.get("input") or {}
    cfm = inp.get("cfm", 0)
    m_type = inp.get("mounting", "unknown")

    # Simple validation logic for fan procurement
    valid = cfm > 0 and m_type in ["ceiling", "wall", "floor", "industrial"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "airflow_requirement_cfm": cfm,
        "mounting_type": m_type,
        "spec_validated": valid,
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Simulates finding a vendor based on the validated specifications."""
    if not state.get("spec_validated"):
        return {"log": [f"{UNISPSC_CODE}:source_vendor_skipped"]}

    m_type = state.get("mounting_type")
    # Mock vendor lookup logic
    v_id = f"VEND-FAN-{m_type.upper()}-01"
    lt = 3 if m_type == "industrial" else 1

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor"],
        "vendor_id": v_id,
        "lead_time_weeks": lt,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Wraps up the procurement process and prepares the final result."""
    ok = state.get("spec_validated", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "ok": ok,
    }

    if ok:
        res["details"] = {
            "vendor": state.get("vendor_id"),
            "lead_time_weeks": state.get("lead_time_weeks"),
            "cfm_target": state.get("airflow_requirement_cfm"),
            "mounting": state.get("mounting_type"),
        }
    else:
        res["error"] = "Fan specification validation failed"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("validate", validate_spec)
_g.add_node("source", source_vendor)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
