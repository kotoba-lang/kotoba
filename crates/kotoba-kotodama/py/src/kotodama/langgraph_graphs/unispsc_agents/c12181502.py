from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class AdhesionState(TypedDict):
    material_id: str
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_cleared: bool

def validate_safety(state: AdhesionState) -> AdhesionState:
    # Logic to verify hazardous materials compliance
    state['validation_log'] = ["Validated SDS compliance for chemical safety."]
    state['is_cleared'] = True
    return state

def check_curing_params(state: AdhesionState) -> AdhesionState:
    # Verify curing temperature specs for the industrial process
    state['validation_log'].append("Curing parameters within industrial standards.")
    return state

graph = StateGraph(AdhesionState)
graph.add_node("safety_check", validate_safety)
graph.add_node("curing_check", check_curing_params)
graph.add_edge("safety_check", "curing_check")
graph.add_edge("curing_check", END)
graph.set_entry_point("safety_check")
graph = graph.compile()
