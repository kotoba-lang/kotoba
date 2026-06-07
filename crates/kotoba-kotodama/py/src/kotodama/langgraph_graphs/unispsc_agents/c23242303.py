# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242303 — Machine Spec.
Bespoke logic for industrial machine specification processing and validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242303"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242303"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Machine Spec
    parameters: dict[str, float]
    is_compliant: bool
    material_compatibility: list[str]
    engineering_signature: str


def ingest_parameters(state: State) -> dict[str, Any]:
    """Identifies and extracts machine parameters from the input payload."""
    inp = state.get("input") or {}
    raw_params = inp.get("specs", {})

    # Extract dimensions or power ratings
    params = {
        "voltage": float(raw_params.get("voltage", 0.0)),
        "power_kw": float(raw_params.get("power_kw", 0.0)),
        "max_rpm": float(raw_params.get("max_rpm", 0.0))
    }

    return {
        "log": [f"{UNISPSC_CODE}:ingest_parameters"],
        "parameters": params,
        "material_compatibility": ["Steel", "Aluminum", "Titanium"],
    }


def validate_constraints(state: State) -> dict[str, Any]:
    """Validates that extracted parameters meet safety and operational constraints."""
    params = state.get("parameters", {})

    # Simple logic: must have some power and not exceed RPM limits
    # Safety threshold: 500kW and 20,000 RPM
    is_safe = 0 < params.get("power_kw", 0) < 500 and params.get("max_rpm", 0) < 20000

    return {
        "log": [f"{UNISPSC_CODE}:validate_constraints"],
        "is_compliant": is_safe,
        "engineering_signature": "SIG-AUTO-23242303" if is_safe else "SIG-PENDING",
    }


def record_specification(state: State) -> dict[str, Any]:
    """Finalizes the machine specification record with metadata."""
    compliant = state.get("is_compliant", False)
    sig = state.get("engineering_signature", "UNRESOLVED")

    return {
        "log": [f"{UNISPSC_CODE}:record_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "status": "VALIDATED" if compliant else "INVALID",
            "signature": sig,
            "ok": compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest_parameters", ingest_parameters)
_g.add_node("validate_constraints", validate_constraints)
_g.add_node("record_specification", record_specification)

_g.add_edge(START, "ingest_parameters")
_g.add_edge("ingest_parameters", "validate_constraints")
_g.add_edge("validate_constraints", "record_specification")
_g.add_edge("record_specification", END)

graph = _g.compile()
