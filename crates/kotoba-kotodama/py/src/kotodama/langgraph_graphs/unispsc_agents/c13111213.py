# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111213"
UNISPSC_TITLE = "Lubricant"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111213"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke Lubricant state fields
    viscosity_index: int
    base_oil_type: str
    is_synthetic: bool
    standards_met: list[str]
    compliance_passed: bool


def analyze_specs(state: State) -> dict[str, Any]:
    """Analyzes the requested lubricant specifications and base oil chemistry."""
    inp = state.get("input") or {}
    target_v = inp.get("target_viscosity", 100)
    oil_type = inp.get("oil_type", "Mineral")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specs"],
        "viscosity_index": int(target_v),
        "base_oil_type": str(oil_type),
        "is_synthetic": str(oil_type).lower() == "synthetic",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Cross-references properties against SAE and ISO industry standards."""
    v_index = state.get("viscosity_index", 0)
    standards = ["ISO 9001"]

    # Basic logic to simulate standard verification
    if v_index >= 30:
        standards.append("SAE J300")
    if state.get("is_synthetic"):
        standards.append("ASTM D4485")

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "standards_met": standards,
        "compliance_passed": len(standards) > 1,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Finalizes the Lubricant actor state and emits the verified result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "viscosity": state.get("viscosity_index"),
                "base_oil": state.get("base_oil_type"),
                "standards": state.get("standards_met"),
            },
            "verified": state.get("compliance_passed", False),
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_specs)
_g.add_node("verify", verify_compliance)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
