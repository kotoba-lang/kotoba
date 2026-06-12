# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121703 — Rail (segment 25).

Bespoke graph logic for rail component validation, metallurgical verification,
and safety certification according to heavy transport standards.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121703"
UNISPSC_TITLE = "Rail"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    track_gauge_mm: float
    steel_grade_spec: str
    ultrasonic_test_passed: bool
    compliance_certificate_id: str


def validate_input(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    gauge = float(inp.get("gauge", 1435.0))
    grade = str(inp.get("grade", "R260"))
    return {
        "log": [f"{UNISPSC_CODE}:validate_input"],
        "track_gauge_mm": gauge,
        "steel_grade_spec": grade,
    }


def perform_metallurgy_audit(state: State) -> dict[str, Any]:
    grade = state.get("steel_grade_spec", "")
    # Simulation of ultrasonic inspection and chemical composition check
    # Common rail grades: R260, R350HT, R320Cr
    passed = grade in ["R260", "R350HT", "R320Cr"]
    return {
        "log": [f"{UNISPSC_CODE}:perform_metallurgy_audit"],
        "ultrasonic_test_passed": passed,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    passed = state.get("ultrasonic_test_passed", False)
    gauge = state.get("track_gauge_mm", 0.0)

    # Standard gauge check (1435mm is standard European/North American gauge)
    is_standard = (1434.0 <= gauge <= 1436.0)
    fully_compliant = passed and is_standard

    cert_id = f"UIC-860-{UNISPSC_CODE}-2026" if fully_compliant else "NON-COMPLIANT"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "compliance_certificate_id": cert_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "compliance_id": cert_id,
            "standard_gauge": is_standard,
            "ok": fully_compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input)
_g.add_node("audit", perform_metallurgy_audit)
_g.add_node("certify", finalize_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "audit")
_g.add_edge("audit", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
