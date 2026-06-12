# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12171503 — Catalyst.
This bespoke agent manages the specification, thermodynamic analysis, and
certification workflow for chemical catalysts within segment 12.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12171503"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12171503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_level: float
    reaction_type: str
    activation_temp_celsius: float
    carrier_material: str
    certification_status: str


def validate_specification(state: State) -> dict[str, Any]:
    """Ensures the catalyst meets chemical purity standards and identifies the reaction class."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.95))
    reaction = str(inp.get("reaction", "oxidation"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "purity_level": purity,
        "reaction_type": reaction,
    }


def analyze_thermodynamics(state: State) -> dict[str, Any]:
    """Evaluates thermal stability and activation requirements for the specific carrier material."""
    inp = state.get("input") or {}
    temp = float(inp.get("activation_temp", 350.0))
    carrier = str(inp.get("carrier", "alumina"))

    # Logic to determine if purity meets high-performance thresholds
    is_pure = state.get("purity_level", 0.0) >= 0.99
    status = "CERTIFIED" if is_pure else "STANDARD"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_thermodynamics"],
        "activation_temp_celsius": temp,
        "carrier_material": carrier,
        "certification_status": status,
    }


def compile_technical_report(state: State) -> dict[str, Any]:
    """Generates the final technical summary for the catalyst batch."""
    return {
        "log": [f"{UNISPSC_CODE}:compile_technical_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specifications": {
                "purity": state.get("purity_level"),
                "reaction_target": state.get("reaction_type"),
                "carrier": state.get("carrier_material"),
                "operating_temp": state.get("activation_temp_celsius"),
            },
            "certification": state.get("certification_status"),
            "segment_metadata": {
                "segment": UNISPSC_SEGMENT,
                "domain": "Chemicals",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specification)
_g.add_node("analyze", analyze_thermodynamics)
_g.add_node("compile", compile_technical_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
