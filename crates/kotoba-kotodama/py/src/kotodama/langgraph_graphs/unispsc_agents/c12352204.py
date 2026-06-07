# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352204 — Metal Oxide (segment 12).

Bespoke graph logic for industrial metal oxide processing validation,
handling material purity, particle size distribution, and batch manifest generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352204"
UNISPSC_TITLE = "Metal Oxide"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352204"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Metal Oxide
    purity_verified: bool
    particle_size_microns: float
    batch_serial: str
    oxidation_state: int
    msds_compliant: bool


def inspect_assay(state: State) -> dict[str, Any]:
    """Inspects the input assay data for material purity and compliance."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.0)
    is_compliant = purity >= 99.5

    return {
        "log": [f"{UNISPSC_CODE}:inspect_assay"],
        "purity_verified": is_compliant,
        "msds_compliant": inp.get("msds_check", False),
        "batch_serial": inp.get("batch_id", "TEMP-000")
    }


def characterize_morphology(state: State) -> dict[str, Any]:
    """Simulates characterization of particle size and oxidation state."""
    # Logic based on whether it passed inspection
    if state.get("purity_verified"):
        size = 1.5  # Standard micron size for high purity
        ox_state = 3 # Common for many industrial oxides like Al2O3
    else:
        size = 5.0
        ox_state = 0

    return {
        "log": [f"{UNISPSC_CODE}:characterize_morphology"],
        "particle_size_microns": size,
        "oxidation_state": ox_state
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final digital twin manifest for the metal oxide batch."""
    purity_ok = state.get("purity_verified", False)
    msds_ok = state.get("msds_compliant", False)

    success = purity_ok and msds_ok

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "batch": state.get("batch_serial"),
            "specs": {
                "purity_pass": purity_ok,
                "microns": state.get("particle_size_microns"),
                "oxidation_state": state.get("oxidation_state")
            },
            "status": "CERTIFIED" if success else "REJECTED"
        }
    }


_g = StateGraph(State)

_g.add_node("inspect_assay", inspect_assay)
_g.add_node("characterize_morphology", characterize_morphology)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_assay")
_g.add_edge("inspect_assay", "characterize_morphology")
_g.add_edge("characterize_morphology", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
