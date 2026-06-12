# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21111508"
UNISPSC_TITLE = "Mining"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21111508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    extraction_site_id: str
    resource_type: str
    safety_clearance: bool
    estimated_tonnage: float


def survey_site(state: State) -> dict[str, Any]:
    """Initial node to identify the mining site and target resources."""
    inp = state.get("input") or {}
    site_id = inp.get("site_id", "NORTH-PIT-01")
    resource = inp.get("resource", "Industrial Minerals")

    return {
        "log": [f"{UNISPSC_CODE}:survey_site"],
        "extraction_site_id": site_id,
        "resource_type": resource,
    }


def safety_audit(state: State) -> dict[str, Any]:
    """Node to verify structural integrity and safety protocols for the operation."""
    inp = state.get("input") or {}
    depth = inp.get("depth_meters", 50)

    # Mining safety logic: excessive depth without special permits fails audit
    is_safe = depth < 1000

    return {
        "log": [f"{UNISPSC_CODE}:safety_audit"],
        "safety_clearance": is_safe,
    }


def calculate_output(state: State) -> dict[str, Any]:
    """Final node to estimate yield and package the mining operation result."""
    safe = state.get("safety_clearance", False)
    site = state.get("extraction_site_id", "N/A")
    res = state.get("resource_type", "N/A")

    tonnage = 5000.0 if safe else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_output"],
        "estimated_tonnage": tonnage,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "site": site,
            "resource": res,
            "tonnage_est": tonnage,
            "ok": safe,
        },
    }


_g = StateGraph(State)

_g.add_node("survey_site", survey_site)
_g.add_node("safety_audit", safety_audit)
_g.add_node("calculate_output", calculate_output)

_g.add_edge(START, "survey_site")
_g.add_edge("survey_site", "safety_audit")
_g.add_edge("safety_audit", "calculate_output")
_g.add_edge("calculate_output", END)

graph = _g.compile()
