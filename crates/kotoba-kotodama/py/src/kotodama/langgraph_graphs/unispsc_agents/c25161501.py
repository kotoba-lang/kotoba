# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25161501"
UNISPSC_TITLE = "Touring Bike"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25161501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Touring Bike specification
    frame_material: str
    rack_mounts_verified: bool
    pannier_capacity_liters: int
    drivetrain_groupset: str
    tire_clearance_mm: int


def select_frame(state: State) -> dict[str, Any]:
    """Node: Select frame material and verify rack compatibility."""
    inp = state.get("input") or {}
    material = inp.get("material", "Chromoly Steel")
    mounts = True if material.lower() in ["chromoly steel", "aluminum", "steel"] else False
    return {
        "log": [f"{UNISPSC_CODE}:select_frame"],
        "frame_material": material,
        "rack_mounts_verified": mounts,
    }


def configure_utility(state: State) -> dict[str, Any]:
    """Node: Configure load capacity and tire clearance for long-distance travel."""
    inp = state.get("input") or {}
    capacity = inp.get("requested_capacity", 40)
    clearance = 45 if capacity > 30 else 32
    return {
        "log": [f"{UNISPSC_CODE}:configure_utility"],
        "pannier_capacity_liters": capacity,
        "tire_clearance_mm": clearance,
    }


def optimize_drivetrain(state: State) -> dict[str, Any]:
    """Node: Assign appropriate drivetrain based on load and frame specs."""
    material = state.get("frame_material", "Steel")
    capacity = state.get("pannier_capacity_liters", 0)

    if capacity > 50:
        groupset = "Rohloff Speedhub"
    elif "Steel" in material:
        groupset = "Shimano Deore XT"
    else:
        groupset = "Shimano GRX"

    return {
        "log": [f"{UNISPSC_CODE}:optimize_drivetrain"],
        "drivetrain_groupset": groupset,
    }


def build_manifest(state: State) -> dict[str, Any]:
    """Node: Finalize the touring bike manifest."""
    spec = {
        "frame": state.get("frame_material"),
        "mounts": state.get("rack_mounts_verified"),
        "capacity_l": state.get("pannier_capacity_liters"),
        "drivetrain": state.get("drivetrain_groupset"),
        "tire_clearance": state.get("tire_clearance_mm"),
    }
    return {
        "log": [f"{UNISPSC_CODE}:build_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": spec,
            "status": "validated" if state.get("rack_mounts_verified") else "warning_non_standard",
        },
    }


_g = StateGraph(State)
_g.add_node("select_frame", select_frame)
_g.add_node("configure_utility", configure_utility)
_g.add_node("optimize_drivetrain", optimize_drivetrain)
_g.add_node("build_manifest", build_manifest)

_g.add_edge(START, "select_frame")
_g.add_edge("select_frame", "configure_utility")
_g.add_edge("configure_utility", "optimize_drivetrain")
_g.add_edge("optimize_drivetrain", "build_manifest")
_g.add_edge("build_manifest", END)

graph = _g.compile()
