# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121806 — Fluid (segment 15).

Bespoke logic for managing fluid material specifications, quality control,
and safety verification for industrial lubricants and hydraulic fluids.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121806"
UNISPSC_TITLE = "Fluid"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Fluid management
    viscosity_index: float
    volume_liters: float
    contamination_ppm: int
    safety_data_sheet_verified: bool
    batch_status: str


def validate_fluid_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the fluid batch."""
    inp = state.get("input") or {}
    visc = float(inp.get("viscosity", 0.0))
    vol = float(inp.get("volume", 0.0))
    sds = bool(inp.get("has_sds", False))

    return {
        "log": [f"{UNISPSC_CODE}:validate_fluid_specs"],
        "viscosity_index": visc,
        "volume_liters": vol,
        "safety_data_sheet_verified": sds,
    }


def perform_quality_analysis(state: State) -> dict[str, Any]:
    """Analyzes contamination levels and verifies safety compliance."""
    inp = state.get("input") or {}
    ppm = int(inp.get("contamination", 100))

    # Logic: Batch is viable if contamination is low and SDS is present
    sds_ok = state.get("safety_data_sheet_verified", False)
    is_clean = ppm < 40

    status = "CERTIFIED" if (sds_ok and is_clean) else "QUARANTINE"

    return {
        "log": [f"{UNISPSC_CODE}:perform_quality_analysis"],
        "contamination_ppm": ppm,
        "batch_status": status,
    }


def finalize_fluid_manifest(state: State) -> dict[str, Any]:
    """Generates the final result manifest for the fluid agent."""
    status = state.get("batch_status", "UNKNOWN")
    is_ok = status == "CERTIFIED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_fluid_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "ok": is_ok,
            "metrics": {
                "viscosity": state.get("viscosity_index"),
                "volume": state.get("volume_liters"),
                "contamination": state.get("contamination_ppm")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_fluid_specs)
_g.add_node("analyze", perform_quality_analysis)
_g.add_node("finalize", finalize_fluid_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
