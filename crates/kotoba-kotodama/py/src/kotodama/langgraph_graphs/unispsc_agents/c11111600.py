# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111600 — Mineral Procurement (segment 11).

Bespoke logic for mineral procurement orchestration, including geological
validation, yield assessment, and regulatory compliance checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111600"
UNISPSC_TITLE = "Mineral Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    geological_report_valid: bool
    extraction_site_id: str
    estimated_tonnage: float
    regulatory_compliance_check: bool


def validate_procurement_request(state: State) -> dict[str, Any]:
    """Validates the initial procurement request and geological data availability."""
    inp = state.get("input") or {}
    site_id = inp.get("site_id", "UNKNOWN-SITE")
    has_report = inp.get("has_geological_report", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_procurement_request"],
        "geological_report_valid": has_report,
        "extraction_site_id": site_id,
    }


def assess_mineral_yield(state: State) -> dict[str, Any]:
    """Assesses potential yield and performs a basic regulatory compliance check."""
    inp = state.get("input") or {}
    tonnage = float(inp.get("requested_tonnage", 0.0))
    # Compliance requires a valid geological report and positive tonnage
    report_ok = state.get("geological_report_valid", False)
    compliance = (tonnage > 0) and report_ok

    return {
        "log": [f"{UNISPSC_CODE}:assess_mineral_yield"],
        "estimated_tonnage": tonnage,
        "regulatory_compliance_check": compliance,
    }


def finalize_procurement_logistics(state: State) -> dict[str, Any]:
    """Finalizes the procurement process and constructs the result payload."""
    is_compliant = state.get("regulatory_compliance_check", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_logistics"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "site_id": state.get("extraction_site_id"),
            "tonnage": state.get("estimated_tonnage"),
            "status": "APPROVED" if is_compliant else "REJECTED",
            "ok": is_compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_procurement_request)
_g.add_node("assess", assess_mineral_yield)
_g.add_node("finalize", finalize_procurement_logistics)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
