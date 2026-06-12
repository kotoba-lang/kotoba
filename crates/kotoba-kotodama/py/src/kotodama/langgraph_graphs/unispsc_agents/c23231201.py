# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231201 — Machine Spec (segment 23).
Bespoke logic for industrial machine specification processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231201"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Machine Spec
    raw_specs: dict[str, Any]
    verified_dimensions: bool
    power_requirements: dict[str, str]
    safety_standards: list[str]


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input machine specifications for completeness."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Check for basic manufacturing specs
    required = ["dimensions", "weight", "material"]
    has_required = all(k in specs for k in required)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "raw_specs": specs,
        "verified_dimensions": has_required,
        "safety_standards": inp.get("safety_protocols", ["ISO-9001"])
    }


def analyze_requirements(state: State) -> dict[str, Any]:
    """Analyzes power and operational requirements based on machine specs."""
    specs = state.get("raw_specs") or {}

    # Extract power configuration or default to industrial standard
    voltage = specs.get("voltage", "400V")
    phase = specs.get("phase", "3-phase")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_requirements"],
        "power_requirements": {
            "voltage": voltage,
            "phase": phase,
            "peak_load": specs.get("peak_load", "25kW")
        }
    }


def finalize_machine_report(state: State) -> dict[str, Any]:
    """Finalizes the bespoke machine specification report."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_machine_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "verified": state.get("verified_dimensions", False),
            "power_config": state.get("power_requirements"),
            "safety_certs": state.get("safety_standards"),
            "status": "specification_finalized"
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("analyze", analyze_requirements)
_g.add_node("finalize", finalize_machine_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
