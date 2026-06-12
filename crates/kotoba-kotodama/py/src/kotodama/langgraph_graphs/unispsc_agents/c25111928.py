# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111928 — Sail Cover (segment 25).

Bespoke graph logic for managing sail cover specifications, material selection,
and UV protection validation for marine hardware accessories.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111928"
UNISPSC_TITLE = "Sail Cover"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111928"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    material_preference: str
    boom_length: float
    uv_resistant: bool
    configuration_status: str


def check_dimensions(state: State) -> dict[str, Any]:
    """Validates the input dimensions for the sail cover."""
    inp = state.get("input") or {}
    length = inp.get("boom_length", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:check_dimensions"],
        "boom_length": float(length),
        "configuration_status": "dimensions_checked" if length > 0 else "invalid_dimensions"
    }


def determine_material(state: State) -> dict[str, Any]:
    """Selects material based on input preferences and durability requirements."""
    inp = state.get("input") or {}
    pref = inp.get("material", "standard")

    # Sail covers require high UV resistance for marine environments
    uv_required = inp.get("high_uv_exposure", True)

    material = "Acrylic Canvas" if pref == "premium" or uv_required else "Treated Polyester"

    return {
        "log": [f"{UNISPSC_CODE}:determine_material"],
        "material_preference": material,
        "uv_resistant": uv_required,
        "configuration_status": "material_assigned"
    }


def package_result(state: State) -> dict[str, Any]:
    """Finalizes the actor state and prepares the output result."""
    is_ok = state.get("boom_length", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:package_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_preference"),
                "boom_length": state.get("boom_length"),
                "uv_protection": state.get("uv_resistant"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("check_dimensions", check_dimensions)
_g.add_node("determine_material", determine_material)
_g.add_node("package_result", package_result)

_g.add_edge(START, "check_dimensions")
_g.add_edge("check_dimensions", "determine_material")
_g.add_edge("determine_material", "package_result")
_g.add_edge("package_result", END)

graph = _g.compile()
