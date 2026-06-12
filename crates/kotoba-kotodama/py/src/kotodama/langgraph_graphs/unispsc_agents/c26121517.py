# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26121517 — Wire (segment 26).

Bespoke graph logic for electrical wire specification and integrity verification.
This agent handles the lifecycle of wire certification, including gauge inspection,
voltage rating verification, and continuity checks.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26121517"
UNISPSC_TITLE = "Wire"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26121517"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Wire
    gauge_awg: int
    conductor_material: str
    voltage_max: int
    insulation_type: str
    integrity_check_passed: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Inspects input parameters and initializes wire physical specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "gauge_awg": inp.get("gauge", 14),
        "conductor_material": inp.get("material", "Copper"),
        "voltage_max": inp.get("voltage", 600),
        "insulation_type": inp.get("insulation", "THHN"),
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Performs simulated electrical safety and compliance checks."""
    gauge = state.get("gauge_awg", 14)
    voltage = state.get("voltage_max", 600)

    # Simulated engineering rule: Thinner wires (higher AWG) have lower voltage thresholds
    is_compliant = not (gauge > 18 and voltage > 300)

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "integrity_check_passed": is_compliant,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Finalizes the wire certification manifest and records the outcome."""
    is_ok = state.get("integrity_check_passed", False)
    status = "Certified" if is_ok else "Compliance Failure"

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "certification_status": status,
            "metadata": {
                "awg": state.get("gauge_awg"),
                "material": state.get("conductor_material"),
                "rating": f"{state.get('voltage_max')}V",
            },
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("verify", verify_compliance)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
