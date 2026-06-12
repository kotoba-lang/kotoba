# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141506 — Organosilicon (segment 12).

Bespoke graph implementation for validating chemical specifications,
calculating molecular properties, and certifying organosilicon batches.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141506"
UNISPSC_TITLE = "Organosilicon"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_level: float
    viscosity_cst: float
    silicon_content_pct: float
    molecular_weight: float
    quality_threshold_met: bool


def analyze_spec(state: State) -> dict[str, Any]:
    """Extract and validate initial organosilicon specifications."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.0))
    viscosity = float(inp.get("viscosity", 0.0))
    mol_weight = float(inp.get("mol_weight", 0.0))

    # Basic quality check: Organosilicon typically requires high purity
    is_valid = purity >= 98.5 and viscosity > 0.5

    return {
        "log": [f"{UNISPSC_CODE}:analyze_spec: purity={purity}%, valid={is_valid}"],
        "purity_level": purity,
        "viscosity_cst": viscosity,
        "molecular_weight": mol_weight,
        "quality_threshold_met": is_valid,
    }


def compute_composition(state: State) -> dict[str, Any]:
    """Derive chemical composition metrics based on purity and molecular weight."""
    purity = state.get("purity_level", 0.0)
    # Heuristic: silicon content for standard organosilicon monomers
    silicon_pct = (purity / 100.0) * 28.085

    return {
        "log": [f"{UNISPSC_CODE}:compute_composition: si_content={silicon_pct:.2f}%"],
        "silicon_content_pct": silicon_pct,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generate the final batch certificate and result object."""
    is_ok = state.get("quality_threshold_met", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "certificate": {
            "status": "APPROVED" if is_ok else "REJECTED",
            "silicon_content": state.get("silicon_content_pct", 0.0),
            "viscosity": state.get("viscosity_cst", 0.0)
        },
        "ok": is_ok,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification: batch_{'accepted' if is_ok else 'failed'}"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_spec)
_g.add_node("compute", compute_composition)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "compute")
_g.add_edge("compute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
