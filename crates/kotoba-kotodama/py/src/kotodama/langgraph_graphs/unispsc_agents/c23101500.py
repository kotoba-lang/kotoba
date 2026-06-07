# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101500 — Machine Spec (segment 23).

This bespoke implementation handles specific requirements for raw material
processing machinery specifications, including power rating analysis,
maintenance interval calculations, and segment 23 compliance validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101500"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    spec_id: str
    machine_type: str
    power_rating_kw: float
    maintenance_interval_days: int
    is_compliant: bool


def ingest_specification(state: State) -> dict[str, Any]:
    """Parses incoming machine spec data and initializes internal tracking."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:ingest_specification"],
        "spec_id": str(inp.get("id", "MCH-DEFAULT-001")),
        "machine_type": str(inp.get("type", "GENERAL-INDUSTRIAL")),
        "power_rating_kw": float(inp.get("power", 0.0)),
    }


def analyze_compliance(state: State) -> dict[str, Any]:
    """Calculates maintenance cycles and verifies segment 23 regulatory bounds."""
    # Industrial machinery in segment 23 requires variable maintenance intervals based on load.
    power = state.get("power_rating_kw", 0.0)

    # Heuristic: Machines over 75kW require quarterly inspections (90 days).
    # Lighter machinery requires semi-annual inspections (180 days).
    interval = 180 if power < 75 else 90

    # Compliance check: machine must have a defined power rating.
    compliant = power > 0.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_compliance"],
        "maintenance_interval_days": interval,
        "is_compliant": compliant,
    }


def emit_machine_record(state: State) -> dict[str, Any]:
    """Produces the final verified specification record for the ledger."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_machine_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "id": state.get("spec_id"),
                "type": state.get("machine_type"),
                "rating": f"{state.get('power_rating_kw')}kW",
                "maintenance_cycle": state.get("maintenance_interval_days"),
                "compliance_verified": state.get("is_compliant"),
            },
            "status": "VALIDATED",
            "ok": state.get("is_compliant", False),
        },
    }


_g = StateGraph(State)

_g.add_node("ingest", ingest_specification)
_g.add_node("analyze", analyze_compliance)
_g.add_node("emit", emit_machine_record)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
