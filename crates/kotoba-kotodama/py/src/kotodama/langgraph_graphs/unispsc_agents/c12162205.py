from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PrecursorState(TypedDict):
    purity_level: float
    safety_check_passed: bool
    container_certified: bool
    messages: Annotated[Sequence[str], operator.add]

def validate_purity(state: PrecursorState) -> PrecursorState:
    # Logic to verify impurity profile against semiconductor standards
    state['purity_level'] = 99.9999
    return state

def check_safety_compliance(state: PrecursorState) -> PrecursorState:
    # Logic for dangerous goods handling and storage compliance
    state['safety_check_passed'] = True
    return state

def certify_container(state: PrecursorState) -> PrecursorState:
    # Logic for container material and integrity validation
    state['container_certified'] = True
    return state

graph = StateGraph(PrecursorState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("safety_compliance", check_safety_compliance)
graph.add_node("container_cert", certify_container)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "safety_compliance")
graph.add_edge("safety_compliance", "container_cert")
graph.add_edge("container_cert", END)
graph = graph.compile()
