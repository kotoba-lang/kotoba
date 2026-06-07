# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111606 — Folder.
Bespoke graph logic for managing office folder specifications and inventory classification.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111606"
UNISPSC_TITLE = "Folder"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Folder
    material_gsm: int
    pocket_layout: str
    tab_position: str
    is_reinforced: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the folder."""
    inp = state.get("input") or {}
    gsm = int(inp.get("gsm", 250))
    layout = inp.get("layout", "standard-double-pocket")

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "material_gsm": gsm,
        "pocket_layout": layout,
    }


def configure_organization(state: State) -> dict[str, Any]:
    """Determines the organizational features like tabs and reinforcement."""
    inp = state.get("input") or {}
    tab = inp.get("tab", "1/3-cut")
    gsm = state.get("material_gsm", 0)

    # Heavy duty folders are automatically marked as reinforced
    reinforced = gsm > 300 or inp.get("heavy_duty", False)

    return {
        "log": [f"{UNISPSC_CODE}:configure_organization"],
        "tab_position": tab,
        "is_reinforced": reinforced,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Produces the final result for the folder asset record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "attributes": {
                "gsm": state.get("material_gsm"),
                "layout": state.get("pocket_layout"),
                "tab": state.get("tab_position"),
                "reinforced": state.get("is_reinforced"),
            },
            "did": UNISPSC_DID,
            "status": "validated",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_spec)
_g.add_node("configure", configure_organization)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
