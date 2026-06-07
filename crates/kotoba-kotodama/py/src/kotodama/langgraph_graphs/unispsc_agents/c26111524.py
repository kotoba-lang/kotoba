# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111524"
UNISPSC_TITLE = "Gear"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111524"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Gear power transmission
    gear_profile: str
    material_grade: str
    torque_rating_nm: float
    tolerance_class: int
    quality_verified: bool


def inspect_geometry(state: State) -> dict[str, Any]:
    """Validates the mechanical geometry and gear profile from input."""
    inp = state.get("input") or {}
    profile = inp.get("gear_profile", "spur")
    t_class = inp.get("tolerance_class", 8)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_geometry"],
        "gear_profile": profile,
        "tolerance_class": t_class,
    }


def verify_load_integrity(state: State) -> dict[str, Any]:
    """Simulates verification of material grade and torque capacity."""
    inp = state.get("input") or {}
    m_grade = inp.get("material_grade", "AISI_4140")

    # Simple logic to determine torque rating based on material
    torque_map = {
        "AISI_4140": 1200.0,
        "AISI_1045": 800.0,
        "Stainless_316": 600.0
    }
    rating = torque_map.get(m_grade, 500.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_load_integrity"],
        "material_grade": m_grade,
        "torque_rating_nm": rating,
        "quality_verified": rating >= 600.0
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Generates the final Gear actor result and compliance status."""
    is_verified = state.get("quality_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "profile": state.get("gear_profile"),
                "material": state.get("material_grade"),
                "max_torque": state.get("torque_rating_nm"),
                "tolerance": state.get("tolerance_class")
            },
            "status": "CERTIFIED" if is_verified else "NON_COMPLIANT",
            "ok": True
        }
    }


_g = StateGraph(State)

_g.add_node("inspect_geometry", inspect_geometry)
_g.add_node("verify_load_integrity", verify_load_integrity)
_g.add_node("finalize_asset_record", finalize_asset_record)

_g.add_edge(START, "inspect_geometry")
_g.add_edge("inspect_geometry", "verify_load_integrity")
_g.add_edge("verify_load_integrity", "finalize_asset_record")
_g.add_edge("finalize_asset_record", END)

graph = _g.compile()
