# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23111503 — Compressor (segment 23).
Bespoke implementation for industrial compressor configuration and state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23111503"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23111503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Compressor
    target_pressure_psi: float
    volumetric_flow_cfm: float
    compression_stages: int
    operational_efficiency: float


def analyze_specs(state: State) -> dict[str, Any]:
    """Analyzes requirements to determine target pressure and flow."""
    inp = state.get("input") or {}
    psi = float(inp.get("psi", 120.0))
    cfm = float(inp.get("cfm", 50.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specs -> {psi} PSI @ {cfm} CFM"],
        "target_pressure_psi": psi,
        "volumetric_flow_cfm": cfm,
    }


def determine_configuration(state: State) -> dict[str, Any]:
    """Determines the number of compression stages and efficiency based on specs."""
    psi = state.get("target_pressure_psi", 0.0)

    # Multistage compression for higher pressures
    stages = 1 if psi <= 150 else 2
    # Efficiency calculation (simulated)
    efficiency = 0.88 if stages == 1 else 0.82

    return {
        "log": [f"{UNISPSC_CODE}:determine_configuration -> stages:{stages}, eff:{efficiency}"],
        "compression_stages": stages,
        "operational_efficiency": efficiency,
    }


def generate_report(state: State) -> dict[str, Any]:
    """Generates the final compressor asset report."""
    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "specification_summary": {
            "psi": state.get("target_pressure_psi"),
            "cfm": state.get("volumetric_flow_cfm"),
            "stages": state.get("compression_stages"),
            "efficiency": state.get("operational_efficiency"),
        },
        "ok": True,
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_specs)
_g.add_node("configure", determine_configuration)
_g.add_node("report", generate_report)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "configure")
_g.add_edge("configure", "report")
_g.add_edge("report", END)

graph = _g.compile()
