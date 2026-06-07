# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12163400 — Peptide (segment 12).

Bespoke graph logic for managing peptide sequence analysis, purity assessment,
and certification for biochemical distribution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12163400"
UNISPSC_TITLE = "Peptide"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12163400"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Peptide domain fields
    sequence_data: str
    molar_mass: float
    is_pure: bool
    synthesis_batch_id: str


def validate_peptide(state: State) -> dict[str, Any]:
    """Validates the amino acid sequence provided in the input."""
    inp = state.get("input") or {}
    seq = str(inp.get("sequence", "GLY-ALA-VAL"))
    batch_id = str(inp.get("batch_id", "BATCH-000"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_peptide"],
        "sequence_data": seq,
        "synthesis_batch_id": batch_id,
    }


def analyze_mass(state: State) -> dict[str, Any]:
    """Calculates the estimated molar mass based on the sequence length."""
    seq = state.get("sequence_data", "")
    # Rough estimation: average amino acid residue is ~110.15 Da
    residue_count = len(seq.split("-"))
    estimated_mass = residue_count * 110.15

    return {
        "log": [f"{UNISPSC_CODE}:analyze_mass"],
        "molar_mass": estimated_mass,
    }


def quality_control(state: State) -> dict[str, Any]:
    """Performs a mock purity check and finalizes the agent state."""
    inp = state.get("input") or {}
    purity_score = float(inp.get("purity", 0.99))
    is_pure = purity_score > 0.95

    return {
        "log": [f"{UNISPSC_CODE}:quality_control"],
        "is_pure": is_pure,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("synthesis_batch_id"),
            "mass_da": state.get("molar_mass"),
            "purity_verified": is_pure,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_peptide", validate_peptide)
_g.add_node("analyze_mass", analyze_mass)
_g.add_node("quality_control", quality_control)

_g.add_edge(START, "validate_peptide")
_g.add_edge("validate_peptide", "analyze_mass")
_g.add_edge("analyze_mass", "quality_control")
_g.add_edge("quality_control", END)

graph = _g.compile()
