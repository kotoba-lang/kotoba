# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352111 — Gas (segment 12).

Bespoke logic for gas utility monitoring and telemetry processing. This agent
handles state transitions for gas flow parameters, safety verification, and
composition analysis within the Etz Hayyim actor framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352111"
UNISPSC_TITLE = "Gas"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352111"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Gas
    pressure_psi: float
    flow_rate_scfh: float
    purity_level: float
    is_hazardous: bool
    safety_clearance: bool


def inspect_intake(state: State) -> dict[str, Any]:
    """Analyze incoming telemetry and initialize gas state parameters."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_intake"],
        "pressure_psi": float(inp.get("pressure", 0.0)),
        "flow_rate_scfh": float(inp.get("flow", 0.0)),
        "purity_level": float(inp.get("purity", 1.0)),
        "is_hazardous": bool(inp.get("hazardous", False)),
    }


def verify_flow_integrity(state: State) -> dict[str, Any]:
    """Check pressure and flow rate against safety thresholds."""
    pressure = state.get("pressure_psi", 0.0)
    hazardous = state.get("is_hazardous", False)

    # Simple logic: pressure must be between 0.5 and 100 PSI for clearance
    cleared = (0.5 <= pressure <= 100.0) and not (hazardous and pressure > 50.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_flow_integrity"],
        "safety_clearance": cleared,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Synthesize final result and prepare the agent response."""
    cleared = state.get("safety_clearance", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if cleared else "ALERT",
            "telemetry": {
                "p": state.get("pressure_psi"),
                "f": state.get("flow_rate_scfh"),
                "q": state.get("purity_level"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_intake", inspect_intake)
_g.add_node("verify_flow_integrity", verify_flow_integrity)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "inspect_intake")
_g.add_edge("inspect_intake", "verify_flow_integrity")
_g.add_edge("verify_flow_integrity", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
