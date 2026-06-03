import wit_world
from kotoba_langgraph import StateGraph, KotobaCheckpointer, START, END, handle_invoke
from typing import Any, Dict

# --- Mock Dependencies (Replacing relative imports) ---

class MockPermitState:
    """Mock class for PermitState."""
    def __init__(self, phase: str, project_id: str, completion_pct: int):
        self.phase = phase
        self.project_id = project_id
        self.completion_pct = completion_pct

# Mock transition functions
def transition_to_jurisdiction_identified(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mock implementation for JURISDICTION_IDENTIFIED transition."""
    return {"permit_state": {"phase": "JURISDICTION_IDENTIFIED", "project_id": state.get("projectId", "unknown"), "completion_pct": 10}, "next_node": "template"}

def transition_to_template_selected(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mock implementation for TEMPLATE_SELECTED transition."""
    return {"permit_state": {"phase": "TEMPLATE_SELECTED", "project_id": state.get("projectId", "unknown"), "completion_pct": 20}, "next_node": "prepare"}

def transition_to_application_prepared(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mock implementation for APPLICATION_PREPARED transition."""
    return {"permit_state": {"phase": "APPLICATION_PREPARED", "project_id": state.get("projectId", "unknown"), "completion_pct": 50}, "next_node": "submit"}

def transition_to_submitted(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mock implementation for SUBMITTED transition."""
    return {"permit_state": {"phase": "SUBMITTED", "project_id": state.get("projectId", "unknown"), "completion_pct": 100}, "submission_id": "XYZ123"}

# --- Node Functions ---

def initialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """INIT: Initialize permit state from input."""
    project_id = state.get("projectId", "unknown")
    init_state = MockPermitState(
        phase="INIT",
        project_id=project_id,
        completion_pct=0,
    )
    return {"permit_state": init_state.__dict__, "next_node": "jurisdiction"}

def jurisdiction_identified(state: Dict[str, Any]) -> Dict[str, Any]:
    """JURISDICTION_IDENTIFIED: Lookup jurisdiction."""
    return transition_to_jurisdiction_identified(state)

def template_selected(state: Dict[str, Any]) -> Dict[str, Any]:
    """TEMPLATE_SELECTED: Match template."""
    return transition_to_template_selected(state)

def application_prepared(state: Dict[str, Any]) -> Dict[str, Any]:
    """APPLICATION_PREPARED: Fill application."""
    return transition_to_application_prepared(state)

def submitted(state: Dict[str, Any]) -> Dict[str, Any]:
    """SUBMITTED: RPC submit to jurisdiction."""
    return transition_to_submitted(state)

# --- Graph Building ---

_g = StateGraph(dict)

_g.add_node("init", initialize_state)
_g.add_node("jurisdiction", jurisdiction_identified)
_g.add_node("template", template_selected)
_g.add_node("prepare", application_prepared)
_g.add_node("submit", submitted)

_g.add_edge("init", "jurisdiction")
_g.add_edge("jurisdiction", "template")
_g.add_edge("template", "prepare")
_g.add_edge("prepare", "submit")
_g.add_edge("submit", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

# --- WASM Component Implementation ---

class WitWorld(wit_world.WitWorld):
    def run(self, ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, compiled)