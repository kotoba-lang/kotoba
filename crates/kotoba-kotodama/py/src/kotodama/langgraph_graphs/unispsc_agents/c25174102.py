# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174102"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Suspension Systems (UNISPSC 25174102)
    suspension_type: str
    load_rating_kg: int
    damping_factor: float
    safety_compliance: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspects the input for suspension system specifications."""
    inp = state.get("input") or {}
    s_type = inp.get("type", "multi-link")
    load = inp.get("load_rating", 1500)
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "suspension_type": s_type,
        "load_rating_kg": load,
    }


def perform_load_test(state: State) -> dict[str, Any]:
    """Simulates a load dynamics test on the specified suspension type."""
    load = state.get("load_rating_kg", 0)
    # Basic logic to determine damping based on load
    damping = 0.65 if load < 2000 else 0.82
    return {
        "log": [f"{UNISPSC_CODE}:perform_load_test"],
        "damping_factor": damping,
        "safety_compliance": load > 0,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the certification for the suspension component."""
    is_compliant = state.get("safety_compliance", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": is_compliant,
            "metrics": {
                "type": state.get("suspension_type"),
                "damping": state.get("damping_factor"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("test", perform_load_test)
_g.add_node("certify", certify_component)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
