# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202503"
UNISPSC_TITLE = "Aircraft Light"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    electrical_match: bool
    lumen_compliance: bool
    component_id: str


def check_electrical_standards(state: State) -> dict[str, Any]:
    """Verify that the light component meets aircraft electrical standards."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 28)
    cid = inp.get("cid", "AL-DEFAULT")
    # Simulation: 28V and 115V are the common aircraft standards
    is_standard = voltage in [28, 115]
    return {
        "log": [f"{UNISPSC_CODE}:check_electrical: voltage={voltage} match={is_standard}"],
        "electrical_match": is_standard,
        "component_id": cid
    }


def verify_illumination(state: State) -> dict[str, Any]:
    """Validate lumen output and beam patterns for safety compliance."""
    inp = state.get("input") or {}
    lumens = inp.get("lumens", 1200)
    # Simulation: Lights must meet minimum intensity thresholds and have valid electricals
    is_compliant = state.get("electrical_match", False) and lumens >= 800
    return {
        "log": [f"{UNISPSC_CODE}:verify_illumination: lumens={lumens} ok={is_compliant}"],
        "lumen_compliance": is_compliant
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generate the procurement readiness record for the aircraft light."""
    ready = state.get("lumen_compliance", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement: ready={ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_ready": ready,
            "cid": state.get("component_id"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("check_electrical", check_electrical_standards)
_g.add_node("verify_illumination", verify_illumination)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "check_electrical")
_g.add_edge("check_electrical", "verify_illumination")
_g.add_edge("verify_illumination", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
