# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101507 — Engine (segment 26).

Bespoke graph for engine validation, diagnostics, and certification.
Segment 26: Power Generation and Distribution Machinery and Accessories.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101507"
UNISPSC_TITLE = "Engine"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    engine_specs: dict[str, Any]
    diagnostic_passed: bool
    performance_score: float
    certification_status: str


def validate_engine_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical and technical specifications of the engine."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    # Core engine validation: requires horsepower and thermal efficiency data
    is_valid = bool(specs.get("horsepower") and specs.get("thermal_efficiency"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_engine_specs"],
        "engine_specs": specs,
        "diagnostic_passed": is_valid,
    }


def perform_diagnostics(state: State) -> dict[str, Any]:
    """Simulates performance diagnostics and stress tests."""
    specs = state.get("engine_specs", {})
    hp = float(specs.get("horsepower", 0))
    eff = float(specs.get("thermal_efficiency", 0))

    # Synthetic performance index
    score = (hp / 1000.0) * eff if hp > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_diagnostics"],
        "performance_score": score,
        "certification_status": "VALID_STATE" if score > 0.4 else "INVALID_STATE",
    }


def certify_engine(state: State) -> dict[str, Any]:
    """Finalizes the certification process and emits the engine status."""
    status = state.get("certification_status", "UNKNOWN")
    passed = state.get("diagnostic_passed", False)
    score = state.get("performance_score", 0.0)

    is_certified = passed and status == "VALID_STATE" and score > 0.5
    final_label = "OPERATIONAL_CERTIFIED" if is_certified else "NON_COMPLIANT"

    return {
        "log": [f"{UNISPSC_CODE}:certify_engine"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_label": final_label,
            "performance_index": round(score, 4),
            "ok": is_certified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_engine_specs)
_g.add_node("diagnose", perform_diagnostics)
_g.add_node("certify", certify_engine)

_g.add_edge(START, "validate")
_g.add_edge("validate", "diagnose")
_g.add_edge("diagnose", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
