# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131800"
UNISPSC_TITLE = "Silicon Procure"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131800"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_level: float
    supplier_vetted: bool
    batch_serial: str
    quarantine_status: bool

def receive_material(state: State) -> dict[str, Any]:
    """Initial intake of silicon material for procurement processing."""
    inp = state.get("input") or {}
    batch = inp.get("batch", "SIL-B-DEFAULT")
    return {
        "log": [f"{UNISPSC_CODE}:receive_material:{batch}"],
        "batch_serial": batch,
        "purity_level": float(inp.get("purity", 0.0)),
        "supplier_vetted": inp.get("vetted", False),
    }

def inspect_and_certify(state: State) -> dict[str, Any]:
    """Validates the silicon purity against electronic grade standards."""
    purity = state.get("purity_level", 0.0)
    vetted = state.get("supplier_vetted", False)
    # Electronic grade silicon requires high purity and a vetted source
    is_certified = purity >= 0.9999 and vetted
    return {
        "log": [f"{UNISPSC_CODE}:inspect_and_certify:certified={is_certified}"],
        "quarantine_status": not is_certified,
    }

def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and prepares the result payload."""
    quarantined = state.get("quarantine_status", True)
    status = "REJECTED" if quarantined else "ACCEPTED"
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement:status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "batch": state.get("batch_serial"),
            "procurement_status": status,
            "did": UNISPSC_DID,
            "ok": not quarantined,
        },
    }

_g = StateGraph(State)
_g.add_node("receive", receive_material)
_g.add_node("inspect", inspect_and_certify)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "receive")
_g.add_edge("receive", "inspect")
_g.add_edge("inspect", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
