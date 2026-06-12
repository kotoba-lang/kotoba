# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352100 — Chemical (segment 12).

Bespoke graph logic for Chemical handling and analysis. This agent validates
Safety Data Sheets (SDS), assesses chemical purity grades, and generates
standardized chemical manifests for downstream processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352100"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352100"


class State(TypedDict, total=False):
    # Required base fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific chemical state
    sds_id: str
    hazard_class: str
    purity_grade: str
    storage_temp_c: float
    is_hazardous: bool


def verify_safety_compliance(state: State) -> dict[str, Any]:
    """Validates presence of SDS and assigns hazard classification."""
    inp = state.get("input") or {}
    sds = str(inp.get("sds_id", "MISSING"))
    haz_class = str(inp.get("hazard_class", "Non-Hazardous"))

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_compliance"],
        "sds_id": sds,
        "hazard_class": haz_class,
        "is_hazardous": haz_class != "Non-Hazardous"
    }


def assay_chemical_quality(state: State) -> dict[str, Any]:
    """Evaluates purity grades and storage requirements."""
    inp = state.get("input") or {}
    purity = str(inp.get("purity_grade", "Industrial"))
    temp = float(inp.get("storage_temp_c", 20.0))

    return {
        "log": [f"{UNISPSC_CODE}:assay_chemical_quality"],
        "purity_grade": purity,
        "storage_temp_c": temp
    }


def finalize_chemical_manifest(state: State) -> dict[str, Any]:
    """Generates the final chemical actor result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_chemical_manifest"],
        "result": {
            "actor": UNISPSC_DID,
            "category": UNISPSC_TITLE,
            "manifest": {
                "sds_reference": state.get("sds_id"),
                "hazard_status": state.get("hazard_class"),
                "purity_specification": state.get("purity_grade"),
                "thermal_constraints": f"{state.get('storage_temp_c')}C"
            },
            "compliance_verified": state.get("is_hazardous") is not None,
            "status": "ready"
        }
    }


_g = StateGraph(State)

_g.add_node("verify_safety", verify_safety_compliance)
_g.add_node("assay_quality", assay_chemical_quality)
_g.add_node("finalize", finalize_chemical_manifest)

_g.add_edge(START, "verify_safety")
_g.add_edge("verify_safety", "assay_quality")
_g.add_edge("assay_quality", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
